"""
FreedomPay payment gateway adapter.

This follows the "pg_" parameter / signature scheme that FreedomPay KZ's
Merchant API documentation describes (the same family of protocol used by
several CIS payment gateways: concatenate script_name + sorted param
values + secret key, then hash). It is NOT verified against a live
FreedomPay account — confirm the exact endpoint, parameter names, the
callback's script_name, and the hashing algorithm against the actual
docs/keys you receive, and adjust this file accordingly.

Until real credentials are configured (FREEDOMPAY_MERCHANT_ID /
FREEDOMPAY_SECRET_KEY in .env) — or while FREEDOMPAY_TEST_MODE=True —
`create_payment()` sends buyers to a local fake payment page instead
(see views.fake_gateway), so the whole order -> paid -> QR -> email
flow is testable today.
"""

import hashlib
import random
import string
import xml.etree.ElementTree as ET

from django.conf import settings
from django.urls import reverse


class FreedomPayError(Exception):
    pass


def _random_salt(length=16):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


def _make_signature(script_name, params, secret_key):
    keys = sorted(k for k in params if k != "pg_sig")
    parts = [script_name] + [str(params[k]) for k in keys] + [secret_key]
    raw = ";".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def is_configured():
    return bool(settings.FREEDOMPAY_MERCHANT_ID and settings.FREEDOMPAY_SECRET_KEY)


def build_init_params(order):
    base = settings.SITE_URL
    params = {
        "pg_merchant_id": settings.FREEDOMPAY_MERCHANT_ID,
        "pg_order_id": str(order.qr_token),
        "pg_amount": str(order.amount),
        "pg_currency": "KGS",
        "pg_description": f"Билет Fairy Tale Picnic — {order.full_name}",
        "pg_salt": _random_salt(),
        "pg_result_url": f"{base}{reverse('tickets:payment_callback')}",
        "pg_success_url": f"{base}{reverse('tickets:payment_success', args=[order.qr_token])}",
        "pg_failure_url": f"{base}{reverse('tickets:payment_fail', args=[order.qr_token])}",
        "pg_request_method": "POST",
        "pg_testing_mode": "0",
    }
    params["pg_sig"] = _make_signature(
        "init_payment.php", params, settings.FREEDOMPAY_SECRET_KEY
    )
    return params


def create_payment(order):
    """Return a URL to send the buyer to in order to pay for `order`."""
    if settings.FREEDOMPAY_TEST_MODE or not is_configured():
        return f"{settings.SITE_URL}{reverse('tickets:fake_gateway', args=[order.qr_token])}"

    import requests

    params = build_init_params(order)
    response = requests.post(settings.FREEDOMPAY_API_URL, data=params, timeout=15)
    response.raise_for_status()

    # Expected shape: <response><pg_status>ok</pg_status>
    #   <pg_redirect_url>...</pg_redirect_url></response>
    # Re-check this parsing against a real response once you have access.
    #
    # Parse response.content (raw bytes), not response.text — the XML
    # prolog declares its own encoding (UTF-8), and letting ElementTree
    # read that directly avoids requests mis-guessing the charset and
    # mangling Cyrillic in pg_error_description/pg_description.
    root = ET.fromstring(response.content)
    status = root.findtext("pg_status")
    if status != "ok":
        description = root.findtext("pg_error_description") or root.findtext(
            "pg_description"
        )
        raise FreedomPayError(description or "FreedomPay init_payment failed")

    redirect_url = root.findtext("pg_redirect_url")
    if not redirect_url:
        raise FreedomPayError("FreedomPay response did not include pg_redirect_url")
    return redirect_url


def verify_callback_signature(params):
    """Verify the signature on an incoming result_url (webhook) callback."""
    if not is_configured():
        return False
    received_sig = params.get("pg_sig", "")
    expected_sig = _make_signature("result_url", params, settings.FREEDOMPAY_SECRET_KEY)
    return received_sig == expected_sig


def build_callback_ack(success, description, secret_key):
    """The XML acknowledgement FreedomPay expects back from result_url."""
    salt = _random_salt()
    ack_params = {
        "pg_status": "ok" if success else "error",
        "pg_description": description,
        "pg_salt": salt,
    }
    sig = _make_signature("result_url", ack_params, secret_key)
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<response>"
        f"<pg_status>{ack_params['pg_status']}</pg_status>"
        f"<pg_description>{ack_params['pg_description']}</pg_description>"
        f"<pg_salt>{salt}</pg_salt>"
        f"<pg_sig>{sig}</pg_sig>"
        "</response>"
    )
