from django.db import migrations

RENAMES = {
    "Oriental Dance": "Восточные танцы",
    "Music & DJ": "Музыка и DJ",
    "Activities": "Игры и интерактивы",
    "Gifts & Surprises": "Подарки и сюрпризы",
    "Best Oriental Look": "Конкурс образов",
}


def to_ru(apps, schema_editor):
    ProgramItem = apps.get_model("event", "ProgramItem")
    for en, ru in RENAMES.items():
        ProgramItem.objects.filter(title=en).update(title=ru)


def to_en(apps, schema_editor):
    ProgramItem = apps.get_model("event", "ProgramItem")
    for en, ru in RENAMES.items():
        ProgramItem.objects.filter(title=ru).update(title=en)


class Migration(migrations.Migration):
    dependencies = [("event", "0005_partner_next_station")]
    operations = [migrations.RunPython(to_ru, to_en)]
