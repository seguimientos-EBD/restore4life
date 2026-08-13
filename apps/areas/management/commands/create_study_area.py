from pathlib import Path

import geopandas as gpd
import pandas as pd
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from areas.models import StudyArea, Wetland

# Shapefile column each wetland field comes from. The `.dbf` truncates names to ten
# characters, hence `officialna` or `area_off`.
COLUMNS = {
    'name': 'officialna',
    'fid': 'fid',
    'v_idris': 'v_idris',
    'ramsar_id': 'ramsarid',
    'iso3': 'iso3',
    'country': 'country_en',
    'official_area': 'area_off',
}

# Without `officialna` there is no way to name the wetlands; the rest may be missing.
NAME_COLUMN = COLUMNS['name']


def _value(row, column, field):
    """Casts a pandas value to the type the model expects, with nulls as None."""
    if column not in row or pd.isna(row[column]):
        return None if field != 'name' else ''
    value = row[column]
    if field in ('fid', 'v_idris', 'ramsar_id'):
        return int(value)
    if field == 'official_area':
        return float(value)
    return str(value).strip()


class Command(BaseCommand):
    help = (
        'Creates a study area with the given name and attaches the wetlands from a shapefile, '
        'one per geometry (reprojected to latitude/longitude, EPSG:4326).'
    )

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Study area name')
        parser.add_argument('shapefile', type=str, help='Path to the wetlands .shp file')
        parser.add_argument(
            '--boundary', type=str, default=None,
            help='Optional .shp/.geojson outlining the study area. The map opens framed on '
                 'it and will not pan outside it. Its features are merged into one geometry.',
        )

    def _read_boundary(self, path):
        """The study area outline as a single geometry, whatever the file holds.

        Basin files usually come as several polygons; they are dissolved into one so the
        map has a single extent to frame itself on rather than a pile of pieces.
        """
        path = Path(path)
        if not path.exists():
            raise CommandError(f'Boundary file not found: {path}')

        gdf = gpd.read_file(path).to_crs(4326)
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
        if gdf.empty:
            raise CommandError(f'The boundary file holds no geometry: {path}')

        merged = gdf.geometry.union_all() if hasattr(gdf.geometry, 'union_all') else gdf.geometry.unary_union
        self.stdout.write(f'Boundary read from {path.name}: {len(gdf)} feature(s) merged into one.')
        return GEOSGeometry(memoryview(merged.wkb), srid=4326)

    def handle(self, *args, **options):
        name = options['name']
        shapefile = Path(options['shapefile'])

        if not shapefile.exists():
            raise CommandError(f'Shapefile not found: {shapefile}')

        gdf = gpd.read_file(shapefile).to_crs(4326)
        if gdf.empty:
            raise CommandError(f'The shapefile holds no geometry at all: {shapefile}')
        if NAME_COLUMN not in gdf.columns:
            raise CommandError(
                f'The shapefile has no "{NAME_COLUMN}" column, which is where each wetland name '
                f'comes from. It has: {", ".join(gdf.columns)}'
            )

        ignored = [c for c in gdf.columns if c != 'geometry' and c not in COLUMNS.values()]
        if ignored:
            self.stdout.write(self.style.WARNING(
                f'Shapefile columns with no matching model field: {", ".join(ignored)}'
            ))

        boundary = self._read_boundary(options['boundary']) if options['boundary'] else None

        with transaction.atomic():
            # Reimporting is the norm while the shapefile is still being tuned, so the
            # study area is reused by name and its wetlands are rebuilt wholesale.
            study_area, created = StudyArea.objects.get_or_create(name=name)
            if boundary is not None:
                study_area.boundary = boundary
                study_area.save(update_fields=['boundary'])
            deleted, _ = study_area.wetlands.all().delete()

            wetlands = [
                Wetland(
                    study_area=study_area,
                    geom=GEOSGeometry(memoryview(row.geometry.wkb), srid=4326),
                    **{field: _value(row, column, field) for field, column in COLUMNS.items()},
                )
                for _, row in gdf.iterrows()
                if row.geometry is not None and not row.geometry.is_empty
            ]
            Wetland.objects.bulk_create(wetlands)

        verb = 'created' if created else 'updated'
        if deleted:
            self.stdout.write(f'Deleted {deleted} wetlands the study area already had.')
        self.stdout.write(self.style.SUCCESS(
            f'Study area "{study_area.name}" {verb} (id={study_area.pk}) with {len(wetlands)} wetlands.'
        ))
