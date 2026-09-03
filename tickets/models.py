import uuid

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


def receipt_upload_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"receipts/{uuid.uuid4()}.{ext}"


class Order(models.Model):
    """One ticket purchase.

    Current flow (manual bank transfer): created with status
    "awaiting_receipt" when the buyer submits the checkout form, moves
    to "pending_review" the moment they upload a transfer receipt — the
    ticket/QR is issued immediately at that point, no need to wait for
    a moderator. A moderator then just confirms or rejects it in the
    Telegram group; rejecting voids the ticket and emails the buyer.

    STATUS_PENDING / STATUS_PAID / STATUS_FAILED are shared by any
    automated gateway (FreedomPay, Finik) — generic "sent to gateway /
    gateway confirmed paid / gateway confirmed failed" states, not
    tied to one provider. `payment_method` records which one actually
    handled a given order.
    """

    METHOD_MANUAL = "manual"
    METHOD_FREEDOMPAY = "freedompay"
    METHOD_FINIK = "finik"
    METHOD_CHOICES = [
        (METHOD_MANUAL, "Ручной перевод"),
        (METHOD_FREEDOMPAY, "FreedomPay"),
        (METHOD_FINIK, "Finik"),
    ]

    # --- Automated gateway flow (FreedomPay paused, Finik active) ---
    STATUS_PENDING = "pending"
    STATUS_PAID = "paid"
    STATUS_FAILED = "failed"

    # --- Manual bank-transfer flow ---
    STATUS_AWAITING_RECEIPT = "awaiting_receipt"
    STATUS_PENDING_REVIEW = "pending_review"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Ожидает оплаты"),
        (STATUS_PAID, "Оплачен"),
        (STATUS_FAILED, "Не оплачен / отменён"),
        (STATUS_AWAITING_RECEIPT, "Ожидает чек оплаты"),
        (STATUS_PENDING_REVIEW, "Билет выдан, ждёт проверки модератором"),
        (STATUS_APPROVED, "Подтверждён модератором"),
        (STATUS_REJECTED, "Отклонён, билет аннулирован"),
    ]

    full_name = models.CharField("ФИО", max_length=200)
    email = models.EmailField("Email")
    phone = models.CharField("Телефон", max_length=32)
    rules_agreed = models.BooleanField("Согласие с правилами", default=False)

    quantity = models.PositiveIntegerField("Количество билетов", default=1)
    amount = models.DecimalField("Сумма, сом", max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        "Способ оплаты",
        max_length=16,
        choices=METHOD_CHOICES,
        default=METHOD_MANUAL,
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_AWAITING_RECEIPT,
    )

    receipt = models.FileField(
        "Чек об оплате",
        upload_to=receipt_upload_path,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(["jpg", "jpeg", "png", "heic", "pdf", "webp"])
        ],
    )

    qr_token = models.UUIDField(
        "QR-токен", default=uuid.uuid4, editable=False, unique=True
    )
    qr_image = models.ImageField(
        "QR-код", upload_to="qrcodes/", blank=True, null=True
    )

    payment_id = models.CharField(
        "ID платежа у платёжного шлюза", max_length=100, blank=True
    )

    telegram_chat_id = models.CharField(
        "Telegram chat ID", max_length=32, blank=True
    )
    telegram_message_id = models.BigIntegerField(
        "Telegram message ID", blank=True, null=True
    )

    email_sent_at = models.DateTimeField("Письмо с билетом отправлено", blank=True, null=True)
    rejection_email_sent_at = models.DateTimeField(
        "Письмо об аннулировании отправлено", blank=True, null=True
    )
    checked_in_at = models.DateTimeField("Отмечен на входе", blank=True, null=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    submitted_at = models.DateTimeField("Чек загружен", blank=True, null=True)
    decided_at = models.DateTimeField("Решение модератора", blank=True, null=True)
    paid_at = models.DateTimeField("Оплачен (через шлюз)", blank=True, null=True)

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} — {self.get_status_display()}"

    # --- Automated gateway flow helpers (FreedomPay paused, Finik active) ---
    @property
    def is_paid(self):
        return self.status == self.STATUS_PAID

    # --- Manual bank-transfer flow helpers ---
    @property
    def is_valid_ticket(self):
        """Ticket has been issued and hasn't been voided by a moderator."""
        return self.status in (
            self.STATUS_PAID,
            self.STATUS_PENDING_REVIEW,
            self.STATUS_APPROVED,
        )

    @property
    def is_rejected(self):
        return self.status in (self.STATUS_REJECTED, self.STATUS_FAILED)

    @property
    def is_checked_in(self):
        return self.checked_in_at is not None

    def get_verify_url(self):
        return f"{settings.SITE_URL}/tickets/verify/{self.qr_token}/"


class PaymentInstructions(models.Model):
    """Bank-transfer QR + instructions shown on the "upload your receipt"
    page. Admin-managed; the most recently updated active row is used."""

    qr_image = models.ImageField("QR-код для перевода", upload_to="payment_qr/")
    note = models.TextField(
        "Реквизиты / пояснение",
        blank=True,
        help_text="Например: банк, получатель, номер счёта — что покупатель увидит рядом с QR",
    )
    is_active = models.BooleanField("Активна", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Реквизиты для оплаты"
        verbose_name_plural = "Реквизиты для оплаты"

    def __str__(self):
        return f"Реквизиты ({'активны' if self.is_active else 'неактивны'})"


class PaymentSettings(models.Model):
    """Singleton — one row, always pk=1. `active_method` decides which
    gateway the "Купить билет" button on the site actually uses.
    Change it here to switch FreedomPay <-> Finik <-> manual transfer
    without touching code, .env, or redeploying."""

    active_method = models.CharField(
        "Активный способ оплаты",
        max_length=16,
        choices=Order.METHOD_CHOICES,
        default=Order.METHOD_FINIK,
        help_text=(
            "Каким способом оплачивается билет при нажатии «Купить билет» "
            "на сайте. FreedomPay/Finik используют тестовый режим, пока не "
            "заданы реальные ключи в .env (см. FREEDOMPAY_TEST_MODE / "
            "FINIK_TEST_MODE)."
        ),
    )

    class Meta:
        verbose_name = "Настройки оплаты"
        verbose_name_plural = "Настройки оплаты"

    def __str__(self):
        return f"Активный способ оплаты: {self.get_active_method_display()}"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # singleton — never actually delete it

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
