from django.test import TestCase
from django.urls import reverse

from feeds.models import Source, SourceCategory


class SourceViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.federal = SourceCategory.objects.get(name='Federal')
        cls.estadual = SourceCategory.objects.get(name='Estadual')
        cls.municipal = SourceCategory.objects.get(name='Municipal')

    def test_create_source_persists_source(self):
        response = self.client.post(reverse('feeds:create_source'), {
            'name': 'Receita Federal',
            'url': 'https://www.gov.br/receitafederal/rss',
            'description': 'Notícias fiscais federais.',
            'category': self.federal.id,
        })

        self.assertRedirects(response, reverse('feeds:sources'))
        self.assertTrue(Source.objects.filter(name='Receita Federal', category=self.federal).exists())

    def test_create_source_rejects_invalid_payload(self):
        response = self.client.post(reverse('feeds:create_source'), {
            'name': '',
            'url': 'https://example.com/rss',
            'category': self.federal.id,
        })

        self.assertRedirects(response, reverse('feeds:sources'))
        self.assertEqual(Source.objects.count(), 0)

    def test_update_source_changes_editable_fields_and_preserves_status(self):
        source = Source.objects.create(
            name='Antiga',
            url='https://example.com/antiga/rss',
            description='Descrição antiga.',
            category=self.federal,
            active=False,
        )

        response = self.client.post(reverse('feeds:update_source', args=[source.id]), {
            'name': 'Atualizada',
            'url': 'https://example.com/nova/rss',
            'description': 'Descrição nova.',
            'category': self.estadual.id,
        })

        self.assertRedirects(response, reverse('feeds:sources'))
        source.refresh_from_db()
        self.assertEqual(source.name, 'Atualizada')
        self.assertEqual(source.category, self.estadual)
        self.assertFalse(source.active)

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

        response = self.client.post(reverse('feeds:toggle_source_status', args=[source.id]), {
            'active': '',
        })

        self.assertRedirects(response, reverse('feeds:sources'))
        source.refresh_from_db()
        self.assertFalse(source.active)
