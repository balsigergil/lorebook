from django.contrib import admin

from .models import Comment, Thread


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0


@admin.register(Thread)
class ThreadAdmin(admin.ModelAdmin):
    list_display = ["__str__", "translation", "author", "created_at", "resolved_at"]
    inlines = [CommentInline]
