from django.contrib import admin

from .models import MediaFile


@admin.register(MediaFile)
class MediaFileAdmin(admin.ModelAdmin):
    list_display = ["original_name", "collection", "content_type", "size", "created_at"]
    list_filter = ["collection"]
