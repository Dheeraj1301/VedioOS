from django.db import migrations


def seed_levels(apps, schema_editor):
    Proficiency = apps.get_model("operations", "EditorProficiency")
    Pointer = apps.get_model("operations", "RoundRobinState")
    for level in ["beginner", "intermediate", "advanced"]:
        proficiency, _ = Proficiency.objects.get_or_create(level=level)
        Pointer.objects.get_or_create(proficiency=proficiency)


class Migration(migrations.Migration):
    dependencies = [("operations", "0001_initial")]
    operations = [migrations.RunPython(seed_levels, migrations.RunPython.noop)]
