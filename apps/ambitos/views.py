import json

from django.contrib.gis.db.models.functions import AsGeoJSON
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views import View, generic

from ambitos.functions import Simplify
from ambitos.models import Ambito, Humedal

"""
El mapa de la zona de trabajo sí se puede ampliar, así que aguanta bastante más detalle que la miniatura, pero la geometría en
bruto son varios MB por ámbito.

"""
MAPA_TOLERANCIA = 0.0002
MAPA_DECIMALES = 6


def coleccion_geojson(humedales):
    """FeatureCollection con un humedal por «feature», ya simplificados.

    Se arma a mano y no con un serializador porque la geometría la trae PostGIS ya
    en GeoJSON: así solo se parsea la geometría, no se vuelve a convertir.
    """
    features = [
        {
            'type': 'Feature',
            'geometry': json.loads(humedal.geojson),
            'properties': {
                'pk': humedal.pk,
                'nombre': humedal.nombre,
                'pais': humedal.pais,
                'area_oficial': humedal.area_oficial,
            },
        }
        for humedal in humedales
        if humedal.geojson
    ]
    return {'type': 'FeatureCollection', 'features': features}


def humedales_simplificados(ambito, tolerancia=MAPA_TOLERANCIA, decimales=MAPA_DECIMALES):
    return (
        Humedal.objects.filter(ambito=ambito)
        .annotate(geojson=AsGeoJSON(Simplify('geom', tolerancia), precision=decimales))
        .defer('geom')
        .order_by('nombre')
    )


class AmbitoDetailView(generic.DetailView):
    model = Ambito
    template_name = 'ambitos/detalle.html'
    context_object_name = 'ambito'


class AmbitoGeoJSONView(View):
    """Sirve los humedales aparte para no incrustar megas de coordenadas en el HTML."""

    def get(self, request, pk):
        ambito = get_object_or_404(Ambito, pk=pk)
        coleccion = coleccion_geojson(humedales_simplificados(ambito))
        return HttpResponse(json.dumps(coleccion), content_type='application/geo+json')


class HumedalGeoJSONView(View):
    """Un solo humedal, para el mapa de la ficha del admin."""

    def get(self, request, pk):
        humedal = get_object_or_404(
            Humedal.objects.annotate(
                geojson=AsGeoJSON(Simplify('geom', MAPA_TOLERANCIA), precision=MAPA_DECIMALES),
            ),
            pk=pk,
        )
        return HttpResponse(humedal.geojson, content_type='application/geo+json')
