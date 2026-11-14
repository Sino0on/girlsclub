import time
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from tickets import services
from tickets.models import Order


class Command(BaseCommand):
    """Send the "💳 Куплен билет!" message to the Telegram group for paid
    orders that never got one (e.g. the bot keys were missing in .env).

    Usage:
        python manage.py notify_purchases --dry-run     # today, just list
        python manage.py notify_purchases               # today, send
        python manage.py notify_purchases --date 2026-11-15

    Orders already announced (telegram_message_id set) are skipped, so
    it is safe to run more than once.
    """

    help = "Send Telegram purchase notices for paid orders of a given day that weren't announced."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="YYYY-MM-DD (Bishkek time). Default: today")
        parser.add_argument("--dry-run", action="store_true", help="Only list the orders, send nothing")

    def handle(self, *args, **opts):
        if not opts["dry_run"] and not (settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_MODERATOR_CHAT_ID):
            raise CommandError("TELEGRAM_BOT_TOKEN / TELEGRAM_MODERATOR_CHAT_ID are not set in .env")

        if opts["date"]:
            try:
                day = datetime.strptime(opts["date"], "%Y-%m-%d").date()
            except ValueError:
                raise CommandError("--date must be YYYY-MM-DD")
        else:
            day = timezone.localdate()
        start = timezone.make_aware(datetime.combine(day, datetime.min.time()))
        end = start + timedelta(days=1)

        orders = (
            Order.objects.filter(status=Order.STATUS_PAID, paid_at__gte=start, paid_at__lt=end)
            .filter(telegram_message_id__isnull=True)
            .order_by("paid_at")
        )
        total = orders.count()
        self.stdout.write(f"{day:%d.%m.%Y}: paid orders not yet announced — {total}")

        sent = 0
        for order in orders:
            line = f"  #{order.pk} {timezone.localtime(order.paid_at):%H:%M} {order.full_name} · {order.quantity} шт · {order.amount} сом"
            if opts["dry_run"]:
                self.stdout.write(line)
                continue
            try:
                services.notify_group_of_purchase(order)
            except Exception as exc:
                self.stderr.write(f"{line}  — ОШИБКА: {exc}")
                continue
            sent += 1
            self.stdout.write(f"{line}  — отправлено")
            time.sleep(1)  # stay well under Telegram's group rate limit

        if not opts["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Sent {sent} of {total}"))
