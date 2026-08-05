from django.contrib import admin

from earthengine.models import EarthEngineAccount


@admin.register(EarthEngineAccount)
class EarthEngineAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'ee_project', 'updated_at')
    search_fields = ('user__email', 'ee_project')
