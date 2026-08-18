"""Hydroperiod computation on Earth Engine.

Ported from `diego/restore4life/app.py` (Diego García Díaz), which is an ipywidgets
widget for notebooks: what is left here is only the computation logic, with no
interface and no state kept alive between calls. The engine is still `ndvi2gif`.

Almost none of this actually computes anything: Earth Engine is lazy and what these
functions return are `ee.Image` graphs. EE triggers the computation when it is asked
for tiles (`tile_url`), for concrete values (`zonal_statistics`) or for an export.
That is why rebuilding the graph on every request comes cheap, which is what lets us
do without the state the widget used to keep in the kernel.

Every function here assumes Earth Engine is already initialized for the current user;
`earthengine.services.ee_initialize_for_user` takes care of that.
"""

import io
import json
import re
import tempfile
import unicodedata
import zipfile
from datetime import date
from pathlib import Path

import ee
import geopandas as gpd
from ndvi2gif import HydroperiodAnalyzer, NdviSeasonality

# --------------------------------------------------------------------------- #
# Constants                                                                    #
# --------------------------------------------------------------------------- #

SENSORS = ('S2', 'Landsat', 'MODIS')

# Day the hydrological year starts, (month, day). It is `HydroperiodAnalyzer`'s
# default, but it is passed explicitly so that ndvi2gif and the form cannot disagree
# on when a cycle closes.
HYDROLOGICAL_YEAR_START = (9, 1)

# First year with data for each sensor
SENSOR_MIN_YEAR = {'S2': 2017, 'Landsat': 1984, 'MODIS': 2000}

# Water indices available per sensor
SENSOR_WATER_INDICES = {
    'S2': ('mndwi', 'ndwi', 'awei', 'aweinsh', 'wi2015'),
    'Landsat': ('mndwi', 'ndwi', 'awei', 'aweinsh', 'wi2015'),
    'MODIS': ('mndwi', 'ndwi'),
}

# Bands produced by computing a hydrological cycle
BANDS = ('normalized', 'hydroperiod', 'valid_days', 'first_flood_doy', 'last_flood_doy', 'irt')

DEM_SOURCES = ('MERIT', 'HYBRID_30M')

ANOMALY_REFERENCES = ('period', 'historical')

# Native resolution of each sensor, to sample statistics without oversampling
SENSOR_SCALE = {'S2': 10, 'Landsat': 30, 'MODIS': 500}
TWI_SCALE = 90

DEFAULT_DRIVE_FOLDER = 'restore4life_hydroperiod'

# Scales offered for exports, in metres. The finest ones only make sense for S2.
EXPORT_SCALES = (10, 20, 30, 100, 250, 500)

# Limits on the geometries uploaded for zonal statistics. `zonal_statistics` waits on
# `getInfo`, which blocks the worker and is capped by Earth Engine anyway, so past this
# many features the honest answer is to export to Drive instead of timing out.
SYNC_FEATURE_LIMIT = 1000
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
# A shapefile of a few hundred KB can zip down to almost nothing, so the guard has to
# be on what comes out, not on what came in.
MAX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024

# Columns a name is looked for in, in this order, when reading uploaded geometries.
NAME_COLUMN_CANDIDATES = (
    'officialna', 'name', 'Name', 'NAME', 'nombre', 'NOMBRE',
    'site', 'Site', 'SITE', 'wetland', 'id', 'ID',
)

# Simplification of the wetland geometry before sending it to Earth Engine. Wetlands
# come from shapefiles with thousands of vertices and EE charges dearly for them on
# every request; ~10 m is the finest pixel we analyse (Sentinel-2).
ROI_TOLERANCE = 0.0001

# A shape drawn by hand has a handful of vertices; anything near this many means the
# geometry did not come from the map's drawing tools.
MAX_DRAWN_VERTICES = 5000

