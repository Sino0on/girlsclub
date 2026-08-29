from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("buy/", views.buy, name="buy"),
    path("payment/callback/", views.payment_callback, name="payment_callback"),
    path("payment/success/<uuid:token>/", views.payment_success, name="payment_success"),
    path("payment/fail/<uuid:token>/", views.payment_fail, name="payment_fail"),
    path("gateway/<uuid:token>/", views.fake_gateway, name="fake_gateway"),
    path("verify/<uuid:token>/", views.verify, name="verify"),
]
