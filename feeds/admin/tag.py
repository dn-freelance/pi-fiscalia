from django.contrib import admin

from feeds.models import Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'created_at', 'updated_at')
    list_filter = ('color',)
    search_fields = ('name',)
    ordering = ('name',)
