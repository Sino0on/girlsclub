import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tickets import services
from tickets.models import Order


class Command(BaseCommand):
    """Issue a ticket without going through any payment gateway — for
    comp/VIP/staff tickets, or just to get a real QR to test the door
    scanner with. Creates a valid, immediately-scannable Order and
    sends the QR straight to a Telegram chat.

    Usage:
        python manage.py issue_ticket \\
            --full-name "Айгуль Иванова" --email aigul@example.com \\
            --telegram-id 795677145 --quantity 1

    The bot can only message a user who has already messaged it at
    least once (e.g. sent /start) — Telegram won't let a bot start a
    conversation. If sendPhoto fails with "bot can't initiate
    conversation", have that person message the bot first, then rerun.
    """

    help = "Issue a ticket outside the payment flow and send its QR to a Telegram chat."

    def add_arguments(self, parser):
        parser.add_argument("--full-name", required=True, help="ФИО for the ticket")
        parser.add_argument("--email", required=True, help="Where the usual ticket email also goes")
        parser.add_argument("--phone", default="", help="Optional")
        parser.add_argument("--quantity", type=int, default=1)
        parser.add_argument(
            "--amount",
            type=int,
            default=0,
            help="Сом charged, 0 by default (comp ticket — nothing was actually paid)",
        )
        parser.add_argument(
            "--telegram-id",
            type=int,
            required=True,
            help="Telegram numeric user/chat ID to send the QR to",
        )
        parser.add_argument(
            "--no-email",
            action="store_true",
            help="Skip sending the usual ticket confirmation email",
        )

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set in .env")

        order = Order.objects.create(
            full_name=options["full_name"],
            email=options["email"],
            phone=options["phone"],
            quantity=options["quantity"],
            amount=options["amount"],
            rules_agreed=True,
            payment_method=Order.METHOD_MANUAL,
            status=Order.STATUS_APPROVED,  # valid & scannable right away
        )
        services.generate_qr_code(order)
        order.save()

        if not options["no_email"]:
            services.send_ticket_email(order)

        self._send_telegram_qr(order, options["telegram_id"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Issued order #{order.id} for {order.full_name} "
                f"({order.quantity} билет(ов)), qr_token={order.qr_token}"
            )
        )

    def _send_telegram_qr(self, order, telegram_id):
        caption = (
            "🎟 Ваш билет FairyTale Picnic\n\n"
            f"{order.full_name}\n"
            f"Билетов: {order.quantity}\n\n"
            "Покажите этот QR-код на входе."
        )
        order.qr_image.open("rb")
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendPhoto",
                data={"chat_id": telegram_id, "caption": caption},
                files={"photo": order.qr_image.read()},
                timeout=15,
            )
        finally:
            order.qr_image.close()

        result = response.json()
        if not result.get("ok"):
            raise CommandError(
                f"Telegram API error: {result.get('description', result)}. "
                "Note: the bot can only message a user who has already "
                "messaged it first (e.g. sent /start)."
            )
