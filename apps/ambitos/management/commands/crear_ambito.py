from pathlib import Path

import geopandas as gpd
import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ambitos.models import Ambito, Humedal

# Columna del shapefile de la que sale cada campo del humedal. El `.dbf` recorta los
# nombres a diez caracteres, de ahí `officialna` o `area_off`.
COLUMNAS = {
    'nombre': 'officialna',
    'fid': 'fid',
    'v_idris': 'v_idris',
    'ramsarid': 'ramsarid',
    'iso3': 'iso3',
    'pais': 'country_en',
    'area_oficial': 'area_off',
}

# Sin `officialna` no hay forma de nombrar los humedales; el resto puede faltar.
COLUMNA_NOMBRE = COLUMNAS['nombre']


def _valor(fila, columna, campo):
    """Pasa un valor de pandas al tipo que espera el modelo, con los nulos a None."""
    if columna not in fila or pd.isna(fila[columna]):
        return None if campo != 'nombre' else ''
    valor = fila[columna]
    if campo in ('fid', 'v_idris', 'ramsarid'):
        return int(valor)
    if campo == 'area_oficial':
        return float(valor)
    return str(valor).strip()


class Command(BaseCommand):
    help = (
        'Crea un Ámbito con el nombre indicado y le cuelga los humedales de un shapefile, '
        'uno por geometría (se reproyecta a latitud/longitud, EPSG:4326).'
    )

    def add_arguments(self, parser):
        parser.add_argument('nombre', type=str, help='Nombre del ámbito')
        parser.add_argument('shapefile', type=str, help='Ruta al fichero .shp de humedales')

    def handle(self, *args, **options):
        nombre = options['nombre']
        shapefile = Path(options['shapefile'])

        if not shapefile.exists():
            raise CommandError(f'No se encuentra el shapefile: {shapefile}')

        gdf = gpd.read_file(shapefile).to_crs(4326)
        if gdf.empty:
            raise CommandError(f'El shapefile no contiene ninguna geometría: {shapefile}')
        if COLUMNA_NOMBRE not in gdf.columns:
            raise CommandError(
                f'El shapefile no trae la columna «{COLUMNA_NOMBRE}», de la que sale el nombre '
                f'de cada humedal. Trae: {", ".join(gdf.columns)}'
            )

        ignoradas = [c for c in gdf.columns if c != 'geometry' and c not in COLUMNAS.values()]
        if ignoradas:
            self.stdout.write(self.style.WARNING(
                f'Columnas del shapefile que no tienen campo en el modelo: {", ".join(ignoradas)}'
            ))

        with transaction.atomic():
            # Reimportar es lo normal mientras se afina el shapefile, así que el ámbito
            # se reutiliza por nombre y sus humedales se rehacen enteros.
            ambito, creado = Ambito.objects.get_or_create(nombre=nombre)
            borrados, _ = ambito.humedales.all().delete()

            humedales = [
                Humedal(
                    ambito=ambito,
                    geom=GEOSGeometry(memoryview(fila.geometry.wkb), srid=4326),
                    **{campo: _valor(fila, columna, campo) for campo, columna in COLUMNAS.items()},
                )
                for _, fila in gdf.iterrows()
                if fila.geometry is not None and not fila.geometry.is_empty
            ]
            Humedal.objects.bulk_create(humedales)

        verbo = 'creado' if creado else 'actualizado'
        if borrados:
            self.stdout.write(f'Se han borrado {borrados} humedales que ya tenía el ámbito.')
        self.stdout.write(self.style.SUCCESS(
            f'Ámbito "{ambito.nombre}" {verbo} (id={ambito.pk}) con {len(humedales)} humedales.'
        ))