from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0014_news_import_job_redirect_sort'),
    ]

    operations = [
        migrations.AddField(
            model_name='newsitemanalysis',
            name='base_importance_score',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='score base da IA'),
        ),
        migrations.AddField(
            model_name='newsitemanalysis',
            name='tag_score_boost',
            field=models.PositiveSmallIntegerField(default=0, verbose_name='bônus por tags'),
        ),
        migrations.AddField(
            model_name='newsitemanalysis',
            name='tag_score_matches',
            field=models.JSONField(blank=True, default=list, verbose_name='detalhes do bônus por tags'),
        ),
        migrations.AddField(
            model_name='source',
            name='tags',
            field=models.ManyToManyField(blank=True, related_name='sources', to='feeds.tag', verbose_name='tags de score'),
        ),
    ]
