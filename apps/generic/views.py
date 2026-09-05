from areas.functions import Simplify
from areas.models import StudyArea
from django.conf import settings
from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.contrib.staticfiles import finders
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


class ManualView(generic.TemplateView):
    """One of the two manuals.

    The same document is served as a page and printed to a PDF (see
    `scripts/build_manual_pdfs.sh`), so there is one source for both and no second copy
    to fall out of step with the first.
    """

    # The PDF the page offers for download, under `static/`. It is only linked once it
    # actually exists: the manuals are written before their screenshots are taken, and
    # the PDF is regenerated afterwards.
    pdf = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['app_url'] = settings.APP_URL
        context['pdf'] = self.pdf if self.pdf and finders.find(self.pdf) else None
        return context


class ManualEarthEngineView(ManualView):
    template_name = 'manual/earth_engine.html'
    pdf = 'manual/restore4life-earth-engine.pdf'


class ManualApplicationView(ManualView):
    template_name = 'manual/application.html'
    pdf = 'manual/restore4life-user-manual.pdf'
