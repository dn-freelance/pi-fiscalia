import logging
from threading import Thread

from django.db import close_old_connections
from django.utils import timezone

from feeds.models import NewsImportJob
from feeds.services.news_import import build_news_import_feedback, import_news_items

logger = logging.getLogger(__name__)


def start_news_import_job(job_id):
    worker = Thread(
        target=run_news_import_job,
        args=(job_id,),
        daemon=True,
        name=f'news-import-job-{job_id}',
    )
    worker.start()
    return worker


def run_news_import_job(job_id):
    close_old_connections()
    try:
        job = NewsImportJob.objects.get(pk=job_id)
        reporter = NewsImportJobReporter(job)
        reporter.mark_started()
        result = import_news_items(progress_callback=reporter.handle_event)
        reporter.mark_completed(result)
    except NewsImportJob.DoesNotExist:
        logger.warning('Job de importação de informativos %s não foi encontrado.', job_id)
    except Exception as error:  # pragma: no cover - proteção adicional para execução em thread
        logger.exception('Falha inesperada ao executar job de importação de informativos %s', job_id)
        _mark_job_failed(job_id, error)
    finally:
        close_old_connections()


class NewsImportJobReporter:
    def __init__(self, job):
        self.job = job

    def mark_started(self):
        now = timezone.now()
        self.job.status = NewsImportJob.STATUS_RUNNING
        self.job.current_stage = NewsImportJob.STAGE_QUEUED
        self.job.stage_title = 'Preparando atualização'
        self.job.stage_message = 'Organizando as fontes e iniciando a atualização dos informativos.'
        self.job.started_at = now
        self.job.finished_at = None
        self.job.error_message = ''
        self.job.result_messages = []
        self.job.save(
            update_fields=[
                'status',
                'current_stage',
                'stage_title',
                'stage_message',
                'started_at',
                'finished_at',
                'error_message',
                'result_messages',
                'updated_at',
            ]
        )

    def handle_event(self, event_name, **payload):
        handler = getattr(self, f'_handle_{event_name}', None)
        if handler is None:
            return

        handler(**payload)

    def mark_completed(self, result):
        self.job.status = NewsImportJob.STATUS_COMPLETED
        self.job.current_stage = NewsImportJob.STAGE_COMPLETED
        self.job.stage_title = 'Atualização concluída'
        self.job.stage_message = _build_completion_message(result)
        self.job.imported_created_count = result.created_count
        self.job.imported_existing_count = result.existing_count
        self.job.import_error_count = result.error_count
        self.job.import_skipped_count = result.skipped_count
        self.job.analysis_failure_count = result.analysis_failure_count
        self.job.analysis_skipped_count = result.analysis_skipped_count
        self.job.result_messages = build_news_import_feedback(result)
        self.job.finished_at = timezone.now()
        self.job.error_message = ''
        self.job.save(
            update_fields=[
                'status',
                'current_stage',
                'stage_title',
                'stage_message',
                'imported_created_count',
                'imported_existing_count',
                'import_error_count',
                'import_skipped_count',
                'analysis_failure_count',
                'analysis_skipped_count',
                'result_messages',
                'finished_at',
                'error_message',
                'updated_at',
            ]
        )

    def _handle_rss_start(self, total_sources, analysis_enabled):
        self.job.status = NewsImportJob.STATUS_RUNNING
        self.job.current_stage = NewsImportJob.STAGE_RSS
        self.job.stage_title = 'Importando notícias das fontes RSS'
        self.job.stage_message = 'Conectando nas fontes ativas e conferindo novos informativos.'
        self.job.rss_total_sources = total_sources
        self.job.rss_processed_sources = 0
        self.job.analysis_enabled = bool(analysis_enabled)
        self.job.analysis_total_items = 0
        self.job.analysis_processed_items = 0
        self.job.save(
            update_fields=[
                'status',
                'current_stage',
                'stage_title',
                'stage_message',
                'rss_total_sources',
                'rss_processed_sources',
                'analysis_enabled',
                'analysis_total_items',
                'analysis_processed_items',
                'updated_at',
            ]
        )

    def _handle_rss_progress(
        self,
        processed_sources,
        total_sources,
        source_name,
        created_count,
        existing_count,
        error_count,
        skipped_count,
        queued_analysis_count,
    ):
        self.job.current_stage = NewsImportJob.STAGE_RSS
        self.job.stage_title = 'Importando notícias das fontes RSS'
        self.job.stage_message = (
            f'Fonte atual: {source_name}. {processed_sources} de {total_sources} fonte(s) processada(s).'
        )
        self.job.rss_total_sources = total_sources
        self.job.rss_processed_sources = processed_sources
        self.job.imported_created_count = created_count
        self.job.imported_existing_count = existing_count
        self.job.import_error_count = error_count
        self.job.import_skipped_count = skipped_count
        self.job.analysis_total_items = queued_analysis_count
        self.job.save(
            update_fields=[
                'current_stage',
                'stage_title',
                'stage_message',
                'rss_total_sources',
                'rss_processed_sources',
                'imported_created_count',
                'imported_existing_count',
                'import_error_count',
                'import_skipped_count',
                'analysis_total_items',
                'updated_at',
            ]
        )

    def _handle_analysis_start(self, total_items, analysis_enabled):
        self.job.current_stage = NewsImportJob.STAGE_ANALYSIS
        self.job.analysis_enabled = bool(analysis_enabled)
        self.job.analysis_total_items = total_items
        self.job.analysis_processed_items = 0
        if analysis_enabled:
            self.job.stage_title = 'Analisando notícias com IA'
            self.job.stage_message = (
                f'Preparando {total_items} notícia(s) para extrair resumo, impacto, score e vigência.'
            )
        else:
            self.job.stage_title = 'Importação concluída, IA desabilitada'
            self.job.stage_message = (
                'As notícias foram importadas normalmente. A camada de IA está desabilitada nesta configuração.'
            )

        self.job.save(
            update_fields=[
                'current_stage',
                'analysis_enabled',
                'analysis_total_items',
                'analysis_processed_items',
                'stage_title',
                'stage_message',
                'updated_at',
            ]
        )

    def _handle_analysis_progress(
        self,
        processed_count,
        total_count,
        updated_count,
        failed_count,
        skipped_count,
        halted,
    ):
        self.job.current_stage = NewsImportJob.STAGE_ANALYSIS
        self.job.analysis_total_items = total_count
        self.job.analysis_processed_items = processed_count
        self.job.analysis_failure_count = failed_count
        self.job.analysis_skipped_count = skipped_count

        if not self.job.analysis_enabled:
            self.job.stage_title = 'Importação concluída, IA desabilitada'
            self.job.stage_message = 'Finalizando a atualização para retornar à listagem.'
        elif halted:
            self.job.stage_title = 'Análise da IA interrompida'
            self.job.stage_message = (
                'A análise foi interrompida por limite do provider. As notícias já importadas serão preservadas.'
            )
        elif total_count == 0:
            self.job.stage_title = 'Sem notícias pendentes para IA'
            self.job.stage_message = 'Nada novo precisou ser analisado nesta atualização.'
        else:
            self.job.stage_title = 'Analisando notícias com IA'
            self.job.stage_message = (
                f'IA processou {processed_count} de {total_count} notícia(s). '
                f'{updated_count} concluída(s), {failed_count} com falha.'
            )

        self.job.save(
            update_fields=[
                'current_stage',
                'analysis_total_items',
                'analysis_processed_items',
                'analysis_failure_count',
                'analysis_skipped_count',
                'stage_title',
                'stage_message',
                'updated_at',
            ]
        )


def _mark_job_failed(job_id, error):
    updated = NewsImportJob.objects.filter(pk=job_id).update(
        status=NewsImportJob.STATUS_FAILED,
        current_stage=NewsImportJob.STAGE_FAILED,
        stage_title='Atualização interrompida',
        stage_message='Ocorreu uma falha inesperada ao processar a atualização dos informativos.',
        error_message=str(error),
        result_messages=[
            {
                'level': 'error',
                'text': 'Não foi possível concluir a atualização dos informativos. Tente novamente em instantes.',
            }
        ],
        finished_at=timezone.now(),
        updated_at=timezone.now(),
    )
    if not updated:
        logger.warning('Não foi possível marcar o job %s como falho porque ele não existe mais.', job_id)


def _build_completion_message(result):
    if result.source_count == 0:
        return 'Nenhuma fonte ativa estava disponível para atualizar.'

    if result.analysis_halted:
        return 'Importação concluída. A análise de IA foi interrompida e poderá ser retomada na próxima atualização.'

    if result.analysis_failure_count:
        return 'Importação concluída. Algumas notícias precisaram ficar sem análise de IA nesta rodada.'

    return 'Importação e análise concluídas. Redirecionando você de volta para a listagem.'
