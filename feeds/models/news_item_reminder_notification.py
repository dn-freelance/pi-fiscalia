from django.db import models

from feeds.models.news_item import NewsItem


class NewsItemReminderNotification(models.Model):
    news_item = models.ForeignKey(
        NewsItem,
        verbose_name='informativo',
        on_delete=models.CASCADE,
        related_name='reminder_notifications',
    )
    effective_date = models.DateField('data de vigência')
    reminder_date = models.DateField('data do lembrete')
    days_before = models.PositiveSmallIntegerField('dias antes da vigência')
    dismissed_at = models.DateTimeField('dispensado em', null=True, blank=True)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    updated_at = models.DateTimeField('atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Notificação de Vigência'
        verbose_name_plural = 'Notificações de Vigência'
        constraints = [
            models.UniqueConstraint(
                fields=['news_item', 'effective_date', 'days_before'],
                name='unique_news_item_effective_date_reminder',
            ),
        ]

    def __str__(self):
        return f'Lembrete {self.days_before}d - {self.news_item.title}'
