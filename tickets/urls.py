from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("buy/", views.buy, name="buy"),
    # These three are static — paste them as-is into the FreedomPay
    # merchant cabinet (Настройки → Магазины → CHECK URL / RESULT URL /
    # SUCCESS URL). FreedomPay appends pg_order_id (and friends) as
    # request params, so no per-order token in the path is needed here.
    path("payment/check/", views.payment_check, name="payment_check"),
    path("payment/callback/", views.payment_callback, name="payment_callback"),
    path("payment/success/", views.payment_success, name="payment_success"),
    path("payment/fail/", views.payment_fail, name="payment_fail"),
    path("gateway/<uuid:token>/", views.fake_gateway, name="fake_gateway"),
    path("verify/<uuid:token>/", views.verify, name="verify"),
]
