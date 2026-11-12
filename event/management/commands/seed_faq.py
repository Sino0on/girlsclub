from django.core.management.base import BaseCommand

from event.models import FAQItem

DEFAULT_FAQ = [
    (
        "Когда состоится мероприятие?",
        "29 ноября 2026 года. Запишите эту дату — ночь будет особенной ✨",
    ),
    (
        "Где будет проходить мероприятие?",
        "В ресторане «Шахерезада».",
    ),
    (
        "Во сколько начало?",
        "Сбор гостей начинается в 19:00, основная программа — в 20:00.",
    ),
    (
        "Сколько стоит билет?",
        "До 21 ноября стоимость билета — 1300 сом.\n"
        "После 21 ноября — 1500 сом.\n"
        "\n"
        "Количество мест ограничено.",
    ),
    (
        "Есть ли дополнительный депозит?",
        "Да, депозит составляет 2000 сом и оплачивается непосредственно на месте, "
        "в заведении. Он оплачивается отдельно от стоимости входного билета.",
    ),
    (
        "Как приобрести билет?",
        "Нажмите кнопку «Купить билет» на сайте и следуйте инструкции — "
        "QR-код билета придёт вам на почту.",
    ),
    (
        "Есть ли дресс-код?",
        "Да! Тематика вечера — Arabian Nights. Подробные референсы и "
        "рекомендации ждут вас в нашем Instagram.",
    ),
    (
        "Будет ли конкурс на лучший образ?",
        "Да! Обладательницу лучшего восточного образа ждёт главный приз — "
        "VIP-тур в Дубай.",
    ),
    (
        "Можно ли прийти с подругами?",
        "Конечно! Мы только за то, чтобы вы разделили эту ночь с близкими подругами.",
    ),
]


class Command(BaseCommand):
    """Replace all FAQ entries with the current DEFAULT_FAQ list above.

    Not run automatically on deploy — call it yourself whenever
    DEFAULT_FAQ changes and you want the live site to match:
        python manage.py seed_faq
    This deletes existing FAQItem rows first, so any edits made directly
    in the admin will be overwritten — that's the point of "seed_faq",
    edit DEFAULT_FAQ instead if you want the change to stick.
    """

    help = "Replace all FAQ entries with the current DEFAULT_FAQ list."

    def handle(self, *args, **options):
        FAQItem.objects.all().delete()
        for order, (question, answer) in enumerate(DEFAULT_FAQ):
            FAQItem.objects.create(question=question, answer=answer, order=order)
        self.stdout.write(self.style.SUCCESS(f"Replaced FAQ with {len(DEFAULT_FAQ)} entries."))
