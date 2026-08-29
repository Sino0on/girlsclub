from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
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


@csrf_exempt
@require_POST
def payment_callback(request):
    """Server-to-server webhook FreedomPay calls once a payment finishes."""
    params = request.POST.dict()
    if not freedompay.verify_callback_signature(params):
        return HttpResponse("signature mismatch", status=400)

    order_token = params.get("pg_order_id")
    order = Order.objects.filter(qr_token=order_token).first()
    if not order:
        return HttpResponse("unknown order", status=404)

    if params.get("pg_result") == "1":
        services.mark_order_paid(order, payment_id=params.get("pg_payment_id", ""))
        ack = freedompay.build_callback_ack(
            True, "Payment accepted", settings.FREEDOMPAY_SECRET_KEY
        )
    else:
        services.mark_order_failed(order)
        ack = freedompay.build_callback_ack(
            True, "Payment failure acknowledged", settings.FREEDOMPAY_SECRET_KEY
        )

    return HttpResponse(ack, content_type="application/xml")


def payment_success(request, token):
    order = get_object_or_404(Order, qr_token=token)
    return render(request, "tickets/success.html", {"order": order})


def payment_fail(request, token):
    order = get_object_or_404(Order, qr_token=token)
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
            return redirect("tickets:payment_success", token=order.qr_token)
        services.mark_order_failed(order)
        return redirect("tickets:payment_fail", token=order.qr_token)

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
