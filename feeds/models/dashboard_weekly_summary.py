from django.db import models


class DashboardWeeklySummary(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendente'),
        (STATUS_RUNNING, 'Em andamento'),
        (STATUS_COMPLETED, 'Concluído'),
        (STATUS_FAILED, 'Falhou'),
    ]

    week_start = models.DateField('início da semana', unique=True)
    week_end = models.DateField('fim da semana')
    revision = models.PositiveIntegerField('revisão', default=1)
    status = models.CharField('status', max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)

    overview = models.TextField('visão geral', blank=True)
    main_changes = models.TextField('principais mudanças', blank=True)
    attention = models.TextField('atenção', blank=True)

    news_count = models.PositiveIntegerField('notícias consideradas', default=0)
    high_relevance_count = models.PositiveIntegerField('itens de alta relevância', default=0)
    effective_this_week_count = models.PositiveIntegerField('itens com vigência na semana', default=0)

    error_message = models.CharField('mensagem de erro', max_length=255, blank=True)
    started_at = models.DateTimeField('iniciado em', null=True, blank=True)
    finished_at = models.DateTimeField('finalizado em', null=True, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['-week_start']
        verbose_name = 'Resumo Semanal do Dashboard'
        verbose_name_plural = 'Resumos Semanais do Dashboard'

    def __str__(self):
        return f'Resumo semanal a partir de {self.week_start:%d/%m/%Y}'

    @property
    def is_ready(self):
        return self.status == self.STATUS_COMPLETED
