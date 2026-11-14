from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import migrations

NAME = "Zelan by Bearbish"
LOGO = Path(settings.BASE_DIR) / "static" / "img" / "partners" / "zelan.png"


def add_partner(apps, schema_editor):
    Partner = apps.get_model("event", "Partner")
    if Partner.objects.filter(name=NAME).exists() or not LOGO.exists():
        return
    partner = Partner(name=NAME, order=1)
    with LOGO.open("rb") as fh:
        partner.logo.save("zelan.png", File(fh), save=False)
    partner.save()


def remove_partner(apps, schema_editor):
    apps.get_model("event", "Partner").objects.filter(name=NAME).delete()


class Migration(migrations.Migration):
    dependencies = [("event", "0006_program_titles_ru")]
    operations = [migrations.RunPython(add_partner, remove_partner)]
