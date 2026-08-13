from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from areas.models import StudyArea, Wetland


class WetlandInline(admin.TabularInline):
    """Only to see at a glance which wetlands the study area holds; they are edited separately."""

    model = Wetland
    fields = ('name', 'country', 'ramsar_id', 'official_area')
    readonly_fields = fields
    extra = 0
    show_change_link = True
    can_delete = False

    def get_queryset(self, request):
        return super().get_queryset(request).defer('geom')

    def has_add_permission(self, request, obj):
        return False


@admin.register(StudyArea)
class StudyAreaAdmin(admin.ModelAdmin):
    """Study areas and their wetlands are loaded with the `create_study_area` command."""

    list_display = ('id', 'name', 'wetland_count')
    search_fields = ('name',)
    inlines = (WetlandInline,)

    @admin.display(description='Wetlands')
    def wetland_count(self, obj):
        return obj.wetlands.count()


@admin.register(Wetland)
class WetlandAdmin(admin.ModelAdmin):
    """The geometry is shown on a read-only map, not in the editable `GISModelAdmin`
    widget: that widget hands it back whole (several MB of WKT) on every POST and
    Django cuts the request off (RequestDataTooBig). By staying out of the form and
    deferred in the queries, saving the other fields neither sends nor rewrites it.
    """

    list_display = ('id', 'name', 'study_area', 'country', 'ramsar_id', 'official_area')
    list_filter = ('study_area', 'country')
    search_fields = ('name', 'ramsar_id')
    exclude = ('geom',)
    readonly_fields = ('map',)

    class Media:
        css = {'all': ('leaflet/dist/leaflet.css', 'leaflet.fullscreen/Control.FullScreen.css')}
        js = ('leaflet/dist/leaflet.js', 'leaflet.fullscreen/Control.FullScreen.js', 'js/areas.js')

    def get_queryset(self, request):
        return super().get_queryset(request).defer('geom')

    def has_add_permission(self, request):
        return False

    @admin.display(description='Geometry')
    def map(self, obj):
        """The map loads the geometry from the public endpoint, not from the form itself."""
        return format_html(
            '<div class="study-area-map" style="height: 500px; max-width: 900px;" data-geojson-url="{}"></div>',
            reverse('areas:wetland-geojson', args=[obj.pk]),
        )
