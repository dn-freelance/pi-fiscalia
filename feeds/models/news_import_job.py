import uuid

from django.db import models


class NewsImportJob(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_RUNNING = 'running'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pendente'),
        (STATUS_RUNNING, 'Em andamento'),
        (STATUS_COMPLETED, 'Concluída'),
        (STATUS_FAILED, 'Falhou'),
    ]

    STAGE_QUEUED = 'queued'
    STAGE_RSS = 'rss'
    STAGE_ANALYSIS = 'analysis'
    STAGE_COMPLETED = 'completed'
    STAGE_FAILED = 'failed'

    STAGE_CHOICES = [
        (STAGE_QUEUED, 'Na fila'),
        (STAGE_RSS, 'Importação RSS'),
        (STAGE_ANALYSIS, 'Análise por IA'),
        (STAGE_COMPLETED, 'Concluída'),
        (STAGE_FAILED, 'Falhou'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField('status', max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)
    current_stage = models.CharField('etapa atual', max_length=16, choices=STAGE_CHOICES, default=STAGE_QUEUED)
    stage_title = models.CharField('título da etapa', max_length=120, blank=True)
    stage_message = models.CharField('mensagem da etapa', max_length=255, blank=True)

    rss_total_sources = models.PositiveIntegerField('total de fontes RSS', default=0)
    rss_processed_sources = models.PositiveIntegerField('fontes RSS processadas', default=0)

    analysis_enabled = models.BooleanField('análise por IA habilitada', default=False)
    analysis_total_items = models.PositiveIntegerField('total de notícias para IA', default=0)
    analysis_processed_items = models.PositiveIntegerField('notícias analisadas pela IA', default=0)

    imported_created_count = models.PositiveIntegerField('notícias novas importadas', default=0)
    imported_existing_count = models.PositiveIntegerField('notícias já existentes', default=0)
    import_error_count = models.PositiveIntegerField('fontes com erro', default=0)
    import_skipped_count = models.PositiveIntegerField('notícias ignoradas na importação', default=0)

    analysis_failure_count = models.PositiveIntegerField('falhas de análise IA', default=0)
    analysis_skipped_count = models.PositiveIntegerField('notícias sem análise IA', default=0)

    redirect_query = models.CharField('filtro de pesquisa', max_length=255, blank=True)
    redirect_source = models.CharField('filtro de fonte', max_length=20, blank=True)
    redirect_status = models.CharField('filtro de status', max_length=20, blank=True)
    redirect_sort = models.CharField('filtro de ordenação', max_length=30, blank=True)
    redirect_relevance = models.CharField('filtro de relevância', max_length=20, blank=True)
    redirect_effective_date_from = models.CharField('vigência inicial', max_length=10, blank=True)
    redirect_effective_date_to = models.CharField('vigência final', max_length=10, blank=True)

    result_messages = models.JSONField('mensagens finais', default=list, blank=True)
    error_message = models.CharField('mensagem de erro', max_length=255, blank=True)
    started_at = models.DateTimeField('iniciado em', null=True, blank=True)
    finished_at = models.DateTimeField('finalizado em', null=True, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Job de Atualização de Informativos'
        verbose_name_plural = 'Jobs de Atualização de Informativos'

    def __str__(self):
        return f'Atualização de informativos {self.pk}'

    @property
    def is_finished(self):
        return self.status in {self.STATUS_COMPLETED, self.STATUS_FAILED}

    @property
    def rss_progress_percent(self):
        if self.rss_total_sources <= 0:
            return 0

        return min(100, int((self.rss_processed_sources / self.rss_total_sources) * 100))

    @property
    def analysis_progress_percent(self):
        if not self.analysis_enabled:
            return 100

        if self.analysis_total_items <= 0:
            return 0

        return min(100, int((self.analysis_processed_items / self.analysis_total_items) * 100))
