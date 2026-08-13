from django.contrib.gis.db.models.functions import GeomOutputGeoFunc


class Simplify(GeomOutputGeoFunc):
    """PostGIS ST_Simplify: Django ships no equivalent.

    It does not preserve topology (it drops the rings that fall below the
    tolerance), which is exactly what suits drawing: study areas are multipolygons
    of hundreds of pieces and many of them do not even span a pixel.
    """

    function = 'ST_Simplify'
    geom_param_pos = (0,)
    arity = 2
