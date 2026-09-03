"""
Finik payment gateway adapter (Web SDK, FINIK_QR).

Docs: https://www.finik.kg/documentation/web-sdk/

Every request to Finik's API needs a `signature` header: RSA-SHA256
over a canonical string, Base64-encoded. Finik's docs only show a
Node.js/TypeScript example (their `@mancho.devs/authorizer` npm
package) and mention Python/PHP packages exist without naming them —
none could be found on PyPI. So this is a byte-for-byte port of that
npm package's canonicalization + signing, verified by downloading the
real package (v2.12.8) from the npm registry, running its actual
`Signer.getData()` against a fixed input in Node, and diffing the
output against this module's `_canonical_string()` on the same input —
they matched exactly.

(The one worked webhook-signature example printed in Finik's own docs
does NOT actually verify — confirmed by running the real npm package
against it too, so that specific example is simply wrong on Finik's
end. Don't use it as a "does my code work" test; it fails against the
official library too.)

Two separate RSA keypairs are involved:
  - YOUR keypair: generate it yourself (see openssl commands in the
    docs), keep the private half secret (FINIK_PRIVATE_KEY below), and
    give Finik the public half when creating your WEB API key in their
    dashboard. You sign every outgoing Create Payment request with
    your private key; Finik verifies it with your public key.
  - FINIK's keypair: they sign every outgoing webhook with THEIR
    private key. You verify incoming webhooks with THEIR public key —
    published in the docs, hardcoded below (WEBHOOK_PUBLIC_KEYS) since
    it's not a secret, just different per beta/prod environment.
"""

import base64
import json
import time
from urllib.parse import unquote

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings
from django.urls import reverse

API_URLS = {
    "beta": "https://beta.api.acquiring.averspay.kg/v1/payment",
    "prod": "https://api.acquiring.averspay.kg/v1/payment",
}

