import json

from django.contrib.gis.db.models.functions import AsGeoJSON
from django.db.models.functions import Coalesce
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View, generic

from areas.functions import Simplify
from areas.models import StudyArea, Wetland

"""
The study area map can be zoomed in, so it takes far more detail than the thumbnail,
but the raw geometry is several MB per area.
"""
MAP_TOLERANCE = 0.0002
MAP_DECIMALS = 6

# The boundary is a single outline drawn as a thin line, so it takes a coarser
# simplification than the wetlands without any visible loss.
BOUNDARY_TOLERANCE = 0.002


def geojson_collection(wetlands):
    """FeatureCollection with one wetland per feature, already simplified.

    It is assembled by hand rather than with a serializer because PostGIS hands the
    geometry over as GeoJSON already: that way only the geometry is parsed, not
    converted all over again.
    """
    features = [
        {
            'type': 'Feature',
            'geometry': json.loads(wetland.geojson),
            'properties': {
                'pk': wetland.pk,
                'name': wetland.name,
                'kind': wetland.kind,
                'country': wetland.country,
                'official_area': wetland.official_area,
            },
        }
        for wetland in wetlands
        if wetland.geojson
    ]
    return {'type': 'FeatureCollection', 'features': features}


def simplified_wetlands(study_area, tolerance=MAP_TOLERANCE, decimals=MAP_DECIMALS):
    """The study area's areas, light enough to draw.

    `ST_Simplify` returns NULL for anything that fits inside the tolerance, and some of
    the eLTER sites are a single plot a few tens of metres across. Falling back to the
    raw geometry costs nothing for exactly those -- they are tiny, that being the
    problem -- and keeps them from vanishing off the map while still being offered in
    the dropdown.
    """
    return (
        Wetland.objects.filter(study_area=study_area)
        .annotate(geojson=Coalesce(
            AsGeoJSON(Simplify('geom', tolerance), precision=decimals),
            AsGeoJSON('geom', precision=decimals),
        ))
        .defer('geom')
        .order_by('name')
    )


class StudyAreaDetailView(generic.DetailView):
    model = StudyArea
    template_name = 'areas/detail.html'
    context_object_name = 'study_area'


class StudyAreaGeoJSONView(View):
    """Serves the wetlands separately so as not to embed megabytes of coordinates in the HTML."""

    def get(self, request, pk):
        study_area = get_object_or_404(StudyArea, pk=pk)
        collection = geojson_collection(simplified_wetlands(study_area))
        return HttpResponse(json.dumps(collection), content_type='application/geo+json')


class StudyAreaBoundaryView(View):
    """The study area outline, which the map frames itself on and will not pan outside.

    Simplified harder than the wetlands: it is one big outline drawn as a thin line, so
    the vertices that survive are the only ones that were ever going to be visible.
    """

    def get(self, request, pk):
        study_area = get_object_or_404(
            StudyArea.objects.annotate(
                geojson=AsGeoJSON(Simplify('boundary', BOUNDARY_TOLERANCE), precision=MAP_DECIMALS),
            ),
            pk=pk,
        )
        if not study_area.geojson:
            raise Http404('This study area has no boundary.')
        return HttpResponse(study_area.geojson, content_type='application/geo+json')


class WetlandGeoJSONView(View):
    """A single wetland, for the map on the admin detail page."""

    def get(self, request, pk):
        wetland = get_object_or_404(
            Wetland.objects.annotate(
                geojson=AsGeoJSON(Simplify('geom', MAP_TOLERANCE), precision=MAP_DECIMALS),
            ),
            pk=pk,
        )
        return HttpResponse(wetland.geojson, content_type='application/geo+json')
