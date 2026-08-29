from django.db import models


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
