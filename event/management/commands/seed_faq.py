from django.core.management.base import BaseCommand

from event.models import FAQItem

DEFAULT_FAQ = [
    (
        "Что входит в билет?",
        "Билет даёт доступ на всю территорию Fairy Tale Picnic: сад, зоны "
        "отдыха, фотозоны и часть активностей. Актуальный список уточняйте "
        "у организаторов ближе к дате.",
    ),
    (
        "Можно ли прийти без определённого дресс-кода?",
        "Дресс-код — это пожелание, а не обязательное условие входа. Но мы "
        "будем рады, если вы поддержите нежную палитру Strawberry Matcha.",
    ),
    (
        "Что делать, если я не получил(а) билет на почту?",
        "Проверьте папку «Спам». Если письма всё равно нет — напишите "
        "организаторам, указав ФИО и номер телефона, которые вы вводили при "
        "покупке.",
    ),
    (
        "Билет можно передать другому человеку?",
        "Билет именной. Если вы не сможете прийти и хотите передать билет — "
        "заранее согласуйте это с организаторами.",
    ),
    (
        "Что взять с собой?",
        "Хорошее настроение, сказочный наряд и этот самый QR-код билета — "
        "на входе его нужно будет показать.",
    ),
]


class Command(BaseCommand):
    """Seed a handful of example FAQ entries — but only into a completely
    empty table, so it never fights with edits made later in the admin."""

    help = "Seed example FAQ entries if the FAQ table is empty."

    def handle(self, *args, **options):
        if FAQItem.objects.exists():
            self.stdout.write("FAQ already has entries — skipping seed.")
            return

        for order, (question, answer) in enumerate(DEFAULT_FAQ):
            FAQItem.objects.create(question=question, answer=answer, order=order)

        self.stdout.write(self.style.SUCCESS(f"Seeded {len(DEFAULT_FAQ)} FAQ entries."))
