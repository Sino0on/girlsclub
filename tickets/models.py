import uuid

from django.conf import settings
from django.db import models


class Order(models.Model):
    """One ticket purchase.

    Created when someone submits the checkout form (status=pending),
    then flipped to paid/failed once FreedomPay confirms the payment
    (or, in test mode, once the fake gateway page is used).
    """

    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает оплаты"),
        (STATUS_PAID, "Оплачен"),
        (STATUS_FAILED, "Не оплачен / отменён"),
    ]

    full_name = models.CharField("ФИО", max_length=200)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=32)
    rules_agreed = models.BooleanField("Согласие с правилами", default=False)

    amount = models.DecimalField("Сумма, сом", max_digits=10, decimal_places=2)
    status = models.CharField(
        "Статус", max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    qr_token = models.UUIDField(
        "QR-токен", default=uuid.uuid4, editable=False, unique=True
    )
    qr_image = models.ImageField(
        "QR-код", upload_to="qrcodes/", blank=True, null=True
    )

    payment_id = models.CharField(
        "ID платежа FreedomPay", max_length=100, blank=True
    )
    email_sent_at = models.DateTimeField("Письмо отправлено", blank=True, null=True)

    checked_in_at = models.DateTimeField("Отмечен на входе", blank=True, null=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    paid_at = models.DateTimeField("Оплачен", blank=True, null=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.get_status_display()}"

    @property
    def is_paid(self):
        return self.status == self.STATUS_PAID

    @property
    def is_checked_in(self):
        return self.checked_in_at is not None

    def get_verify_url(self):
        return f"{settings.SITE_URL}/tickets/verify/{self.qr_token}/"
