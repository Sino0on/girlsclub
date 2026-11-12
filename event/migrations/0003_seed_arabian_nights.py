from django.db import migrations

PROGRAM = [
    ("Oriental Dance", "Восточные танцы и яркие выступления, от которых невозможно отвести взгляд.", "img/nights/palace-dance.jpg"),
    ("Music & DJ", "Музыка, любимые хиты и танцы до самой глубокой ночи.", "img/nights/night-court.jpg"),
    ("Activities", "Тематические активности, игры и интерактивы — немного восточной магии в каждом.", "img/nights/tea.jpg"),
    ("Gifts & Surprises", "Подарки, сюрпризы и приятные неожиданности, спрятанные в этой ночи.", "img/nights/jewels.jpg"),
    ("Best Oriental Look", "Конкурс на лучший восточный образ — и главный приз, VIP-тур в Дубай.", "img/nights/veil-eyes.jpg"),
]


def seed(apps, schema_editor):
    from event.management.commands.seed_faq import DEFAULT_FAQ

    ProgramItem = apps.get_model("event", "ProgramItem")
    FAQItem = apps.get_model("event", "FAQItem")
    EventSettings = apps.get_model("event", "EventSettings")

    EventSettings.objects.get_or_create(pk=1)

    if not ProgramItem.objects.exists():
        for i, (title, desc, img) in enumerate(PROGRAM):
            ProgramItem.objects.create(title=title, description=desc, static_image=img, order=i)

    # Previous event's (FairyTale Picnic) questions: hide, don't delete.
    FAQItem.objects.update(is_active=False)
    for i, (q, a) in enumerate(DEFAULT_FAQ):
        FAQItem.objects.create(question=q, answer=a, order=i)


class Migration(migrations.Migration):
    dependencies = [("event", "0002_event_settings_program_partners")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
