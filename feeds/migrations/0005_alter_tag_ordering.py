# Generated migration: alter Tag ordering from alphabetical to reverse creation date

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0004_create_tag'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='tag',
            options={'ordering': ['-created_at'], 'verbose_name': 'Tag', 'verbose_name_plural': 'Tags'},
        ),
    ]
