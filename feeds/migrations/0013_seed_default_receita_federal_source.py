from django.db import migrations


DEFAULT_SOURCE_URL = 'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS'


def create_default_source(apps, schema_editor):
    Source = apps.get_model('feeds', 'Source')
    SourceCategory = apps.get_model('feeds', 'SourceCategory')

    category, _created = SourceCategory.objects.get_or_create(
        name='Federal',
        defaults={'order': 1},
    )

    Source.objects.get_or_create(
        url=DEFAULT_SOURCE_URL,
        defaults={
            'name': 'Receita Federal',
            'description': 'Fonte padrão de notícias da Receita Federal do Brasil.',
            'category': category,
            'active': True,
        },
    )


def delete_default_source(apps, schema_editor):
    Source = apps.get_model('feeds', 'Source')
    Source.objects.filter(url=DEFAULT_SOURCE_URL).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0012_create_news_item_follow_and_reminder_notification'),
    ]

    operations = [
        migrations.RunPython(create_default_source, delete_default_source),
    ]
