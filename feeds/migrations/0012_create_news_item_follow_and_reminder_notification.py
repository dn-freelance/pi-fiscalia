from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0011_news_import_job_redirect_effective_dates'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsItemFollow',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='atualizado em')),
                (
                    'news_item',
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='follow',
                        to='feeds.newsitem',
                        verbose_name='informativo',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Acompanhamento de Informativo',
                'verbose_name_plural': 'Acompanhamentos de Informativos',
            },
        ),
        migrations.CreateModel(
            name='NewsItemReminderNotification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('effective_date', models.DateField(verbose_name='data de vigência')),
                ('reminder_date', models.DateField(verbose_name='data do lembrete')),
                ('days_before', models.PositiveSmallIntegerField(verbose_name='dias antes da vigência')),
                ('dismissed_at', models.DateTimeField(blank=True, null=True, verbose_name='dispensado em')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='atualizado em')),
                (
                    'news_item',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='reminder_notifications',
                        to='feeds.newsitem',
                        verbose_name='informativo',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Notificação de Vigência',
                'verbose_name_plural': 'Notificações de Vigência',
            },
        ),
        migrations.AddConstraint(
            model_name='newsitemremindernotification',
            constraint=models.UniqueConstraint(
                fields=('news_item', 'effective_date', 'days_before'),
                name='unique_news_item_effective_date_reminder',
            ),
        ),
    ]
