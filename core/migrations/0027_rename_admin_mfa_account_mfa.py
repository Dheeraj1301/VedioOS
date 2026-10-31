import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Rename keeps every row and the table's row-level security setting."""

    dependencies = [
        ("core", "0026_admin_mfa"),
    ]

    operations = [
        migrations.RenameModel(old_name="AdminMFA", new_name="AccountMFA"),
        migrations.AlterModelTable(name="accountmfa", table="account_mfa"),
        migrations.AlterField(
            model_name="accountmfa",
            name="user",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="mfa",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
