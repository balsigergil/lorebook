from django.db import migrations

DEFAULTS = [("fr", "Français"), ("de", "Deutsch"), ("it", "Italiano"), ("en", "English")]


def create_languages(apps, schema_editor):
    Language = apps.get_model("i18n", "Language")
    if Language.objects.exists():
        return
    for position, (code, name) in enumerate(DEFAULTS):
        Language.objects.create(code=code, name=name, position=position, enabled=True)


class Migration(migrations.Migration):
    dependencies = [("i18n", "0001_initial")]

    operations = [migrations.RunPython(create_languages, migrations.RunPython.noop)]
