import io
import json

import qrcode
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Order


def generate_qr_code(order):
    """Render a QR PNG encoding this order's verification URL and attach
    it to the order (does not save the model — caller is expected to)."""
    img = qrcode.make(order.get_verify_url())
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    filename = f"ticket-{order.qr_token}.png"
    order.qr_image.save(filename, ContentFile(buffer.getvalue()), save=False)


def send_ticket_email(order):
    subject = "Ваш билет на FairyTale Picnic"
    context = {"order": order}
    text_body = render_to_string("tickets/email/ticket_email.txt", context)
    html_body = render_to_string("tickets/email/ticket_email.html", context)

    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[order.email])
    message.attach_alternative(html_body, "text/html")

    if order.qr_image:
        order.qr_image.open("rb")
        message.attach(
            f"ticket-{order.qr_token}.png", order.qr_image.read(), "image/png"
        )
        order.qr_image.close()

    message.send(fail_silently=False)
    order.email_sent_at = timezone.now()
    order.save(update_fields=["email_sent_at"])


def send_rejection_email(order):
    subject = "Ваш билет на FairyTale Picnic аннулирован"
    context = {"order": order}
    text_body = render_to_string("tickets/email/rejection_email.txt", context)
    html_body = render_to_string("tickets/email/rejection_email.html", context)

    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[order.email])
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)

    order.rejection_email_sent_at = timezone.now()
    order.save(update_fields=["rejection_email_sent_at"])


def notify_moderators(order):
    """Send the uploaded receipt to the Telegram moderator group with a
    Да/Нет inline keyboard. Best-effort — a Telegram/network hiccup here
    must not stop the buyer from getting their ticket, so callers should
    swallow exceptions from this (see issue_ticket)."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_MODERATOR_CHAT_ID
    if not token or not chat_id:
        return

    caption = (
        "🎟 Новый заказ билетов FairyTale Picnic\n\n"
        f"ФИО: {order.full_name}\n"
        f"Email: {order.email}\n"
        f"Телефон: {order.phone}\n"
        f"Количество: {order.quantity}\n"
        f"Сумма: {order.amount} сом\n\n"
        "Билет уже отправлен покупателю. «Нет» аннулирует его и уведомит "
        "покупателя по почте."
    )
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Да", "callback_data": f"order_yes:{order.id}"},
                {"text": "❌ Нет", "callback_data": f"order_no:{order.id}"},
            ]
        ]
    }

    api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
    data = {
        "chat_id": chat_id,
        "caption": caption,
        "reply_markup": json.dumps(keyboard),
    }

    if order.receipt:
        order.receipt.open("rb")
        try:
            response = requests.post(
                api_url,
                data=data,
                files={"photo": order.receipt.read()},
                timeout=15,
            )
        finally:
            order.receipt.close()
    else:
        data["chat_id"] = chat_id
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={**data, "text": caption},
            timeout=15,
        )

    response.raise_for_status()
    result = response.json().get("result", {})
    order.telegram_chat_id = str(result.get("chat", {}).get("id", chat_id))
    order.telegram_message_id = result.get("message_id")
    order.save(update_fields=["telegram_chat_id", "telegram_message_id"])


def issue_ticket(order):
    """Called the moment a buyer uploads their bank-transfer receipt —
    the ticket is issued right away (no waiting on moderator review);
    the Telegram Да/Нет is purely a post-hoc check that can void it."""
    generate_qr_code(order)
    order.status = Order.STATUS_PENDING_REVIEW
    order.submitted_at = timezone.now()
    order.save()

    send_ticket_email(order)

    try:
        notify_moderators(order)
    except Exception:
        # The buyer already has their ticket; a moderator can still be
        # notified manually (the order is visible in /admin/) even if
        # this particular Telegram call failed.
        pass


def approve_order(order_id):
    order = Order.objects.filter(id=order_id).first()
    if not order or order.status != Order.STATUS_PENDING_REVIEW:
        return
    order.status = Order.STATUS_APPROVED
    order.decided_at = timezone.now()
    order.save(update_fields=["status", "decided_at"])


def reject_order(order_id):
    order = Order.objects.filter(id=order_id).first()
    if not order or order.status not in (
        Order.STATUS_PENDING_REVIEW,
        Order.STATUS_APPROVED,
    ):
        return
    order.status = Order.STATUS_REJECTED
    order.decided_at = timezone.now()
    order.save(update_fields=["status", "decided_at"])
    send_rejection_email(order)


def try_check_in(order):
    """Attempt to check a ticket in at the door. Used by both the
    manual /tickets/verify/ page and the camera scanner's JSON API —
    the single place that decides green vs. red.

    Returns (ok, reason, message):
      ok=True,  reason="ok"          -> green light, just checked in
      ok=False, reason="used"        -> red, already checked in before
      ok=False, reason="rejected"    -> red, ticket was voided
      ok=False, reason="not_issued"  -> red, no valid ticket on this order
    """
    if order.is_rejected:
        return False, "rejected", "Билет аннулирован"

    if not order.is_valid_ticket:
        return False, "not_issued", "Билет ещё не оформлен"

    if order.is_checked_in:
        when = timezone.localtime(order.checked_in_at).strftime("%H:%M")
        return False, "used", f"Уже использован сегодня в {when}"

    order.checked_in_at = timezone.now()
    order.save(update_fields=["checked_in_at"])
    return True, "ok", "Билет действителен"


# --- FreedomPay flow (paused, kept working) ---


def mark_order_paid(order, payment_id=""):
    """Single entry point for confirming a FreedomPay payment. Called by
    both the real webhook and the local test-mode fake gateway."""
    if order.status == Order.STATUS_PAID:
        return  # already processed — avoid duplicate emails on retried callbacks

    order.status = Order.STATUS_PAID
    order.payment_id = payment_id
    order.paid_at = timezone.now()
    if not order.qr_image:
        generate_qr_code(order)
    order.save()
    send_ticket_email(order)


def mark_order_failed(order):
    if order.status == Order.STATUS_PAID:
        return
    order.status = Order.STATUS_FAILED
    order.save(update_fields=["status"])
