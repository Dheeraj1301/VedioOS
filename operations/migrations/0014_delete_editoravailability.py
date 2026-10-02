from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("operations", "0013_support_requests")]

    operations = [migrations.DeleteModel(name="EditorAvailability")]
