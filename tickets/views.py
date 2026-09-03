import json

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import finik, freedompay, services
from .forms import OrderForm, ReceiptUploadForm
from .models import Order, PaymentInstructions


def buy(request):
    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.amount = order.quantity * settings.TICKET_PRICE_KGS
            order.payment_method = Order.METHOD_FINIK
            order.status = Order.STATUS_PENDING
            order.save()
            try:
                redirect_url = finik.create_payment(order)
            except finik.FinikError as exc:
                messages.error(request, f"Не удалось создать платёж: {exc}")
                return render(request, "tickets/buy.html", {"form": form})
            return redirect(redirect_url)
    else:
        form = OrderForm()
    return render(request, "tickets/buy.html", {"form": form})


def upload_receipt(request, token):
    """Step 2: show the bank-transfer QR + amount, collect the buyer's
    receipt screenshot/file. The ticket is issued the moment this is
    submitted — a moderator can only void it afterwards, not block it."""
    order = get_object_or_404(Order, qr_token=token)

    if order.status != Order.STATUS_AWAITING_RECEIPT:
        # Already submitted (or from another flow) — just show the ticket.
        return render(request, "tickets/success.html", {"order": order})

    if request.method == "POST":
        form = ReceiptUploadForm(request.POST, request.FILES, instance=order)
        if form.is_valid():
            form.save()
            services.issue_ticket(order)
            return render(request, "tickets/success.html", {"order": order})
    else:
        form = ReceiptUploadForm(instance=order)

    instructions = PaymentInstructions.objects.filter(is_active=True).first()
    return render(
        request,
        "tickets/upload_receipt.html",
        {"form": form, "order": order, "instructions": instructions},
    )


@staff_member_required
def verify(request, token):
    """Door-staff view: open the QR's link directly (e.g. via the phone's
    own camera app) to see the ticket and mark it used by hand. The
    camera *scanner* page (below) is the faster way to do this all day —
    this page still works standalone as a fallback / for spot checks."""
    order = get_object_or_404(Order, qr_token=token)

    if request.method == "POST":
        services.try_check_in(order)
        return redirect("tickets:verify", token=order.qr_token)

    return render(request, "tickets/verify.html", {"order": order})


@staff_member_required
def scanner(request):
    """Camera-based scanning UI: point a phone's browser here (no app
    install), scan each guest's QR in turn, get an instant green/red."""
    return render(request, "tickets/scanner.html")


@staff_member_required
@require_POST
def scan_api(request, token):
    """JSON endpoint the scanner page calls after decoding each QR.
    Same green/red decision as `verify`, just machine-readable."""
    order = Order.objects.filter(qr_token=token).first()
    if not order:
        return JsonResponse({"ok": False, "reason": "not_found", "message": "Билет не найден"})

    ok, reason, message = services.try_check_in(order)
    return JsonResponse(
        {
            "ok": ok,
            "reason": reason,
            "message": message,
            "full_name": order.full_name,
            "quantity": order.quantity,
        }
    )


# =====================================================================
# FreedomPay flow — paused for now, kept working in case it comes back.
# Nothing above calls into any of this.
# =====================================================================


def _find_order(request):
    """FreedomPay identifies the order via pg_order_id, sent either as a
    POST body param (server-to-server callbacks) or a GET query param
    (browser redirects) — check whichever is present."""
    order_id = request.POST.get("pg_order_id") or request.GET.get("pg_order_id")
    return Order.objects.filter(qr_token=order_id).first()


def _xml_ack(success, description, script_name):
    body = freedompay.build_ack(
        success, description, settings.FREEDOMPAY_SECRET_KEY, script_name
    )
    return HttpResponse(body, content_type="application/xml")


