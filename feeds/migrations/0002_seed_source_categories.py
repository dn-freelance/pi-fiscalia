from django.db import migrations


SOURCE_CATEGORIES = (
    ('Federal', 1),
    ('Estadual', 2),
    ('Municipal', 3),
)


def create_source_categories(apps, schema_editor):
    SourceCategory = apps.get_model('feeds', 'SourceCategory')

    for name, order in SOURCE_CATEGORIES:
        SourceCategory.objects.get_or_create(
            name=name,
            defaults={'order': order},
        )


def delete_source_categories(apps, schema_editor):
    SourceCategory = apps.get_model('feeds', 'SourceCategory')
    SourceCategory.objects.filter(
        name__in=[name for name, _order in SOURCE_CATEGORIES],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_source_categories, delete_source_categories),
    ]