# Visualization palettes per band/product
VIS = {
    'hydroperiod': {
        'min': 0, 'max': 365,
        'palette': ['ffffff', 'ffffcc', 'c7e9b4', '7fcdbb', '41b6c4', '1d91c0', '225ea8', '0c2c84'],
    },
    'normalized': {
        'min': 0, 'max': 365,
        'palette': ['ffffff', 'ffffcc', 'c7e9b4', '7fcdbb', '41b6c4', '1d91c0', '225ea8', '0c2c84'],
    },
    'valid_days': {
        'min': 0, 'max': 365,
        'palette': ['f7fbff', 'deebf7', '9ecae1', '3182bd', '08306b'],
    },
    'first_flood_doy': {
        'min': 0, 'max': 365,
        'palette': ['440154', '31688e', '35b779', 'fde725'],
    },
    'last_flood_doy': {
        'min': 0, 'max': 365,
        'palette': ['fde725', '35b779', '31688e', '440154'],
    },
    'irt': {
        'min': 0, 'max': 1,
        'palette': ['d73027', 'fc8d59', 'fee08b', 'd9ef8b', '91cf60', '1a9850'],
    },
    'mean_hydroperiod': {
        'min': 0, 'max': 365,
        'palette': ['ffffff', 'ffffcc', 'c7e9b4', '7fcdbb', '41b6c4', '1d91c0', '225ea8', '0c2c84'],
    },
    # Diverging around zero, dry to wet: the sign is a number of flooded days above or
    # below the reference, so the wet end is blue. Red-green would have read as
    # bad-good, which is not what a longer hydroperiod means, and is besides the one
    # pair that colour-blind readers cannot separate.
    'anomaly': {
        'min': -180, 'max': 180,
        'palette': ['67001f', 'b2182b', 'd6604d', 'f4a582', 'f7f7f7', '92c5de', '4393c3', '2166ac', '053061'],
    },
    'twi': {
        'min': 2, 'max': 20,
        'palette': ['f7fbff', 'deebf7', 'c6dbef', '9ecae1', '6baed6', '4292c6', '2171b5', '08519c', '08306b'],
    },
}


# --------------------------------------------------------------------------- #
# Region of interest                                                           #
# --------------------------------------------------------------------------- #

def wetland_roi(wetland, tolerance=ROI_TOLERANCE):
    """Turns a `Wetland`'s geometry into the `ee.Geometry` to analyse.

    With `tolerance=None` the geometry is sent whole, which for the large wetlands
    means several hundred KB per request.
    """
    geom = wetland.geom.simplify(tolerance, preserve_topology=True) if tolerance else wetland.geom
    return ee.Geometry(json.loads(geom.geojson))


def drawn_roi(geojson):
    """Turns a shape drawn on the map into the `ee.Geometry` to analyse.

    This one arrives from the browser rather than from the database, so it is checked
    before Earth Engine ever sees it: only areal geometries, a bounded number of
    vertices, and coordinates that are actually longitude/latitude.
    """
    try:
        geometry = json.loads(geojson)
    except (TypeError, ValueError):
        raise ValueError('The drawn area is not valid GeoJSON.')

    if not isinstance(geometry, dict):
        raise ValueError('The drawn area is not valid GeoJSON.')
    # Leaflet hands back a Feature; Earth Engine wants the geometry itself.
    if geometry.get('type') == 'Feature':
        geometry = geometry.get('geometry') or {}

    if geometry.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('Draw a polygon or a rectangle: a hydroperiod needs an area.')

    vertices = _count_vertices(geometry.get('coordinates'))
    if not vertices:
        raise ValueError('The drawn area has no coordinates.')
    if vertices > MAX_DRAWN_VERTICES:
        raise ValueError(f'The drawn area has too many vertices (limit {MAX_DRAWN_VERTICES}).')

    return ee.Geometry(geometry)


