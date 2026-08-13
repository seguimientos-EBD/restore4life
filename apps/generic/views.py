from areas.functions import Simplify
from areas.models import StudyArea
from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.db.models import Count
from django.views import generic

# The listing thumbnails are 160 px: below ~500 m and 4 decimals (~10 m) the detail is
# no longer distinguishable, and the full geometry is several MB.
THUMBNAIL_TOLERANCE = 0.005
THUMBNAIL_DECIMALS = 4


class IndexView(generic.ListView):
    template_name = "index.html"
    context_object_name = 'study_areas'

    def get_queryset(self):
        # The thumbnail merges the study area's wetlands with `ST_Collect`, not with
        # `ST_Union`: overlaps need not be dissolved just to draw, it comes out far
        # cheaper and, above all, merging already-simplified geometries fails (the
        # simplification does not preserve topology and GEOS chokes on it).
        return StudyArea.objects.annotate(
            wetland_count=Count('wetlands'),
            geojson=AsGeoJSON(
                Collect(Simplify('wetlands__geom', THUMBNAIL_TOLERANCE)),
                precision=THUMBNAIL_DECIMALS,
            ),
        ).order_by('name')


class CitationView(generic.TemplateView):
    template_name = "citation.html"


class FaqView(generic.TemplateView):
    template_name = "faq.html"
