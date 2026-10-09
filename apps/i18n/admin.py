from django.contrib import admin

from .models import GlossaryTerm, Language


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "enabled", "position"]
    list_editable = ["enabled", "position"]


@admin.register(GlossaryTerm)
class GlossaryTermAdmin(admin.ModelAdmin):
    list_display = ["__str__", "updated_at"]
