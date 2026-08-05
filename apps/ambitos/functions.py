from django.contrib.gis.db.models.functions import GeomOutputGeoFunc


class Simplify(GeomOutputGeoFunc):
    """ST_Simplify de PostGIS: Django no trae equivalente.

    No preserva la topología (descarta los anillos que caen por debajo de la
    tolerancia), que es justo lo que interesa para dibujar: los ámbitos son
    multipolígonos de cientos de piezas y muchas no llegan ni a un píxel.
    """

    function = 'ST_Simplify'
    geom_param_pos = (0,)
    arity = 2
