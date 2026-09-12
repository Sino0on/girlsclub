from django.core.management.base import BaseCommand
from django.db.migrations.recorder import MigrationRecorder

from tickets import services
from tickets.models import Order

# The migration that introduced the Ticket model and dropped
# Order.qr_image/checked_in_at. Its recorded apply timestamp is the
# exact, self-contained boundary between "legacy order — only ever had
# one shared QR for the whole group" and "new order — every person
# gets their own QR", for whichever environment this runs in (local,
# staging, prod each applied it at their own time).
LEGACY_CUTOFF_MIGRATION = "0005_remove_order_checked_in_at_remove_order_qr_image_and_more"


class Command(BaseCommand):
    """One-time (but safely re-runnable) repair for orders that predate
    the Ticket model:

    1. They lost their visible QR when Order.qr_image was dropped, since
       nothing automatically created Ticket rows for orders that already
       existed at that point. services.create_tickets() reuses
       order.qr_token for the first ticket — the *same* token these
       orders always had — so a QR a buyer already has saved/emailed
       keeps scanning correctly.

    2. For quantity>1 orders (group purchases, comp/VIP batches issued
       before the Ticket model existed), the buyer was only ever given
       that ONE QR for the whole group, never N separate ones — so this
       command also flags the order as is_legacy_shared_qr, which makes
       scanning that one QR check the *whole group* in at once (see
       services.try_check_in) instead of admitting a single person while
       the rest of the group's tickets sit looking unused forever.

    Driven by created_at < (when migration 0005 was applied here), not
    by "has no tickets yet" — so re-running this after it already
    created tickets once (e.g. it ran on prod before this flag existed)
    still correctly sets is_legacy_shared_qr on those same orders.
    """

    help = "Backfill Ticket rows + is_legacy_shared_qr for orders that predate the Ticket model."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List affected orders without changing anything",
        )

    def handle(self, *args, **options):
        migration = MigrationRecorder.Migration.objects.filter(
            app="tickets", name=LEGACY_CUTOFF_MIGRATION
        ).first()
        if not migration:
            self.stdout.write(self.style.ERROR(
                f"Migration tickets.{LEGACY_CUTOFF_MIGRATION} hasn't been applied yet — run migrate first."
            ))
            return
        cutoff = migration.applied

        valid_statuses = [
            Order.STATUS_PAID,
            Order.STATUS_APPROVED,
            Order.STATUS_PENDING_REVIEW,
        ]
        candidates = Order.objects.filter(status__in=valid_statuses, created_at__lt=cutoff)

        to_fix = []
        for order in candidates:
            needs_tickets = not order.tickets.exists()
            needs_flag = not order.is_legacy_shared_qr
            if needs_tickets or needs_flag:
                to_fix.append((order, needs_tickets, needs_flag))

        if not to_fix:
            self.stdout.write(self.style.SUCCESS("Nothing to backfill — every legacy order already has tickets and is flagged."))
            return

        for order, needs_tickets, needs_flag in to_fix:
            actions = []
            if needs_tickets:
                actions.append("создать билеты")
            if needs_flag:
                actions.append("пометить как общий QR на группу")
            self.stdout.write(
                f"Order #{order.id} — {order.full_name} <{order.email}>, "
                f"{order.quantity} билет(ов), статус {order.get_status_display()} "
                f"[{', '.join(actions)}]"
            )
            if not options["dry_run"]:
                services.create_tickets(order)
                if needs_flag:
                    order.is_legacy_shared_qr = True
                    order.save(update_fields=["is_legacy_shared_qr"])

        if options["dry_run"]:
            self.stdout.write(
                self.style.WARNING(f"Dry run — {len(to_fix)} order(s) would be fixed. Re-run without --dry-run to apply.")
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"Backfilled {len(to_fix)} order(s)."))
