from django.contrib import admin
from django.utils.html import format_html

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "email",
        "phone",
        "amount",
        "status",
        "created_at",
        "paid_at",
        "checked_in_column",
    )
    list_filter = ("status",)
    search_fields = ("full_name", "email", "phone", "qr_token", "payment_id")
    readonly_fields = (
        "qr_token",
        "qr_preview",
        "created_at",
        "paid_at",
        "email_sent_at",
        "checked_in_at",
    )
    fields = (
        "full_name",
        "email",
        "phone",
        "rules_agreed",
        "amount",
        "status",
        "payment_id",
        "qr_token",
        "qr_preview",
        "created_at",
        "paid_at",
        "email_sent_at",
        "checked_in_at",
    )

    def qr_preview(self, obj):
        if obj.qr_image:
            return format_html('<img src="{}" style="height:160px" />', obj.qr_image.url)
        return "—"

    qr_preview.short_description = "QR-код"

    def checked_in_column(self, obj):
        return obj.is_checked_in

    checked_in_column.boolean = True
    checked_in_column.short_description = "На входе"
