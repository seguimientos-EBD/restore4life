from ambitos.functions import Simplify
from ambitos.models import Ambito
from django.contrib.gis.db.models import Collect
from django.contrib.gis.db.models.functions import AsGeoJSON
from django.db.models import Count
from django.views import generic

# Las miniaturas del listado son de 160 px: por debajo de ~500 m y de 4 decimales
# (~10 m) el detalle ya no se distingue, y la geometría completa son varios MB.
MINIATURA_TOLERANCIA = 0.005
MINIATURA_DECIMALES = 4


class IndexView(generic.ListView):
    template_name = "index.html"
    context_object_name = 'ambitos'

    def get_queryset(self):
        # La miniatura junta los humedales del ámbito con `ST_Collect`, no con
        # `ST_Union`: no hace falta disolver los solapes para dibujar, sale mucho más
        # barato y, sobre todo, unir geometrías ya simplificadas falla (la
        # simplificación no preserva la topología y GEOS se atraganta).
        return Ambito.objects.annotate(
            n_humedales=Count('humedales'),
            geojson=AsGeoJSON(
                Collect(Simplify('humedales__geom', MINIATURA_TOLERANCIA)),
                precision=MINIATURA_DECIMALES,
            ),
        ).order_by('nombre')


class CitaRecomendadaView(generic.TemplateView):
    template_name = "cita-recomendada.html"


class PreguntasFrecuentesView(generic.TemplateView):
    template_name = "preguntas-frecuentes.html"