from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from . import services
from .models import Order, PaymentInstructions, PaymentSettings, Ticket


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 0
    can_delete = False
    fields = ("qr_preview", "qr_token", "checked_in_at")
    readonly_fields = ("qr_preview", "qr_token", "checked_in_at")

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" style="height:90px" />', obj.qr_image.url)
        return "—"

    qr_preview.short_description = "QR-код"

    def has_add_permission(self, request, obj=None):
        return False  # tickets are only ever created by services.create_tickets


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "phone",
        "quantity",
        "amount",
        "payment_method",
        "status",
        "created_at",
        "checked_in_column",
        "is_legacy_shared_qr",
    )
    list_filter = ("payment_method", "status", "is_legacy_shared_qr")
    search_fields = ("full_name", "email", "phone", "qr_token", "payment_id", "tickets__qr_token")
    readonly_fields = (
        "qr_token",
        "receipt_preview",
        "created_at",
        "submitted_at",
        "decided_at",
        "paid_at",
        "email_sent_at",
        "rejection_email_sent_at",
        "telegram_chat_id",
        "telegram_message_id",
    )
    fields = (
        "full_name",
        "email",
        "phone",
        "rules_agreed",
        "quantity",
        "amount",
        "payment_method",
        "status",
        "receipt_preview",
        "qr_token",
        "is_legacy_shared_qr",
        "payment_id",
        "telegram_chat_id",
        "telegram_message_id",
        "created_at",
        "submitted_at",
        "decided_at",
        "paid_at",
        "email_sent_at",
        "rejection_email_sent_at",
    )
    inlines = [TicketInline]
    actions = ["mark_legacy_shared_qr"]

    @admin.action(description="Пометить как заказ с общим QR на группу")
    def mark_legacy_shared_qr(self, request, queryset):
        for order in queryset:
            services.create_tickets(order)  # no-op if tickets already exist
        updated = queryset.update(is_legacy_shared_qr=True)
        self.message_user(request, f"Помечено как общий QR на группу: {updated}.")

    def receipt_preview(self, obj):
        if not obj.receipt:
            return "—"
        if obj.receipt.name.lower().endswith(".pdf"):
            return format_html('<a href="{}" target="_blank">Открыть PDF</a>', obj.receipt.url)
        return format_html(
            '<a href="{}" target="_blank"><img src="{}" style="height:220px" /></a>',
            obj.receipt.url,
            obj.receipt.url,
        )

    receipt_preview.short_description = "Чек"

    def checked_in_column(self, obj):
        return f"{obj.checked_in_count} / {obj.quantity}"

    checked_in_column.short_description = "На входе"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "qr_token", "checked_in_at")
    list_filter = ("checked_in_at",)
    search_fields = ("qr_token", "order__full_name", "order__email")
    readonly_fields = ("order", "qr_token", "qr_preview", "checked_in_at")
    fields = ("order", "qr_token", "qr_preview", "checked_in_at")
    actions = ["mark_not_checked_in"]

    @admin.action(description="Сделать билет активным (сбросить отметку о сканировании)")
    def mark_not_checked_in(self, request, queryset):
        updated = queryset.update(checked_in_at=None)
        self.message_user(request, f"Сброшено билетов: {updated}.")

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" style="height:200px" />', obj.qr_image.url)
        return "—"

    qr_preview.short_description = "QR-код"

    def has_add_permission(self, request):
        return False


@admin.register(PaymentInstructions)
class PaymentInstructionsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "is_active", "updated_at")
    list_editable = ("is_active",)


@admin.register(PaymentSettings)
class PaymentSettingsAdmin(admin.ModelAdmin):
    """Singleton — one row controls which gateway "Купить билет" uses."""

    list_display = ("active_method",)
    fields = ("active_method",)

    def has_add_permission(self, request):
        return not PaymentSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Skip straight to the (only) row's edit form instead of a
        # changelist with one link to click through.
        obj = PaymentSettings.load()
        return redirect(reverse("admin:tickets_paymentsettings_change", args=[obj.pk]))
