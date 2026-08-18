"""Endpoints of the hydroperiod panel: map tiles, zonal statistics and Drive exports.

None of them keeps anything between requests: every call rebuilds the Earth Engine
graph from the form parameters. It comes cheap because EE is lazy — `getMapId()`
returns a tile URL without computing a single pixel, and the real computation is
triggered by the browser one tile at a time.

The three endpoints share how they turn parameters into an image (`PRODUCTS`) and how
they report Earth Engine's failure modes (`ee_json`), so statistics and exports work on
whatever the map is showing without a product list of their own.
"""

import logging
from collections import namedtuple

import ee
from areas.models import Wetland
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from earthengine.services import NotConnected, ee_initialize_for_user
from google.auth.exceptions import RefreshError

from hydroperiod import services
from hydroperiod.forms import (
    AnomaliesForm, ExportForm, HydroperiodForm, PointForm, StatsForm, TwiForm,
)

logger = logging.getLogger(__name__)


def hydroperiod_layer(roi, data):
    analyzer, cycles = services.compute_cycles(
        roi, data['sensor'], data['start_year'], data['end_year'],
        data['index'], data['threshold'], data['max_clouds'],
    )
    if data['band'] == 'irt':
        return services.compute_irt(analyzer), 'irt', 'IRT'

    year = data['year']
    if year not in cycles:
        raise ValueError(f'The {year}/{year + 1} cycle was never computed.')
    return cycles[year].select(data['band']), data['band'], f'{data["band"]} {year}/{year + 1}'


def anomalies_layer(roi, data):
    analyzer, cycles = services.compute_cycles(
        roi, data['sensor'], data['start_year'], data['end_year'],
        data['index'], data['threshold'], data['max_clouds'],
    )
    anomalies = services.compute_anomalies(analyzer, cycles, data['reference'])

    if data['layer'] == 'mean':
        return anomalies['mean'], 'mean_hydroperiod', 'Mean hydroperiod'

    year = data['anomaly_year']
    if year not in anomalies['anomalies']:
        raise ValueError(f'The {year}/{year + 1} cycle was never computed.')
    return anomalies['anomalies'][year], 'anomaly', f'Anomaly {year}/{year + 1}'


def twi_layer(roi, data):
    return services.compute_twi(roi, data['dem_source']), 'twi', 'TWI'


# Each product: the form that validates its parameters and the function that builds the image.
PRODUCTS = {
    'hydroperiod': (HydroperiodForm, hydroperiod_layer),
    'anomalies': (AnomaliesForm, anomalies_layer),
    'twi': (TwiForm, twi_layer),
}

# Reducer outputs, in the order they read best in a table. Anything else a feature
# carried in from the uploaded file comes after them.
STAT_COLUMNS = ('first', 'mean', 'median', 'min', 'max', 'stdDev', 'count')


def _first_error(form):
    for errors in form.errors.values():
        return errors[0]
    return 'Invalid parameters.'


def ee_json(request, build, action):
    """Runs `build()` with Earth Engine initialized, as a JSON response.

    Every Earth Engine failure that the user can actually do something about is told
    apart here: a missing connection, an expired one and a computation that does not
    fit each need a different fix, and a generic 502 for all three would hide that.
    """
    try:
        ee_initialize_for_user(request.user)
        return JsonResponse(build())
    except NotConnected:
        return JsonResponse({'error': 'You have no Earth Engine account connected.'}, status=409)
    except RefreshError:
        # The stored token no longer works: it is not a computation failure and it is
        # fixed by authorizing again, so it is worth saying so separately.
        logger.warning('Earth Engine credentials expired for %s', request.user)
        return JsonResponse(
            {'error': 'Your Earth Engine authorization has expired: connect the account again.'},
            status=409,
        )
    except ValueError as error:
        return JsonResponse({'error': str(error)}, status=400)
    except ee.EEException as error:
        # The memory limit trips on long periods over large wetlands, and is fixed by
        # asking for less: that deserves saying instead of a generic error.
        logger.warning('Earth Engine rejected %s: %s', action, error)
        if 'memory' in str(error).lower():
            return JsonResponse({'error': (
                'The computation does not fit in Earth Engine: shorten the year range '
                'or use a coarser sensor.'
            )}, status=400)
        return JsonResponse({'error': f'Earth Engine rejected the computation: {error}'}, status=502)
    except Exception:
        logger.exception('Error while %s', action)
        return JsonResponse({'error': f'Earth Engine could not complete: {action}.'}, status=502)


# What every endpoint needs once the parameters have been turned into an image. The ROI
# travels with it because building it is the one costly step here, and an export would
# otherwise pay for it twice. `label` names the area in exports and messages, whether it
# came from the database or from the map.
Product = namedtuple('Product', 'roi label image vis_key name data')


class ProductView(LoginRequiredMixin, View):
    """Shared plumbing for the endpoints that work on a product over an area."""

    def resolve_roi(self, parameters):
        """The area to analyse: a wetland from the database, or a shape drawn on the map.

        The two are mutually exclusive and the drawing wins, because it is the more
        deliberate act: you have to draw it, whereas a wetland may just be left over in
        the dropdown from a previous run.
        """
        drawn = parameters.get('geometry')
        if drawn:
            return services.drawn_roi(drawn), 'drawn area'

        wetland_pk = parameters.get('wetland')
        if not wetland_pk:
            raise ValueError('Pick a wetland or draw an area on the map.')

        wetland = get_object_or_404(Wetland, pk=wetland_pk)
        return services.wetland_roi(wetland), wetland.name

    def resolve_product(self, request):
        """Builds the selected product, or raises `ValueError` if the parameters do not.

        The product forms are the same ones the map layers use, so statistics and
        exports measure exactly what is on screen instead of re-deriving it.
        """
        parameters = request.POST if request.method == 'POST' else request.GET
        product = PRODUCTS.get(parameters.get('product'))
        if product is None:
            raise ValueError('Unknown product.')
        form_class, build_layer = product

        form = form_class(parameters)
        if not form.is_valid():
            raise ValueError(_first_error(form))

        roi, label = self.resolve_roi(parameters)
        image, vis_key, name = build_layer(roi, form.cleaned_data)
        return Product(roi, label, image, vis_key, name, form.cleaned_data)


