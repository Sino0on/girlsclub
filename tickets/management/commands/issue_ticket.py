from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tickets import services
from tickets.models import Order


class Command(BaseCommand):
    """Issue ticket(s) without going through any payment gateway — for
    comp/VIP/staff tickets, or just to get a real QR to test the door
    scanner with. Creates a valid, immediately-scannable Order with one
    individual Ticket (own QR) per --quantity, and sends every QR
    straight to a Telegram chat, one photo each.

    Usage:
        python manage.py issue_ticket \\
            --full-name "Айгуль Иванова" --email aigul@example.com \\
            --telegram-id 795677145 --quantity 50

    The bot can only message a user who has already messaged it at
    least once (e.g. sent /start) — Telegram won't let a bot start a
    conversation. If sending fails with "bot can't initiate
    conversation", have that person message the bot first, then rerun.
    """

    help = "Issue ticket(s) outside the payment flow and send their QRs to a Telegram chat."

    def add_arguments(self, parser):
        parser.add_argument("--full-name", required=True, help="ФИО for the ticket(s)")
        parser.add_argument("--email", required=True, help="Where the usual ticket email also goes")
        parser.add_argument("--phone", default="", help="Optional")
        parser.add_argument("--quantity", type=int, default=1, help="How many individual tickets/QRs to create")
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
            help="Telegram numeric user/chat ID to send the QRs to",
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
        tickets = services.create_tickets(order)

        if not options["no_email"]:
            services.send_ticket_email(order)

        try:
            services.send_tickets_to_telegram(order, options["telegram_id"])
        except Exception as exc:
            raise CommandError(
                f"{exc}. Note: the bot can only message a user who has "
                "already messaged it first (e.g. sent /start)."
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Issued order #{order.id} for {order.full_name} — "
                f"{len(tickets)} билет(ов), sent to Telegram id {options['telegram_id']}"
            )
        )
