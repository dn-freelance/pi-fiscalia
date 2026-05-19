from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from feeds.models import NewsItem, NewsItemAnalysis
from feeds.services.news_analysis import build_news_analysis_service


class Command(BaseCommand):
    help = 'Executa backfill da análise de IA para informativos antigos ou pendentes.'

    def handle(self, *args, **options):
        service, warning_message = build_news_analysis_service()
        if service is None:
            if warning_message:
                self.stdout.write(self.style.WARNING(warning_message))
            else:
                self.stdout.write(self.style.WARNING('IA desabilitada. Nenhuma análise foi executada.'))
            return

        queryset = NewsItem.objects.select_related('source', 'source__category', 'analysis').prefetch_related('source__tags').filter(
            Q(analysis__isnull=True)
            | Q(analysis__status=NewsItemAnalysis.STATUS_FAILED)
            | ~Q(analysis__pipeline_version=settings.NEWS_AI['PIPELINE_VERSION'])
        )

        pending_news_items = list(queryset)
        processed_count = 0
        failed_count = 0
        halted_message = ''

        for start in range(0, len(pending_news_items), service.batch_size):
            batch = pending_news_items[start:start + service.batch_size]
            execution_result = service.analyze_news_items(batch)
            processed_count += execution_result.updated_count
            failed_count += execution_result.failed_count

            if execution_result.halted:
                halted_message = (
                    'Backfill interrompido por limite do provider de IA. '
                    f'{execution_result.halted_pending_count} notícia(s) permaneceram pendentes. '
                    f'{execution_result.halt_reason}'
                )
                break

        self.stdout.write(
            self.style.SUCCESS(
                f'Backfill concluído: {processed_count} análise(s) atualizada(s) e {failed_count} falha(s).'
            )
        )
        if halted_message:
            self.stdout.write(self.style.WARNING(halted_message))
