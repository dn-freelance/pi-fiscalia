from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0008_create_news_import_job'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsimportjob',
            name='redirect_relevance',
            field=models.CharField(blank=True, max_length=20, verbose_name='filtro de relevância'),
        ),
    ]
