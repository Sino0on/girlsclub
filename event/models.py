import datetime

from django.db import models
from django.utils import timezone

# 21 Nov 2026 is the last early-bird day: the price switches at midnight
# Bishkek time (UTC+6) going into 22 Nov.
DEFAULT_PRICE_SWITCH_AT = datetime.datetime(2026, 11, 21, 18, 0, tzinfo=datetime.timezone.utc)


class EventSettings(models.Model):
    """Singleton (always pk=1) with everything the landing page shows that
    organisers may want to change without a developer: date, venue,
    times, ticket prices and the automatic price switch, deposit, links.

    The ticket price used at checkout comes from here too (see
    current_price), so the site and the actual charge never disagree.
    """

    title = models.CharField("Название", max_length=120, default="A Thousand and One Nights")
    title_ru = models.CharField("Название по-русски", max_length=120, default="Тысяча и одна ночь")

    event_date = models.DateField("Дата мероприятия", default=datetime.date(2026, 11, 29))
    gathering_time = models.TimeField("Сбор гостей", default=datetime.time(19, 0))
    program_time = models.TimeField("Начало программы", default=datetime.time(20, 0))
    venue = models.CharField("Место", max_length=200, default="Ресторан «Шахерезада»")
    venue_map_url = models.URLField(
        "Ссылка на карту", blank=True, help_text="2ГИС / Google Maps. Пусто — ссылка не показывается."
    )

    price_early = models.PositiveIntegerField("Цена до смены тарифа, сом", default=1300)
    price_late = models.PositiveIntegerField("Цена после смены тарифа, сом", default=1500)
    price_switch_at = models.DateTimeField(
        "Когда цена повышается",
        default=DEFAULT_PRICE_SWITCH_AT,
        help_text=(
            "С этого момента сайт и оформление заказа автоматически берут "
            "вторую цену. По умолчанию — 22 ноября 00:00 (т.е. 21 ноября "
            "ещё действует ранняя цена)."
        ),
    )
    seats_limited = models.BooleanField("Показывать «количество мест ограничено»", default=True)
    deposit = models.PositiveIntegerField(
        "Депозит на месте, сом", default=2000, help_text="0 — блок о депозите не показывается."
    )

    buy_url = models.URLField(
        "Внешняя ссылка на покупку",
        blank=True,
        help_text=(
            "Обычно пусто — все кнопки «Купить билет» ведут на оформление "
            "заказа на этом сайте. Заполните, только если продажи переехали "
            "на внешний сервис."
        ),
    )
    instagram_url = models.URLField("Instagram Girls Club", blank=True)
    dresscode_url = models.URLField(
        "Ссылка на Dress Code",
        blank=True,
        help_text="Публикация в Instagram с референсами образов. Пусто — ведёт на Instagram Girls Club.",
    )

    prize_image = models.ImageField(
        "Фото для блока VIP-тура",
        upload_to="site/",
        blank=True,
        help_text="Эффектная фотография Дубая. Пока пусто — показывается золотой силуэт города.",
    )
    prize_terms = models.TextField(
        "Условия VIP-тура",
        blank=True,
        help_text="Мелким текстом под блоком приза. Согласуйте с партнёром перед публикацией.",
    )

    class Meta:
        verbose_name = "Настройки мероприятия"
        verbose_name_plural = "Настройки мероприятия"

    def __str__(self):
        return "Настройки мероприятия"

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    # --- pricing ---

    def is_early(self, now=None):
        return (now or timezone.now()) < self.price_switch_at

    def current_price(self, now=None):
        return self.price_early if self.is_early(now) else self.price_late

    @property
    def early_until(self):
        """Last calendar day (local time) the early price applies."""
        return timezone.localtime(self.price_switch_at - datetime.timedelta(minutes=1)).date()

    @property
    def event_start(self):
        return timezone.make_aware(datetime.datetime.combine(self.event_date, self.program_time))

    @property
    def dresscode_link(self):
        return self.dresscode_url or self.instagram_url


class ProgramItem(models.Model):
    """One card in «Что тебя ждёт?»."""

    title = models.CharField("Название", max_length=80, help_text="Например: Oriental Dance")
    description = models.CharField("Описание", max_length=200)
    image = models.ImageField("Фото", upload_to="program/", blank=True)
    static_image = models.CharField(
        "Фото по умолчанию",
        max_length=200,
        blank=True,
        help_text="Встроенная картинка сайта — используется, пока не загружено своё фото.",
    )
    order = models.PositiveIntegerField("Порядок", default=0, help_text="Меньше — раньше")
    is_active = models.BooleanField("Показывать на сайте", default=True)

    class Meta:
        verbose_name = "Пункт программы"
        verbose_name_plural = "Программа («Что тебя ждёт?»)"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title


class Partner(models.Model):
    name = models.CharField("Название", max_length=120)
    logo = models.ImageField(
        "Логотип",
        upload_to="partners/",
        help_text="Лучше PNG/SVG на прозрачном фоне — на сайте все логотипы приводятся к одному размеру и цвету.",
    )
    url = models.URLField("Ссылка", blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)
    is_active = models.BooleanField("Показывать на сайте", default=True)

    class Meta:
        verbose_name = "Партнёр"
        verbose_name_plural = "Партнёры"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class FAQItem(models.Model):
    """A single question/answer pair for the FAQ section.

    Manageable from the Django admin — order controls display position.
    """

    question = models.CharField("Вопрос", max_length=300)
    answer = models.TextField("Ответ")
    order = models.PositiveIntegerField(
        "Порядок", default=0, help_text="Меньше — выше на странице"
    )
    is_active = models.BooleanField("Показывать на сайте", default=True)

    class Meta:
        verbose_name = "Вопрос FAQ"
        verbose_name_plural = "FAQ"
        ordering = ["order", "id"]

    def __str__(self):
        return self.question
