from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0010_create_dashboard_weekly_summary'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsimportjob',
            name='redirect_effective_date_from',
            field=models.CharField(blank=True, max_length=10, verbose_name='vigência inicial'),
        ),
        migrations.AddField(
            model_name='newsimportjob',
            name='redirect_effective_date_to',
            field=models.CharField(blank=True, max_length=10, verbose_name='vigência final'),
        ),
    ]
