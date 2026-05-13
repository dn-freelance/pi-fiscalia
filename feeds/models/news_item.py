from django.db import models

from feeds.models.source import Source


class NewsItem(models.Model):
    source = models.ForeignKey(
        Source,
        verbose_name='fonte',
        on_delete=models.CASCADE,
        related_name='news_items',
    )
    title = models.CharField('título', max_length=500)
    summary = models.TextField('resumo', blank=True)
    link = models.URLField('link original', max_length=1000)
    external_id = models.CharField('identificador externo', max_length=500, blank=True)
    dedupe_key = models.CharField('chave de deduplicação', max_length=64)
    published_at = models.DateTimeField('publicado em', null=True, blank=True)
    is_read = models.BooleanField('lido', default=False)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Informativo'
        verbose_name_plural = 'Informativos'
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'dedupe_key'],
                name='unique_news_item_per_source_dedupe',
            ),
        ]

    def __str__(self):
        return self.title

    @property
    def displayed_at(self):
        return self.published_at or self.created_at
