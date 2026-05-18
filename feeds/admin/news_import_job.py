from django.contrib import admin

from feeds.models import NewsImportJob


@admin.register(NewsImportJob)
class NewsImportJobAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'status',
        'current_stage',
        'rss_processed_sources',
        'rss_total_sources',
        'analysis_processed_items',
        'analysis_total_items',
        'created_at',
        'finished_at',
    )
    list_filter = ('status', 'current_stage', 'analysis_enabled')
    search_fields = ('id', 'stage_title', 'stage_message', 'error_message')
    readonly_fields = (
        'id',
        'created_at',
        'updated_at',
        'started_at',
        'finished_at',
        'result_messages',
    )
