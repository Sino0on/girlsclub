from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import migrations

LOGO = Path(settings.BASE_DIR) / "static" / "img" / "partners" / "next-station-light.png"


def add_partner(apps, schema_editor):
    Partner = apps.get_model("event", "Partner")
    if Partner.objects.filter(name="Next Station").exists() or not LOGO.exists():
        return
    partner = Partner(name="Next Station", order=0)
    with LOGO.open("rb") as fh:
        partner.logo.save("next-station.png", File(fh), save=False)
    partner.save()


def remove_partner(apps, schema_editor):
    apps.get_model("event", "Partner").objects.filter(name="Next Station").delete()


class Migration(migrations.Migration):
    dependencies = [("event", "0004_title_ru_1001")]
    operations = [migrations.RunPython(add_partner, remove_partner)]
