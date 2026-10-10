from django.contrib import admin

from .models import Article, ArticleTranslation, Collection, Revision


@admin.register(Collection)
class CollectionAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_public", "position"]
    prepopulated_fields = {"slug": ["name"]}


class TranslationInline(admin.TabularInline):
    model = ArticleTranslation
    fields = ["language", "draft_title", "title", "published_at", "is_outdated"]
    readonly_fields = ["title", "published_at"]
    extra = 0


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["slug", "collection", "parent", "position", "updated_at"]
    list_filter = ["collection"]
    search_fields = ["slug", "translations__title", "translations__draft_title"]
    filter_horizontal = ["read_groups"]
    inlines = [TranslationInline]


@admin.register(Revision)
class RevisionAdmin(admin.ModelAdmin):
    list_display = ["translation", "number", "kind", "author", "created_at"]
    list_filter = ["kind"]
    readonly_fields = ["translation", "number", "kind", "title", "content", "author"]
