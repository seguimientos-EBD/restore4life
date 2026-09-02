from pathlib import Path

import geopandas as gpd
from django.contrib.gis.geos import GEOSGeometry
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from areas.models import StudyArea, Wetland

# GeoJSON property each field comes from. Unlike the Ramsar shapefile there is no `.dbf`
# truncating anything here, so the names are the ones DEIMS-SDR publishes.
COLUMNS = {
    'name': 'name',
    'country': 'country',
    'deims_id': 'deimsid',
}

NAME_COLUMN = COLUMNS['name']


class Command(BaseCommand):
    help = (
        'Attaches the eLTER sites of a GeoJSON to an existing study area, one per geometry '
        '(reprojected to latitude/longitude, EPSG:4326). They sit alongside the Ramsar '
        'wetlands and are analysed the same way; only the registry they come from differs.'
    )

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Name of the study area to attach them to')
        parser.add_argument('geojson', type=str, help='Path to the eLTER sites .geojson file')

    def handle(self, *args, **options):
        name = options['name']
        path = Path(options['geojson'])

        if not path.exists():
            raise CommandError(f'GeoJSON file not found: {path}')

        # The study area must already exist: the sites are a second layer over a basin
        # that `create_study_area` has framed and populated, not a study area of their own.
        try:
            study_area = StudyArea.objects.get(name=name)
        except StudyArea.DoesNotExist:
            raise CommandError(
                f'There is no study area called "{name}". Create it first with create_study_area.'
            )

        gdf = gpd.read_file(path).to_crs(4326)
        if gdf.empty:
            raise CommandError(f'The file holds no geometry at all: {path}')
        if NAME_COLUMN not in gdf.columns:
            raise CommandError(
                f'The file has no "{NAME_COLUMN}" property, which is where each site name '
                f'comes from. It has: {", ".join(gdf.columns)}'
            )

        with transaction.atomic():
            # Rebuilt wholesale, like the wetlands are, and just as narrowly: the Ramsar
            # sites of this study area are none of this command's business.
            deleted, _ = study_area.wetlands.filter(kind=Wetland.Kind.ELTER).delete()

            sites = [
                Wetland(
                    study_area=study_area,
                    kind=Wetland.Kind.ELTER,
                    geom=GEOSGeometry(memoryview(row.geometry.wkb), srid=4326),
                    **{
                        field: ('' if column not in row or row[column] is None else str(row[column]).strip())
                        for field, column in COLUMNS.items()
                    },
                )
                for _, row in gdf.iterrows()
                if row.geometry is not None and not row.geometry.is_empty
            ]
            Wetland.objects.bulk_create(sites)

        if deleted:
            self.stdout.write(f'Deleted {deleted} eLTER sites the study area already had.')
        self.stdout.write(self.style.SUCCESS(
            f'Study area "{study_area.name}" (id={study_area.pk}) now has {len(sites)} eLTER sites.'
        ))
