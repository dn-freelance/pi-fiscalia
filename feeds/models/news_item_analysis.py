from django.db import models

from feeds.models.news_item import NewsItem


class NewsItemAnalysis(models.Model):
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Concluída'),
        (STATUS_FAILED, 'Falhou'),
    ]

    IMPACT_HIGH = 'high'
    IMPACT_MEDIUM = 'medium'
    IMPACT_LOW = 'low'

    IMPACT_LEVEL_CHOICES = [
        (IMPACT_HIGH, 'Alta'),
        (IMPACT_MEDIUM, 'Média'),
        (IMPACT_LOW, 'Baixa'),
    ]

    news_item = models.OneToOneField(
        NewsItem,
        verbose_name='informativo',
        on_delete=models.CASCADE,
        related_name='analysis',
    )
    summary = models.TextField('resumo da IA', blank=True)
    impact_level = models.CharField(
        'grau de impacto',
        max_length=16,
        choices=IMPACT_LEVEL_CHOICES,
        blank=True,
    )
    impact_context = models.CharField('contexto do impacto', max_length=255, blank=True)
    keywords = models.JSONField('palavras-chave', default=list, blank=True)
    importance_score = models.PositiveSmallIntegerField('score de importância', null=True, blank=True)
    effective_date = models.DateField('data de vigência', null=True, blank=True)
    effective_date_label = models.CharField('rótulo da vigência', max_length=120, blank=True)
    status = models.CharField('status da análise', max_length=16, choices=STATUS_CHOICES, default=STATUS_FAILED)
    provider = models.CharField('provider', max_length=50, blank=True)
    model = models.CharField('modelo', max_length=100, blank=True)
    input_hash = models.CharField('hash de entrada', max_length=64, blank=True)
    pipeline_version = models.CharField('versão do pipeline', max_length=50, blank=True)
    error_message = models.CharField('mensagem de erro', max_length=255, blank=True)
    analyzed_at = models.DateTimeField('analisado em', null=True, blank=True)
    last_attempt_at = models.DateTimeField('última tentativa em', null=True, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Análise de Informativo'
        verbose_name_plural = 'Análises de Informativos'

    def __str__(self):
        return f'Análise IA - {self.news_item.title}'

    @property
    def impact_label(self):
        return {
            self.IMPACT_HIGH: 'ALTA',
            self.IMPACT_MEDIUM: 'MÉDIA',
            self.IMPACT_LOW: 'BAIXA',
        }.get(self.impact_level, '')

    @property
    def impact_context_display(self):
        if self.impact_context:
            return self.impact_context

        return {
            self.IMPACT_HIGH: 'Alto potencial de impacto fiscal ou operacional, com necessidade de acompanhamento prioritário.',
            self.IMPACT_MEDIUM: 'Possível reflexo fiscal ou operacional, recomendado para acompanhamento.',
            self.IMPACT_LOW: 'Baixo impacto fiscal imediato, sem indícios de mudança relevante até o momento.',
        }.get(self.impact_level, '')

    @property
    def effective_date_display(self):
        if self.effective_date_label:
            return self.effective_date_label

        if self.effective_date is None:
            return ''

        return self.effective_date.strftime('%d/%m/%Y')

    @property
    def has_impact(self):
        return bool(self.impact_level or self.impact_context_display)

    @property
    def has_keywords(self):
        return bool(self.keywords)

    @property
    def has_importance_score(self):
        return self.importance_score is not None

    @property
    def has_effective_date_display(self):
        return bool(self.effective_date_display)
