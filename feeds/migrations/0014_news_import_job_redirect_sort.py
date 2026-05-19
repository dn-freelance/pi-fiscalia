from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0013_seed_default_receita_federal_source'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsimportjob',
            name='redirect_sort',
            field=models.CharField(blank=True, max_length=30, verbose_name='filtro de ordenação'),
        ),
    ]
