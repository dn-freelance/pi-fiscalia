from django.contrib import admin

from feeds.models import NewsItem


@admin.register(NewsItem)
class NewsItemAdmin(admin.ModelAdmin):
    list_display = ('title', 'source', 'analysis_status', 'is_read', 'published_at', 'updated_at')
    list_filter = ('is_read', 'source')
    search_fields = ('title', 'link', 'source__name')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('source', 'analysis')

    @admin.display(description='IA')
    def analysis_status(self, obj):
        analysis = obj.analysis_or_none
        if analysis is None:
            return '-'

        return analysis.get_status_display()
