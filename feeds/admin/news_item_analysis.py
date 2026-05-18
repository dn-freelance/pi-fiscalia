from django.contrib import admin

from feeds.models import NewsItemAnalysis


@admin.register(NewsItemAnalysis)
class NewsItemAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        'news_item',
        'status',
        'impact_level',
        'importance_score',
        'provider',
        'model',
        'analyzed_at',
    )
    list_filter = ('status', 'impact_level', 'provider', 'model')
    search_fields = ('news_item__title', 'news_item__source__name', 'impact_context', 'summary')
    readonly_fields = ('created_at', 'updated_at', 'last_attempt_at', 'analyzed_at')
    list_select_related = ('news_item', 'news_item__source')
