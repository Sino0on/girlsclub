from django.conf import settings


def _format_phone(raw):
    digits = "".join(ch for ch in raw if ch.isdigit())
    if digits.startswith("996") and len(digits) == 12:
        display = f"+{digits[0:3]} {digits[3:6]} {digits[6:9]} {digits[9:12]}"
    else:
        display = raw
    return {"digits": digits, "display": display}


def site_settings(request):
    """Expose a few site-wide constants to every template."""
    return {
        "TICKET_PRICE_KGS": settings.TICKET_PRICE_KGS,
        "CONTACT_PHONES": [_format_phone(p) for p in settings.CONTACT_PHONES],
    }
