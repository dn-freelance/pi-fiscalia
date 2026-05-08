from django.db import migrations


def create_default_tags(apps, schema_editor):
    Tag = apps.get_model('feeds', 'Tag')
    default_tags = [
        {'name': 'NCM', 'color': 'blue'},
        {'name': 'ICMS', 'color': 'green'},
        {'name': 'PIS/COFINS', 'color': 'purple'},
        {'name': 'Simples Nacional', 'color': 'yellow'},
        {'name': 'CEST', 'color': 'orange'},
        {'name': 'Substituição Tributária', 'color': 'red'},
    ]

    for tag_data in default_tags:
        Tag.objects.get_or_create(name=tag_data['name'], defaults={'color': tag_data['color']})


def delete_default_tags(apps, schema_editor):
    Tag = apps.get_model('feeds', 'Tag')
    Tag.objects.filter(
        name__in=[
            'NCM',
            'ICMS',
            'PIS/COFINS',
            'Simples Nacional',
            'CEST',
            'Substituição Tributária',
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0004_create_tag'),
    ]

    operations = [
        migrations.RunPython(create_default_tags, delete_default_tags),
    ]