def _count_vertices(coordinates, depth=0):
    """Walks the nested coordinate lists, validating each position on the way."""
    if depth > 4 or not isinstance(coordinates, (list, tuple)):
        raise ValueError('The drawn area is malformed.')

    # A position is the innermost list: two or three numbers.
    if coordinates and all(isinstance(value, (int, float)) for value in coordinates):
        if len(coordinates) < 2:
            raise ValueError('The drawn area is malformed.')
        longitude, latitude = coordinates[0], coordinates[1]
        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise ValueError('The drawn area falls outside longitude/latitude bounds.')
        return 1

    return sum(_count_vertices(item, depth + 1) for item in coordinates)


# --------------------------------------------------------------------------- #
# Hydroperiod                                                                  #
# --------------------------------------------------------------------------- #

def last_closed_cycle(today=None):
    """Year the last already-finished hydrological cycle started in.

    The Y/Y+1 cycle runs from 1 September of Y to 1 September of Y+1, so until that
    date the cycle that started last year is still open and its flooded days do not
    yet add up to a full year.
    """
    today = today or date.today()
    month, day = HYDROLOGICAL_YEAR_START
    return today.year - 1 if (today.month, today.day) >= (month, day) else today.year - 2


def validate_parameters(sensor, start_year, end_year, index):
    """Checks the sensor/years/index combination and returns a message or None."""
    if sensor not in SENSORS:
        return f'Unknown sensor: {sensor}.'
    if start_year > end_year:
        return 'The start year must be earlier than or equal to the end year.'
    if start_year < SENSOR_MIN_YEAR[sensor]:
        return f'{sensor} has no data before {SENSOR_MIN_YEAR[sensor]}.'
    if index not in SENSOR_WATER_INDICES[sensor]:
        return f'The {index} index is not available for {sensor}.'
    return None


def compute_cycles(roi, sensor, start_year, end_year, index, threshold, max_clouds=100):
    """Builds the analyzer and the hydrological cycles for the period.

    Returns `(analyzer, cycles)`, where `cycles` is `{year: ee.Image}` with one cycle
    per hydrological year. The analyzer is needed afterwards for the anomalies and the
    IRT, and is rebuilt identically from these very same parameters.
    """
    error = validate_parameters(sensor, start_year, end_year, index)
    if error:
        raise ValueError(error)

    series = NdviSeasonality(
        roi=roi,
        sat=sensor,
        start_year=start_year,
        end_year=end_year,
        max_cloud_cover=max_clouds,
    )
    analyzer = HydroperiodAnalyzer(series, hydrological_year_start=HYDROLOGICAL_YEAR_START)
    return analyzer, analyzer.compute_all_cycles(index=index, threshold=threshold)


def compute_irt(analyzer):
    """Per-pixel IRT (temporal regularity index) image."""
    return analyzer.compute_irt_image()


def compute_anomalies(analyzer, cycles, reference='period'):
    """Anomalies relative to the period mean or to the historical archive mean.

    Returns `{'mean': ee.Image, 'anomalies': {year: ee.Image}}`.
    """
    if reference not in ANOMALY_REFERENCES:
        raise ValueError(f'Unknown reference: {reference}.')
    return analyzer.compute_anomalies(cycles=cycles, reference=reference)


# --------------------------------------------------------------------------- #
# TWI                                                                          #
# --------------------------------------------------------------------------- #

def compute_twi(roi, dem_source='MERIT'):
    """Topographic wetness index: TWI = ln(a / tan β).

    `a` is the upstream drainage area per unit contour length and `β` the local slope.

    - `MERIT`: MERIT Hydro v1.0.1 (~90 m) for both slope and accumulation, internally
      consistent.
    - `HYBRID_30M`: NASADEM (30 m) for the slope and MERIT's `upa` reprojected for the
      accumulation. The accumulation is still 90 m: filling sinks and routing D8 at
      30 m on the fly is not viable in GEE.
    """
    if dem_source not in DEM_SOURCES:
        raise ValueError(f'Unknown DEM source: {dem_source}.')

    merit = ee.Image('MERIT/Hydro/v1_0_1')
    upa = merit.select('upa')  # upstream drainage area, km²

    elevation = ee.Image('NASA/NASADEM_HGT/001').select('elevation') if dem_source == 'HYBRID_30M' \
        else merit.select('elv')

    slope = ee.Terrain.slope(elevation)
    tangent = slope.multiply(ee.Number(3.141592653589793).divide(180)).tan().max(0.001)

    # Specific catchment area: upa (km²) → m², divided by the contour length,
    # approximated as the square root of the pixel area in the local projection.
    cell_width = ee.Image.pixelArea().sqrt()
    area = upa.multiply(1e6).divide(cell_width)

    return area.divide(tangent).log().rename('twi').clip(roi)


