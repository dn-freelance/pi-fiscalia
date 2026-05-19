from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from feeds.models import DashboardWeeklySummary, Source, SourceCategory, Tag


class SourceViewTests(TestCase):
    default_source_url = 'https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS'

    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')
        cls.estadual = SourceCategory.objects.get(name='Estadual')
        cls.municipal = SourceCategory.objects.get(name='Municipal')

    def test_create_source_persists_source(self):
        response = self.client.post(
            reverse('feeds:create_source'),
            {
                'name': 'Receita Federal',
                'url': 'https://www.gov.br/receitafederal/rss',
                'description': 'Notícias fiscais federais.',
                'category': self.federal.id,
            },
        )

        self.assertRedirects(response, reverse('feeds:sources'))
        self.assertTrue(Source.objects.filter(name='Receita Federal', category=self.federal).exists())

    def test_create_source_persists_selected_tags(self):
        icms = Tag.objects.get(name='ICMS')
        ncm = Tag.objects.get(name='NCM')

        response = self.client.post(
            reverse('feeds:create_source'),
            {
                'name': 'Fonte com tags',
                'url': 'https://example.com/fonte-com-tags/rss',
                'description': 'Fonte filtrada por tags.',
                'category': self.federal.id,
                'tags': [str(icms.id), str(ncm.id)],
            },
        )

        self.assertRedirects(response, reverse('feeds:sources'))
        source = Source.objects.get(name='Fonte com tags')
        self.assertCountEqual(source.tags.values_list('name', flat=True), ['ICMS', 'NCM'])

    def test_create_source_rejects_invalid_payload(self):
        response = self.client.post(
            reverse('feeds:create_source'),
            {
                'name': '',
                'url': 'https://example.com/rss',
                'category': self.federal.id,
            },
        )

        self.assertRedirects(response, reverse('feeds:sources'))
        self.assertEqual(Source.objects.count(), 1)
        self.assertTrue(Source.objects.filter(url=self.default_source_url).exists())

    def test_update_source_changes_editable_fields_and_preserves_status(self):
        source = Source.objects.create(
            name='Antiga',
            url='https://example.com/antiga/rss',
            description='Descrição antiga.',
            category=self.federal,
            active=False,
        )

        response = self.client.post(
            reverse('feeds:update_source', args=[source.id]),
            {
                'name': 'Atualizada',
                'url': 'https://example.com/nova/rss',
                'description': 'Descrição nova.',
                'category': self.estadual.id,
            },
        )

        self.assertRedirects(response, reverse('feeds:sources'))
        source.refresh_from_db()
        self.assertEqual(source.name, 'Atualizada')
        self.assertEqual(source.category, self.estadual)
        self.assertFalse(source.active)

    def test_update_source_replaces_selected_tags(self):
        icms = Tag.objects.get(name='ICMS')
        ncm = Tag.objects.get(name='NCM')
        simples = Tag.objects.get(name='Simples Nacional')
        source = Source.objects.create(
            name='Fonte com tags',
            url='https://example.com/tags/rss',
            description='Descrição antiga.',
            category=self.federal,
        )
        source.tags.set([icms, ncm])

        response = self.client.post(
            reverse('feeds:update_source', args=[source.id]),
            {
                'name': 'Fonte com tags',
                'url': 'https://example.com/tags/rss',
                'description': 'Descrição atualizada.',
                'category': self.federal.id,
                'tags': [str(simples.id)],
            },
        )

        self.assertRedirects(response, reverse('feeds:sources'))
        source.refresh_from_db()
        self.assertCountEqual(source.tags.values_list('name', flat=True), ['Simples Nacional'])

    def test_delete_source_removes_source(self):
        source = Source.objects.create(
            name='Fonte removível',
            url='https://example.com/remover/rss',
            category=self.municipal,
        )

        response = self.client.post(reverse('feeds:delete_source', args=[source.id]))

        self.assertRedirects(response, reverse('feeds:sources'))
        self.assertFalse(Source.objects.filter(id=source.id).exists())

    def test_toggle_source_status_updates_active_flag(self):
        source = Source.objects.create(
            name='Fonte pausada',
            url='https://example.com/pausada/rss',
            category=self.federal,
            active=True,
        )

        response = self.client.post(
            reverse('feeds:toggle_source_status', args=[source.id]),
            {
                'active': '',
            },
        )

        self.assertRedirects(response, reverse('feeds:sources'))
        source.refresh_from_db()
        self.assertFalse(source.active)

    def test_delete_source_invalidates_current_weekly_summary(self):
        week_start = timezone.localdate() - timedelta(days=timezone.localdate().weekday())
        week_end = week_start + timedelta(days=6)
        summary = DashboardWeeklySummary.objects.create(
            week_start=week_start,
            week_end=week_end,
            status=DashboardWeeklySummary.STATUS_COMPLETED,
            revision=2,
            overview='Resumo antigo.',
            main_changes='Mudanças antigas.',
            attention='Atenção antiga.',
        )
        source = Source.objects.create(
            name='Fonte removível',
            url='https://example.com/remover/rss',
            category=self.municipal,
        )

        self.client.post(reverse('feeds:delete_source', args=[source.id]))

        summary.refresh_from_db()
        self.assertEqual(summary.status, DashboardWeeklySummary.STATUS_PENDING)
        self.assertEqual(summary.revision, 3)
        self.assertEqual(summary.overview, '')
