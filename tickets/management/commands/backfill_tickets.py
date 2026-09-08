from django.core.management.base import BaseCommand

from tickets import services
from tickets.models import Order


class Command(BaseCommand):
    """One-time repair for orders that predate the Ticket model
    (migration 0005) — they lost their visible QR when Order.qr_image
    was dropped, since nothing automatically created Ticket rows for
    orders that already existed at that point.

    services.create_tickets() reuses order.qr_token for the first
    ticket — the *same* token these orders always had (that field was
    never removed) — so a QR a buyer already has saved/emailed keeps
    scanning correctly: it encodes /tickets/verify/<token>/, and that
    token resolves to a real Ticket again after this runs.

    For quantity>1 orders (comp/VIP batches issued before the Ticket
    model existed), ticket #1 gets that same backward-compatible
    token; the rest get fresh ones, since the old single-QR-per-order
    system never issued them distinct codes to begin with — there is
    nothing to preserve there, they're genuinely new.

    Safe to re-run: only acts on orders that currently have zero
    tickets, and create_tickets() itself is a no-op if any exist.
    """

    help = "Backfill Ticket rows for orders that lost their QR when the Ticket model was introduced."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List affected orders without changing anything",
        )

    def handle(self, *args, **options):
        valid_statuses = [
            Order.STATUS_PAID,
            Order.STATUS_APPROVED,
            Order.STATUS_PENDING_REVIEW,
        ]
        orders = list(
            Order.objects.filter(status__in=valid_statuses)
            .exclude(id__in=Order.objects.filter(tickets__isnull=False).values("id"))
        )

        if not orders:
            self.stdout.write(self.style.SUCCESS("Nothing to backfill — every valid order already has tickets."))
            return

        for order in orders:
            self.stdout.write(
                f"Order #{order.id} — {order.full_name} <{order.email}>, "
                f"{order.quantity} билет(ов), статус {order.get_status_display()}"
            )
            if not options["dry_run"]:
                services.create_tickets(order)

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"Dry run — {len(orders)} order(s) would be fixed. Re-run without --dry-run to apply.")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"Backfilled tickets for {len(orders)} order(s)."))
