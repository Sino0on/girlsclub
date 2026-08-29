from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import freedompay, services
from .forms import OrderForm
from .models import Order


def buy(request):
    if request.method == "POST":
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.amount = settings.TICKET_PRICE_KGS
            order.save()
            try:
                redirect_url = freedompay.create_payment(order)
            except freedompay.FreedomPayError as exc:
                messages.error(request, f"Не удалось создать платёж: {exc}")
                return render(request, "tickets/buy.html", {"form": form})
            return redirect(redirect_url)
    else:
        form = OrderForm()
    return render(request, "tickets/buy.html", {"form": form})


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


@staff_member_required
def verify(request, token):
    """Door-staff view: scan the QR, see the ticket, mark it used."""
    order = get_object_or_404(Order, qr_token=token)

    if request.method == "POST" and order.is_paid and not order.is_checked_in:
        order.checked_in_at = timezone.now()
        order.save(update_fields=["checked_in_at"])
        return redirect("tickets:verify", token=order.qr_token)

    return render(request, "tickets/verify.html", {"order": order})
