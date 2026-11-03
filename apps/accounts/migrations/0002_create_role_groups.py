from django.db import migrations

# Mirrors apps.accounts.roles.ALL_ROLES; migrations must not import app code.
ROLE_NAMES = ("PROJECT_MANAGER", "PROJECT_MEMBER", "SALES_VIEWER", "FINANCE_VIEWER", "SYSTEM_ADMIN")


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for name in ROLE_NAMES:
        Group.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(create_groups, migrations.RunPython.noop)]
