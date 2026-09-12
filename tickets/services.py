import io
import json
import time

import qrcode
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import Order, Ticket


def generate_qr_code(ticket):
    """Render a QR PNG encoding this ticket's verification URL and
    attach it (does not save the model — caller is expected to)."""
    img = qrcode.make(ticket.get_verify_url())
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    filename = f"ticket-{ticket.qr_token}.png"
    ticket.qr_image.save(filename, ContentFile(buffer.getvalue()), save=False)


def create_tickets(order):
    """Create order.quantity individual Ticket rows, each with its own
    QR — idempotent, so calling this twice (e.g. a retried webhook)
    never issues duplicates. Returns the order's tickets.

    The first ticket reuses order.qr_token instead of generating a new
    one. order.qr_token is already a unique UUID assigned the moment
    the order was created, so this loses nothing — and it means a QR
    a buyer already has (emailed, saved, screenshotted) keeps scanning
    correctly even if tickets get (re)created later, e.g. by
    backfill_tickets after the Order.qr_image -> Ticket migration."""
    existing = list(order.tickets.all())
    if existing:
        return existing

    tickets = []
    for i in range(order.quantity):
        ticket = Ticket(order=order, qr_token=order.qr_token) if i == 0 else Ticket(order=order)
        generate_qr_code(ticket)
        ticket.save()
        tickets.append(ticket)
    return tickets


def send_ticket_email(order):
    tickets = list(order.tickets.all())
    context = {"order": order, "tickets": tickets}
    subject = "Ваш билет на FairyTale Picnic" if len(tickets) == 1 else "Ваши билеты на FairyTale Picnic"
    text_body = render_to_string("tickets/email/ticket_email.txt", context)
    html_body = render_to_string("tickets/email/ticket_email.html", context)

    message = EmailMultiAlternatives(subject=subject, body=text_body, to=[order.email])
    message.attach_alternative(html_body, "text/html")

    for i, ticket in enumerate(tickets, start=1):
        if not ticket.qr_image:
            continue
        ticket.qr_image.open("rb")
        message.attach(f"ticket-{i}-{ticket.qr_token}.png", ticket.qr_image.read(), "image/png")
        ticket.qr_image.close()

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
    the ticket(s) are issued right away (no waiting on moderator
    review); the Telegram Да/Нет is purely a post-hoc check that can
    void them."""
    create_tickets(order)
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


def resolve_ticket(token):
    """Find the Ticket a scanned QR token should check in.

    A direct Ticket.qr_token match is the normal case — every order's
    first ticket reuses order.qr_token (see create_tickets), so this
    is what matches for both new orders and already-backfilled legacy
    ones.

    If nothing matches, the token might still be an Order.qr_token
    from before the Ticket model existed: those orders only ever had
    that one QR printed/sent for the whole group, and never got a
    Ticket row created for them. Rather than depending on someone
    having run backfill_tickets before the doors open, create it right
    here and flag the order as a legacy shared-QR group — so scanning
    that old QR just works the first time, no manual step required.

    Returns None if the token matches neither a Ticket nor a valid
    Order.
    """
    ticket = Ticket.objects.select_related("order").filter(qr_token=token).first()
    if ticket:
        return ticket

    order = Order.objects.filter(qr_token=token).first()
    if not order or not order.is_valid_ticket:
        return None

    if not order.tickets.exists():
        create_tickets(order)
    if not order.is_legacy_shared_qr:
        order.is_legacy_shared_qr = True
        order.save(update_fields=["is_legacy_shared_qr"])

    return order.tickets.filter(qr_token=token).first()


def try_check_in(ticket):
    """Attempt to check one ticket in at the door. Used by both the
    manual /tickets/verify/ page and the camera scanner's JSON API —
    the single place that decides green vs. red.

    Returns (ok, reason, message):
      ok=True,  reason="ok"          -> green light, just checked in
      ok=False, reason="used"        -> red, already checked in before
      ok=False, reason="rejected"    -> red, ticket was voided
      ok=False, reason="not_issued"  -> red, no valid ticket on this order
    """
    order = ticket.order
    if order.is_rejected:
        return False, "rejected", "Билет аннулирован"

    if not order.is_valid_ticket:
        return False, "not_issued", "Билет ещё не оформлен"

    if order.is_legacy_shared_qr:
        return _try_check_in_group(order)

    if ticket.is_checked_in:
        when = timezone.localtime(ticket.checked_in_at).strftime("%H:%M")
        return False, "used", f"Уже использован сегодня в {when}"

    ticket.checked_in_at = timezone.now()
    ticket.save(update_fields=["checked_in_at"])
    return True, "ok", "Билет действителен"


def _try_check_in_group(order):
    """Legacy orders (see Order.is_legacy_shared_qr) only ever had ONE
    QR physically handed to the buyer, covering the whole quantity —
    unlike today's orders, where each Ticket row's QR was actually
    distributed to a distinct person. So scanning that one QR must
    admit the entire group in a single scan, not just the lone Ticket
    row it happens to point at (which would otherwise silently leave
    the rest of the group's tickets looking forever unused)."""
    tickets = list(order.tickets.all())
    if all(t.is_checked_in for t in tickets):
        when = timezone.localtime(tickets[0].checked_in_at).strftime("%H:%M")
        return False, "used", f"Уже использован сегодня в {when}"

    now = timezone.now()
    for t in tickets:
        t.checked_in_at = now
    Ticket.objects.bulk_update(tickets, ["checked_in_at"])

    if order.quantity > 1:
        return True, "ok", f"Билет действителен — пропустить всю группу ({order.quantity} чел.)"
    return True, "ok", "Билет действителен"


def send_tickets_to_telegram(order, telegram_id, pause=0.5):
    """Send every ticket in the order as its own photo to a Telegram
    chat — used by the issue_ticket management command. `pause` throttles
    between sends so a big quantity doesn't trip Telegram's flood control
    on a single chat."""
    token = settings.TELEGRAM_BOT_TOKEN
    tickets = list(order.tickets.all())
    total = len(tickets)
    for i, ticket in enumerate(tickets, start=1):
        caption = (
            "🎟 Ваш билет FairyTale Picnic\n\n"
            f"{order.full_name}\n"
            f"Билет {i} из {total}\n\n"
            "Покажите этот QR-код на входе."
        )
        ticket.qr_image.open("rb")
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data={"chat_id": telegram_id, "caption": caption},
                files={"photo": ticket.qr_image.read()},
                timeout=15,
            )
        finally:
            ticket.qr_image.close()
        result = response.json()
        if not result.get("ok"):
            raise RuntimeError(f"Telegram API error on ticket {i}/{total}: {result}")
        if i < total and pause:
            time.sleep(pause)


