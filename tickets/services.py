import io

import qrcode
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
    subject = "Ваш билет на Fairy Tale Picnic"
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


def mark_order_paid(order, payment_id=""):
    """Single entry point for confirming a payment.

    Called by both the real FreedomPay webhook and the local test-mode
    fake gateway, so the QR-generation / email-sending logic only has
    to live in one place.
    """
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
