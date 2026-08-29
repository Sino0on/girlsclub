from django.conf import settings


def site_settings(request):
    """Expose a few site-wide constants to every template."""
    return {
        "TICKET_PRICE_KGS": settings.TICKET_PRICE_KGS,
    }