@csrf_exempt
@require_POST
def payment_check(request):
    """Called by FreedomPay before charging, to confirm the order is
    real and still payable — no money has moved yet at this point."""
    params = request.POST.dict()

    if not freedompay.verify_incoming_signature(params, freedompay.CHECK_SCRIPT_NAME):
        return _xml_ack(False, "Invalid signature", freedompay.CHECK_SCRIPT_NAME)

    order = _find_order(request)
    if not order:
        return _xml_ack(False, "Unknown order", freedompay.CHECK_SCRIPT_NAME)
    if order.status != Order.STATUS_PENDING:
        return _xml_ack(False, "Order is not payable anymore", freedompay.CHECK_SCRIPT_NAME)

    return _xml_ack(True, "Order is payable", freedompay.CHECK_SCRIPT_NAME)


@csrf_exempt
@require_POST
def payment_callback(request):
    """Server-to-server webhook FreedomPay calls once a payment finishes.
    This — not the success/fail redirect — is the source of truth for
    whether an order actually got paid."""
    params = request.POST.dict()

    if not freedompay.verify_incoming_signature(params, freedompay.RESULT_SCRIPT_NAME):
        return _xml_ack(False, "Invalid signature", freedompay.RESULT_SCRIPT_NAME)

    order = _find_order(request)
    if not order:
        return _xml_ack(False, "Unknown order", freedompay.RESULT_SCRIPT_NAME)

    pg_result = params.get("pg_result")
    if pg_result == "1":
        services.mark_order_paid(order, payment_id=params.get("pg_payment_id", ""))
        return _xml_ack(True, "Payment accepted", freedompay.RESULT_SCRIPT_NAME)
    if pg_result == "2":
        # Incomplete — FreedomPay may still call back again with a
        # final result later, so don't mark the order failed yet.
        return _xml_ack(True, "Acknowledged, awaiting final result", freedompay.RESULT_SCRIPT_NAME)
    services.mark_order_failed(order)
    return _xml_ack(True, "Payment failure acknowledged", freedompay.RESULT_SCRIPT_NAME)


def payment_success(request):
    order = _find_order(request)
    if not order:
        messages.error(request, "Не удалось найти заказ.")
        return redirect("event:home")
    return render(request, "tickets/success.html", {"order": order})


def payment_fail(request):
    order = _find_order(request)
    return render(request, "tickets/fail.html", {"order": order})


def fake_gateway(request, token):
    """Stand-in for FreedomPay's hosted payment page.

    Only reachable while FREEDOMPAY_TEST_MODE is on or real credentials
    aren't configured yet — lets the full purchase flow be tested end
    to end without a live merchant account.
    """
    order = get_object_or_404(Order, qr_token=token)

    if request.method == "POST":
        if request.POST.get("action") == "pay":
            services.mark_order_paid(
                order, payment_id="TEST-" + str(order.qr_token)[:8]
            )
            target = reverse("tickets:payment_success")
        else:
            services.mark_order_failed(order)
            target = reverse("tickets:payment_fail")
        return redirect(f"{target}?pg_order_id={order.qr_token}")

    return render(request, "tickets/fake_gateway.html", {"order": order})


# =====================================================================
# Finik flow — the active payment method.
# =====================================================================


def finik_return(request, token):
    """Where Finik redirects the buyer's browser after they pay.
    Just a landing page — the webhook below (not this) is the source
    of truth for whether the order is actually paid, so this may
    render slightly before that webhook has landed."""
    order = get_object_or_404(Order, qr_token=token)
    return render(request, "tickets/success.html", {"order": order})


@csrf_exempt
@require_POST
def finik_webhook(request):
    """Server-to-server notification Finik sends once a payment
    succeeds (per their docs, only ever sent on success — there's no
    webhook call for a failed/abandoned payment)."""
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    if not finik.verify_webhook(request, payload):
        return HttpResponse(status=401)

    status = str(payload.get("status", "")).lower()
    if status not in ("success", "succeeded"):
        # Finik's docs say this shouldn't happen, but don't fail the
        # request over it — just don't act on it either.
        return HttpResponse(status=200)

    payment_id = (payload.get("fields") or {}).get("paymentId")
    order = Order.objects.filter(qr_token=payment_id).first()
    if not order:
        return HttpResponse(status=200)

    services.mark_order_paid(
        order,
        payment_id=payload.get("transactionId", ""),
        payment_method=Order.METHOD_FINIK,
    )
    return HttpResponse(status=200)
