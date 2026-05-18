from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feeds', '0009_news_import_job_redirect_relevance'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardWeeklySummary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('week_start', models.DateField(unique=True, verbose_name='início da semana')),
                ('week_end', models.DateField(verbose_name='fim da semana')),
                ('revision', models.PositiveIntegerField(default=1, verbose_name='revisão')),
                (
                    'status',
                    models.CharField(
                        choices=[
                            ('pending', 'Pendente'),
                            ('running', 'Em andamento'),
                            ('completed', 'Concluído'),
                            ('failed', 'Falhou'),
                        ],
                        default='pending',
                        max_length=16,
                        verbose_name='status',
                    ),
                ),
                ('overview', models.TextField(blank=True, verbose_name='visão geral')),
                ('main_changes', models.TextField(blank=True, verbose_name='principais mudanças')),
                ('attention', models.TextField(blank=True, verbose_name='atenção')),
                ('news_count', models.PositiveIntegerField(default=0, verbose_name='notícias consideradas')),
                ('high_relevance_count', models.PositiveIntegerField(default=0, verbose_name='itens de alta relevância')),
                ('effective_this_week_count', models.PositiveIntegerField(default=0, verbose_name='itens com vigência na semana')),
                ('error_message', models.CharField(blank=True, max_length=255, verbose_name='mensagem de erro')),
                ('started_at', models.DateTimeField(blank=True, null=True, verbose_name='iniciado em')),
                ('finished_at', models.DateTimeField(blank=True, null=True, verbose_name='finalizado em')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='atualizado em')),
            ],
            options={
                'verbose_name': 'Resumo Semanal do Dashboard',
                'verbose_name_plural': 'Resumos Semanais do Dashboard',
                'ordering': ['-week_start'],
            },
        ),
    ]
