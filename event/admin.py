from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html

from .models import EventSettings, FAQItem, Partner, ProgramItem


@admin.register(EventSettings)
class EventSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Мероприятие", {"fields": ("title", "title_ru", "event_date", "gathering_time", "program_time", "venue", "venue_map_url")}),
        ("Стоимость", {"fields": ("price_early", "price_late", "price_switch_at", "current_price_display", "seats_limited", "deposit")}),
        ("Ссылки", {"fields": ("buy_url", "instagram_url", "dresscode_url")}),
        ("VIP-тур", {"fields": ("prize_image", "prize_terms")}),
    )
    readonly_fields = ("current_price_display",)

    @admin.display(description="Цена прямо сейчас")
    def current_price_display(self, obj):
        return f"{obj.current_price()} сом"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Singleton: skip the list, go straight to the one row.
        obj = EventSettings.load()
        return redirect(reverse("admin:event_eventsettings_change", args=[obj.pk]))


@admin.register(ProgramItem)
class ProgramItemAdmin(admin.ModelAdmin):
    list_display = ("title", "description", "order", "is_active")
    list_editable = ("order", "is_active")
    readonly_fields = ("static_image",)
    ordering = ("order", "id")


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ("name", "logo_preview", "url", "order", "is_active")
    list_editable = ("order", "is_active")
    ordering = ("order", "id")

    @admin.display(description="Логотип")
    def logo_preview(self, obj):
        if not obj.logo:
            return "—"
        return format_html('<img src="{}" style="height:32px;max-width:120px;object-fit:contain">', obj.logo.url)


@admin.register(FAQItem)
class FAQItemAdmin(admin.ModelAdmin):
    list_display = ("question", "order", "is_active")
    list_editable = ("order", "is_active")
    search_fields = ("question", "answer")
    ordering = ("order", "id")