# Published in Finik's docs (Справочник → Публичные ключи) — used to
# verify the signature on incoming webhooks. Not secret; safe to
# commit. Separate key per environment.
WEBHOOK_PUBLIC_KEYS = {
    "prod": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAuF/PUmhMPPidcMxhZBPb
BSGJoSphmCI+h6ru8fG8guAlcPMVlhs+ThTjw2LHABvciwtpj51ebJ4EqhlySPyT
hqSfXI6Jp5dPGJNDguxfocohaz98wvT+WAF86DEglZ8dEsfoumojFUy5sTOBdHEu
g94B4BbrJvjmBa1YIx9Azse4HFlWhzZoYPgyQpArhokeHOHIN2QFzJqeriANO+wV
aUMta2AhRVZHbfyJ36XPhGO6A5FYQWgjzkI65cxZs5LaNFmRx6pjnhjIeVKKgF99
4OoYCzhuR9QmWkPl7tL4Kd68qa/xHLz0Psnuhm0CStWOYUu3J7ZpzRK8GoEXRcr8
tQIDAQAB
-----END PUBLIC KEY-----""",
    "beta": """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAwlrlKz/8gLWd1ARWGA/8
o3a3Qy8G+hPifyqiPosiTY6nCHovANMIJXk6DH4qAqqZeLu8pLGxudkPbv8dSyG7
F9PZEAryMPzjoB/9P/F6g0W46K/FHDtwTM3YIVvstbEbL19m8yddv/xCT9JPPJTb
LsSTVZq5zCqvKzpupwlGS3Q3oPyLAYe+ZUn4Bx2J1WQrBu3b08fNaR3E8pAkCK27
JqFnP0eFfa817VCtyVKcFHb5ij/D0eUP519Qr/pgn+gsoG63W4pPHN/pKwQUUiAy
uLSHqL5S2yu1dffyMcMVi9E/Q2HCTcez5OvOllgOtkNYHSv9pnrMRuws3u87+hNT
ZwIDAQAB
-----END PUBLIC KEY-----""",
}


class FinikError(Exception):
    pass


def is_configured():
    return bool(
        settings.FINIK_API_KEY and settings.FINIK_PRIVATE_KEY and settings.FINIK_ACCOUNT_ID
    )


# --- canonicalization + signing (port of @mancho.devs/authorizer) ---


def _headers_data(host, api_headers):
    parts = [f"host:{host}"]
    for key in sorted(api_headers):
        parts.append(f"{key.lower()}:{api_headers[key]}")
    return "&".join(parts)


def _json_body(body):
    if not body:
        return ""
    # Top-level keys sorted alphabetically; nested objects keep
    # whatever order they were built in (matches Object.entries(...)
    # .sort().reduce() in the original — only sorts one level deep).
    sorted_body = {k: body[k] for k in sorted(body.keys())}
    return json.dumps(sorted_body, separators=(",", ":"), ensure_ascii=False)


def _canonical_string(method, path, host, api_headers, body):
    parts = [method.lower(), unquote(path), _headers_data(host, api_headers)]
    # The original algorithm also has a query-string component
    # (encodeURI(decodeURI(k))=encodeURI(decodeURI(v)) pairs, sorted),
    # omitted here since neither Create Payment nor the webhook uses
    # query params — add it if that ever changes.
    parts.append(_json_body(body))
    return "\n".join(parts)


def _sign(private_key_pem, method, path, host, api_headers, body):
    data = _canonical_string(method, path, host, api_headers, body)
    private_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None
    )
    signature = private_key.sign(data.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode("ascii")


def _verify(public_key_pem, signature_b64, method, path, host, api_headers, body):
    data = _canonical_string(method, path, host, api_headers, body)
    public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    try:
        public_key.verify(
            base64.b64decode(signature_b64),
            data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except (InvalidSignature, ValueError):
        return False


# --- create payment ---


def create_payment(order):
    """Return a URL to send the buyer to in order to pay via Finik.

    While FINIK_TEST_MODE is on (or real credentials aren't configured
    yet), sends buyers to the same local fake payment page used to
    test the (paused) FreedomPay flow — same order -> paid -> QR ->
    email pipeline, just without a real gateway involved.
    """
    if settings.FINIK_TEST_MODE or not is_configured():
        return f"{settings.SITE_URL}{reverse('tickets:fake_gateway', args=[order.qr_token])}"
    return _create_payment_via_api(order)


def _create_payment_via_api(order):
    """POST a signed Create Payment request to Finik. Returns the URL
    to send the buyer to (the Location header of Finik's 302).
    Raises FinikError on any failure."""
    api_url = API_URLS[settings.FINIK_MODE]
    host = api_url.split("/")[2]
    path = "/v1/payment"
    timestamp = str(int(time.time() * 1000))

    body = {
        "Amount": int(order.amount),
        "CardType": "FINIK_QR",
        "PaymentId": str(order.qr_token),
        "RedirectUrl": f"{settings.SITE_URL}{reverse('tickets:finik_return', args=[order.qr_token])}",
        "Data": {
            "accountId": settings.FINIK_ACCOUNT_ID,
            "name_en": settings.FINIK_QR_NAME,
            "webhookUrl": f"{settings.SITE_URL}{reverse('tickets:finik_webhook')}",
            "description": f"Билет FairyTale Picnic — {order.full_name}",
            "Lang": "ru",
        },
    }

    api_headers = {"x-api-key": settings.FINIK_API_KEY, "x-api-timestamp": timestamp}
    signature = _sign(settings.FINIK_PRIVATE_KEY, "POST", path, host, api_headers, body)

    try:
        response = requests.post(
            api_url,
            json=body,
            headers={
                "content-type": "application/json",
                "x-api-key": settings.FINIK_API_KEY,
                "x-api-timestamp": timestamp,
                "signature": signature,
            },
            allow_redirects=False,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise FinikError(f"Не удалось связаться с Finik: {exc}") from exc

    if response.status_code == 302:
        location = response.headers.get("Location")
        if not location:
            raise FinikError("Finik ответил 302 без заголовка Location")
        return location

    try:
        payload = response.json()
        message = payload.get("ErrorMessage") or payload.get("errorMessage") or response.text
    except ValueError:
        message = response.text
    raise FinikError(f"Finik вернул {response.status_code}: {message}")


# --- webhook verification ---


def verify_webhook(request, payload):
    """Verify an incoming webhook's `signature` header against Finik's
    published public key for the configured environment. `payload` is
    the already-json.loads()'d request body (parsed once by the
    caller, reused here rather than re-reading request.body)."""
    public_key = WEBHOOK_PUBLIC_KEYS[settings.FINIK_MODE]
    signature = request.headers.get("signature", "")
    if not signature:
        return False

    host = request.headers.get("host") or request.get_host()
    api_headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower().startswith("x-api-")
    }
    return _verify(public_key, signature, "POST", request.path, host, api_headers, payload)