# --- Gateway flow (FreedomPay paused, Finik active) ---


def notify_group_of_purchase(order):
    """Heads-up to the Telegram group whenever a gateway payment
    (FreedomPay/Finik) succeeds — plain informational message, no
    Да/Нет buttons (unlike notify_moderators, which is for reviewing a
    manual-transfer receipt, not just announcing a sale)."""
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_MODERATOR_CHAT_ID
    if not token or not chat_id:
        return

    text = (
        "💳 Куплен билет!\n\n"
        f"ФИО: {order.full_name}\n"
        f"Email: {order.email}\n"
        f"Телефон: {order.phone}\n"
        f"Количество: {order.quantity}\n"
        f"Сумма: {order.amount} сом\n"
        f"Способ оплаты: {order.get_payment_method_display()}"
    )
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data={"chat_id": chat_id, "text": text},
        timeout=15,
    )
    response.raise_for_status()


def mark_order_paid(order, payment_id="", payment_method=None):
    """Single entry point for confirming a gateway payment (FreedomPay
    or Finik). Called by the real webhook and the local test-mode fake
    gateway alike — idempotent, so retried webhook deliveries are safe."""
    if order.status == Order.STATUS_PAID:
        return  # already processed — avoid duplicate emails on retried callbacks

    order.status = Order.STATUS_PAID
    order.payment_id = payment_id
    if payment_method:
        order.payment_method = payment_method
    order.paid_at = timezone.now()
    order.save()
    create_tickets(order)
    send_ticket_email(order)

    try:
        notify_group_of_purchase(order)
    except Exception:
        # The buyer already has their ticket regardless of whether this
        # Telegram heads-up goes through — never block on it.
        pass


def mark_order_failed(order):
    if order.status == Order.STATUS_PAID:
        return
    order.status = Order.STATUS_FAILED
    order.save(update_fields=["status"])
