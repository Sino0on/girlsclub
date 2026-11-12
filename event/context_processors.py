from django.conf import settings
from django.urls import reverse

from .models import EventSettings


def _format_phone(raw):
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("996") and len(digits) == 12:
        display = f"+{digits[0:3]} {digits[3:6]} {digits[6:9]} {digits[9:12]}"
    else:
        display = raw
    return {"digits": digits, "display": display}


def site_settings(request):
    """Expose a few site-wide constants to every template."""
    event = EventSettings.load()
    return {
        "EVENT": event,
        # Price right now — switches automatically at event.price_switch_at.
        "TICKET_PRICE_KGS": event.current_price(),
        # Every "Купить билет" button points here.
        "BUY_URL": event.buy_url or reverse("tickets:buy"),
        "CONTACT_PHONES": [_format_phone(p) for p in settings.CONTACT_PHONES],
    }
