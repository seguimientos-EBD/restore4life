from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from ambitos.models import Ambito, Humedal


class HumedalInline(admin.TabularInline):
    """Solo para ver de un vistazo qué humedales tiene el ámbito; se editan aparte."""

    model = Humedal
    fields = ('nombre', 'pais', 'ramsarid', 'area_oficial')
    readonly_fields = fields
    extra = 0
    show_change_link = True
    can_delete = False

    def get_queryset(self, request):
        return super().get_queryset(request).defer('geom')

    def has_add_permission(self, request, obj):
        return False


@admin.register(Ambito)
class AmbitoAdmin(admin.ModelAdmin):
    """Los ámbitos y sus humedales se dan de alta con el comando `crear_ambito`."""

    list_display = ('id', 'nombre', 'n_humedales')
    search_fields = ('nombre',)
    inlines = (HumedalInline,)

    @admin.display(description='Humedales')
    def n_humedales(self, obj):
        return obj.humedales.count()


@admin.register(Humedal)
class HumedalAdmin(admin.ModelAdmin):
    """La geometría se enseña en un mapa de solo lectura, no en el widget editable de
    `GISModelAdmin`: ese widget la devuelve entera (varios MB de WKT) en cada POST y
    Django corta la petición (RequestDataTooBig). Al quedar fuera del formulario y
    diferida en las consultas, guardar el resto de campos ni la envía ni la reescribe.
    """

    list_display = ('id', 'nombre', 'ambito', 'pais', 'ramsarid', 'area_oficial')
    list_filter = ('ambito', 'pais')
    search_fields = ('nombre', 'ramsarid')
    exclude = ('geom',)
    readonly_fields = ('mapa',)

    class Media:
        css = {'all': ('leaflet/dist/leaflet.css', 'leaflet.fullscreen/Control.FullScreen.css')}
        js = ('leaflet/dist/leaflet.js', 'leaflet.fullscreen/Control.FullScreen.js', 'js/ambitos.js')

    def get_queryset(self, request):
        return super().get_queryset(request).defer('geom')

    def has_add_permission(self, request):
        return False

    @admin.display(description='Geometría')
    def mapa(self, obj):
        """El mapa carga la geometría del endpoint público, no del propio formulario."""
        return format_html(
            '<div class="ambito-mapa" style="height: 500px; max-width: 900px;" data-geojson-url="{}"></div>',
            reverse('ambitos:humedal-geojson', args=[obj.pk]),
        )
