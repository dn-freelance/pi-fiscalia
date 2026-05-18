from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from feeds.models import NewsItem, Source, SourceCategory


class DashboardViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')
        cls.estadual = SourceCategory.objects.get(name='Estadual')

    def test_dashboard_reads_metrics_and_topics_from_database(self):
        active_source = Source.objects.create(
            name='Receita Federal',
            url='https://example.com/receita/rss',
            category=self.federal,
            active=True,
        )
        inactive_source = Source.objects.create(
            name='SEFAZ-SP',
            url='https://example.com/sefaz/rss',
            category=self.estadual,
            active=False,
        )

        now = timezone.now()
        older_date = now - timedelta(days=40)

        newest_item = NewsItem.objects.create(
            source=active_source,
            title='Nova atualizacao fiscal de ICMS',
            summary='Resumo do item mais recente.',
            link='https://example.com/noticia-1',
            external_id='news-1',
            dedupe_key='dedupe-1',
            published_at=now - timedelta(hours=1),
            is_read=False,
        )
        NewsItem.objects.create(
            source=active_source,
            title='Item ja lido sobre NCM',
            summary='Resumo do item lido.',
            link='https://example.com/noticia-2',
            external_id='news-2',
            dedupe_key='dedupe-2',
            published_at=now - timedelta(days=2),
            is_read=True,
        )
        NewsItem.objects.create(
            source=inactive_source,
            title='Historico de abril',
            summary='Resumo mais antigo.',
            link='https://example.com/noticia-3',
            external_id='news-3',
            dedupe_key='dedupe-3',
            published_at=older_date,
            is_read=False,
        )

        response = self.client.get(reverse('feeds:index'))

        metrics = {
            metric['label']: metric['value']
            for metric in response.context['dashboard_metrics']
        }
        ai_metrics = {
            metric['label']: metric['value']
            for metric in response.context['ai_metrics']
        }

        self.assertEqual(metrics['Total de Informativos'], 3)
        self.assertEqual(metrics['Não Lidos'], 2)
        self.assertEqual(metrics['Em Foco Agora'], 1)
        self.assertEqual(metrics['Assuntos em Destaque'], 3)
        self.assertEqual(ai_metrics['Alertas com IA'], 0)
        self.assertEqual(ai_metrics['Priorização com IA'], 0)

        self.assertEqual(response.context['unread_count'], 2)
        self.assertEqual(response.context['published_this_month_count'], 2)
        self.assertEqual(response.context['source_health']['inactive_count'], 1)
        self.assertEqual(response.context['source_health']['active_percentage'], 50)
        self.assertEqual(response.context['recent_news_items'][0], newest_item)
        self.assertEqual(response.context['principal_change'], newest_item)
        self.assertEqual(response.context['topic_rows'][0]['name'], 'ICMS')
        self.assertEqual(response.context['top_sources'][0], active_source)
        self.assertEqual(response.context['top_sources'][0].news_total, 2)
        self.assertEqual(response.context['top_sources'][0].unread_total, 1)

    def test_dashboard_shows_seeded_categories_even_without_sources(self):
        response = self.client.get(reverse('feeds:index'))

        categories = response.context['category_rows']

        self.assertEqual(len(categories), 3)
        self.assertContains(response, 'Cobertura monitorada')
        self.assertContains(response, 'Assuntos monitorados')