# --------------------------------------------------------------------------- #
# Visualization                                                                #
# --------------------------------------------------------------------------- #

def pixel_value(image, longitude, latitude, scale):
    """Every band of `image` at one point, as `{band: value}`.

    Like `zonal_statistics`, this one waits on Earth Engine instead of handing the
    browser a URL, but it samples a single pixel so it comes back quickly. Bands the
    product masked out come back as None, which is the honest answer: the pixel was
    never flooded rather than flooded for zero days.
    """
    point = ee.Geometry.Point([longitude, latitude])
    values = image.reduceRegion(reducer=ee.Reducer.first(), geometry=point, scale=scale).getInfo()
    return values or {}


def tile_url(image, vis_key):
    """XYZ tile URL to draw the image on Leaflet.

    It is what `Map.addLayer` used to do under the hood. The response is immediate: EE
    computes nothing until the browser asks it for each tile.
    """
    return image.getMapId(VIS[vis_key])['tile_fetcher'].url_format


# --------------------------------------------------------------------------- #
# Uploaded geometries                                                          #
# --------------------------------------------------------------------------- #

def _name_column(gdf):
    """First plausible name column in `gdf`, falling back to the first one."""
    for column in NAME_COLUMN_CANDIDATES:
        if column in gdf.columns:
            return column
    return gdf.columns[0]


def _shapefile_from_zip(content):
    """Reads the first shapefile inside a ZIP bundle.

    The members are checked before extracting: unlike the notebook widget this port
    comes from, here the ZIP arrives from a browser, so a member named `../../etc/x`
    would write outside the temporary directory.
    """
    with zipfile.ZipFile(io.BytesIO(content)) as bundle:
        if sum(item.file_size for item in bundle.infolist()) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError('The ZIP expands to too much data.')

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir).resolve()
            for item in bundle.infolist():
                target = (root / item.filename).resolve()
                if not target.is_relative_to(root):
                    raise ValueError(f'The ZIP holds an unsafe path: {item.filename}')
            bundle.extractall(tmpdir)

            shapefiles = sorted(root.glob('**/*.shp'))
            if not shapefiles:
                raise ValueError('No .shp file found inside the ZIP.')
            return gpd.read_file(shapefiles[0])


def read_geometries(upload):
    """Parses an uploaded file into the collection to compute statistics over.

    Accepts `.geojson`, `.json` and `.zip` (a shapefile bundle), the same three the
    notebook widget took. Returns `(collection, is_point, count, name_column)`:
    whether the geometries are points decides the reducer, and the count decides
    whether it is worth waiting for the result at all.
    """
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValueError(f'The file exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')

    name = upload.name.lower()
    content = upload.read()

    if not name.endswith(('.geojson', '.json', '.zip')):
        raise ValueError(f'Unsupported file type: {upload.name}. Use .geojson, .json or .zip.')

    # A malformed file is the user's to fix, not a server fault, so whatever geopandas
    # or zipfile throws on the way in is reported as a bad request.
    try:
        if name.endswith('.zip'):
            gdf = _shapefile_from_zip(content)
        else:
            gdf = gpd.read_file(io.BytesIO(content))
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f'{upload.name} could not be read: {error}') from error

    if gdf.empty:
        raise ValueError('The file holds no geometry at all.')

    # A GeoJSON with no CRS declared is EPSG:4326 by specification; anything else has
    # to say so, and gets reprojected.
    gdf = gdf.set_crs(4326) if gdf.crs is None else gdf.to_crs(4326)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]
    if gdf.empty:
        raise ValueError('Every geometry in the file is empty.')

    is_point = bool(gdf.geometry.geom_type.isin(('Point', 'MultiPoint')).all())
    collection = ee.FeatureCollection(json.loads(gdf.to_json()))
    return collection, is_point, len(gdf), _name_column(gdf)


