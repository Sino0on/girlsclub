from django.apps import AppConfig


class TicketsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tickets"
    verbose_name = "Билеты"

    def ready(self):
        from .net import force_ipv4_for_requests

        force_ipv4_for_requests()