class TilesView(ProductView):
    """Returns the XYZ URL with which Leaflet draws the product over the wetland."""

    def get(self, request):
        def build():
            product = self.resolve_product(request)
            return {
                'url': services.tile_url(product.image, product.vis_key),
                'name': product.name,
                'legend': services.VIS[product.vis_key],
            }

        return ee_json(request, build, f'computing the {request.GET.get("product")} layer')


class InspectView(ProductView):
    """The value of the displayed product at one point on the map.

    The browser sends back the very parameters that produced the layer it is showing, so
    the image sampled here is the same one drawn there — not whatever the panel happens
    to have selected by now.
    """

    def get(self, request):
        point_form = PointForm(request.GET)
        if not point_form.is_valid():
            return JsonResponse({'error': _first_error(point_form)}, status=400)

        def build():
            product = self.resolve_product(request)
            longitude = point_form.cleaned_data['longitude']
            latitude = point_form.cleaned_data['latitude']
            scale = services.default_scale(request.GET.get('product'), product.data.get('sensor'))
            values = services.pixel_value(product.image, longitude, latitude, scale)
            return {
                'product': product.name,
                'scale': scale,
                'longitude': longitude,
                'latitude': latitude,
                'values': values,
            }

        return ee_json(request, build, 'reading the pixel value')


class StatsView(ProductView):
    """Per-feature statistics of the selected product over uploaded geometries.

    This is the one endpoint that waits on Earth Engine rather than handing the browser
    a URL, so it is also the one that can time out: past `SYNC_FEATURE_LIMIT` features
    it refuses and points at the Drive export instead.
    """

    def post(self, request):
        stats_form = StatsForm(request.POST, request.FILES)
        if not stats_form.is_valid():
            return JsonResponse({'error': _first_error(stats_form)}, status=400)

        def build():
            product = self.resolve_product(request)
            collection, is_point, count, name_column = services.read_geometries(
                stats_form.cleaned_data['geometries'],
            )
            scale = stats_form.cleaned_data.get('scale') or services.default_scale(
                request.POST.get('product'), product.data.get('sensor'),
            )
            geometry = 'points' if is_point else 'polygons'

            if stats_form.cleaned_data['to_drive']:
                folder = stats_form.cleaned_data['folder']
                description = services.task_name('stats', product.name, product.label)
                services.export_table(product.image, collection, scale, is_point, description, folder)
                return {
                    'product': product.name, 'scale': scale, 'geometry': geometry,
                    'features': count, 'folder': folder, 'tasks': [description],
                }

            if count > services.SYNC_FEATURE_LIMIT:
                raise ValueError(
                    f'{count} features is too many to compute while you wait '
                    f'(the limit is {services.SYNC_FEATURE_LIMIT}). Use "Send to Drive" instead.'
                )

            rows = services.zonal_statistics(product.image, collection, scale, is_point)
            return {
                'product': product.name,
                'scale': scale,
                'geometry': geometry,
                'columns': self.columns(rows, name_column),
                'rows': rows,
            }

        return ee_json(request, build, 'computing zonal statistics')

    @staticmethod
    def columns(rows, name_column):
        """Column order: what identifies the feature first, then the reducer outputs."""
        present = {key for row in rows for key in row}
        ordered = [name_column] if name_column in present else []
        ordered += [column for column in STAT_COLUMNS if column in present]
        ordered += sorted(present - set(ordered) - {'_fid'})
        return ordered


class ExportView(ProductView):
    """Starts Drive exports on the user's own Earth Engine account.

    Earth Engine queues the tasks and runs them on its own time, so this returns as
    soon as they are accepted: the files show up in Drive later, and progress is
    followed from the Earth Engine task manager.
    """

    def post(self, request):
        export_form = ExportForm(request.POST)
        if not export_form.is_valid():
            return JsonResponse({'error': _first_error(export_form)}, status=400)

        folder = export_form.cleaned_data['folder']
        scale = export_form.cleaned_data['export_scale']

        def build():
            if export_form.cleaned_data['target'] == 'cycles':
                return self.export_cycles(request, folder, scale)
            return self.export_product(request, folder, scale)

        return ee_json(request, build, 'starting the Drive export')

    def export_cycles(self, request, folder, scale):
        """One GeoTIFF per hydrological cycle of the period, as the notebook widget did."""
        form = HydroperiodForm(request.POST)
        if not form.is_valid():
            raise ValueError(_first_error(form))

        roi, label = self.resolve_roi(request.POST)
        data = form.cleaned_data
        analyzer, cycles = services.compute_cycles(
            roi, data['sensor'], data['start_year'], data['end_year'],
            data['index'], data['threshold'], data['max_clouds'],
        )
        descriptions = services.export_cycles(analyzer, cycles, label, scale, folder)
        return {'folder': folder, 'scale': scale, 'tasks': descriptions}

    def export_product(self, request, folder, scale):
        """A single GeoTIFF of whatever product is selected — TWI, IRT, an anomaly or a band."""
        product = self.resolve_product(request)
        description = services.task_name(product.name, product.label)
        services.export_image(product.image, product.roi, description, scale, folder)
        return {'folder': folder, 'scale': scale, 'tasks': [description]}
