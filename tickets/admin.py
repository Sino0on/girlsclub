from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .models import Order, PaymentInstructions, PaymentSettings


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
    )
    list_filter = ("payment_method", "status")
    search_fields = ("full_name", "email", "phone", "qr_token", "payment_id")
    readonly_fields = (
        "qr_token",
        "qr_preview",
        "receipt_preview",
        "created_at",
        "submitted_at",
        "decided_at",
        "paid_at",
        "email_sent_at",
        "rejection_email_sent_at",
        "checked_in_at",
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
        "qr_preview",
        "payment_id",
        "telegram_chat_id",
        "telegram_message_id",
        "created_at",
        "submitted_at",
        "decided_at",
        "paid_at",
        "email_sent_at",
        "rejection_email_sent_at",
        "checked_in_at",
    )

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" style="height:160px" />', obj.qr_image.url)
        return "—"

    qr_preview.short_description = "QR-код"

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
        return obj.is_checked_in

    checked_in_column.boolean = True
    checked_in_column.short_description = "На входе"


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
