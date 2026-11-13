from django.db import migrations


def seed(apps, schema_editor):
    PromoCode = apps.get_model("tickets", "PromoCode")
    PromoCode.objects.get_or_create(
        code="Isabell15",
        defaults={"discount_percent": 15, "is_active": True},
    )


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0007_promo_codes"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