# --------------------------------------------------------------------------- #
# Zonal statistics                                                             #
# --------------------------------------------------------------------------- #

def reducer(is_point):
    """Pixel value for points; the usual summary for polygons."""
    if is_point:
        return ee.Reducer.first()
    return (ee.Reducer.mean()
            .combine(ee.Reducer.median(), sharedInputs=True)
            .combine(ee.Reducer.min(), sharedInputs=True)
            .combine(ee.Reducer.max(), sharedInputs=True)
            .combine(ee.Reducer.stdDev(), sharedInputs=True)
            .combine(ee.Reducer.count(), sharedInputs=True))


def default_scale(product, sensor):
    """Sampling resolution matching the product being measured."""
    return TWI_SCALE if product == 'twi' else SENSOR_SCALE.get(sensor, 30)


def zonal_statistics(image, collection, scale, is_point):
    """Per-feature statistics over `collection`, as a list of dictionaries.

    It is the only function in the module that waits on Earth Engine (`getInfo`), so it
    blocks for as long as the computation takes.
    """
    result = image.reduceRegions(collection=collection, reducer=reducer(is_point), scale=scale)
    rows = []
    for element in result.getInfo().get('features', []):
        properties = dict(element.get('properties', {}))
        properties['_fid'] = element.get('id', '')
        rows.append(properties)
    return rows


# --------------------------------------------------------------------------- #
# Export to Drive                                                              #
# --------------------------------------------------------------------------- #

def task_name(*parts):
    """Joins the parts into a name Earth Engine will accept for a task.

    EE takes only letters, digits, and a handful of punctuation, and rejects the whole
    export if the name breaks the rule — so this has to run over anything coming from
    the data, wetland names above all: they arrive from the shapefiles with accents,
    parentheses and spaces in them.

    Accented letters are folded to their ASCII base first, so `Kopački rit` becomes
    `Kopacki_rit` rather than `Kopa_ki_rit`.
    """
    joined = '_'.join(str(part) for part in parts if part)
    folded = unicodedata.normalize('NFKD', joined).encode('ascii', 'ignore').decode()
    return re.sub(r'[^A-Za-z0-9_-]+', '_', folded).strip('_')[:100]


def export_image(image, roi, description, scale, folder=DEFAULT_DRIVE_FOLDER):
    """Starts the export of an image as GeoTIFF and returns the task."""
    task = ee.batch.Export.image.toDrive(
        image=image,
        description=description,
        folder=folder,
        fileNamePrefix=description,
        region=roi,
        scale=scale,
        maxPixels=1e13,
    )
    task.start()
    return task


def export_cycles(analyzer, cycles, label, scale, folder=DEFAULT_DRIVE_FOLDER):
    """Starts one export per hydrological cycle and returns their descriptions."""
    descriptions = []
    for year, image in cycles.items():
        description = task_name('hydroperiod', label, year, year + 1)
        analyzer.export_to_drive(image=image, folder=folder, description=description, scale=scale)
        descriptions.append(description)
    return descriptions


def export_table(image, collection, scale, is_point, description, folder=DEFAULT_DRIVE_FOLDER):
    """Exports the zonal statistics as CSV, without waiting for the result.

    It is the alternative to `zonal_statistics` when the collection is large: EE works
    it out on its own and drops the file in Drive.
    """
    result = image.reduceRegions(collection=collection, reducer=reducer(is_point), scale=scale)
    task = ee.batch.Export.table.toDrive(
        collection=result,
        description=description,
        folder=folder,
        fileNamePrefix=description,
        fileFormat='CSV',
    )
    task.start()
    return task
