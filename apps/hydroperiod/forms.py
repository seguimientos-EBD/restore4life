"""Validation of the hydroperiod panel parameters.

One form per product, because each rebuilds a different Earth Engine graph, but they
all share the time-series parameters: the panel is a single `<form>` and each tab
sends the same common block plus its own fields.

The dropdown labels live here too, since they are interface and have no place in
`services.py`.
"""

from datetime import date

from django import forms

from hydroperiod import services

SENSOR_LABELS = {
    'S2': 'Sentinel-2 (10 m, from 2017)',
    'Landsat': 'Landsat (30 m, from 1984)',
    'MODIS': 'MODIS (500 m, from 2000)',
}

INDEX_LABELS = {
    'mndwi': 'MNDWI',
    'ndwi': 'NDWI',
    'awei': 'AWEI',
    'aweinsh': 'AWEI (no shadow)',
    'wi2015': 'WI2015',
}

BAND_LABELS = {
    'normalized': 'Normalized hydroperiod',
    'hydroperiod': 'Hydroperiod (flooded days)',
    'valid_days': 'Days with valid data',
    'first_flood_doy': 'First flood day',
    'last_flood_doy': 'Last flood day',
    'irt': 'IRT (temporal regularity)',
}

REFERENCE_LABELS = {
    'period': 'Mean of the selected period',
    'historical': 'Historical mean (full archive)',
}

DEM_LABELS = {
    'MERIT': 'MERIT Hydro (~90 m)',
    'HYBRID_30M': 'Hybrid 30 m (NASADEM slope)',
}

ANOMALY_LAYER_LABELS = {
    'mean': 'Reference mean hydroperiod',
    'anomaly': 'Anomaly of one cycle',
}

# Every index of every sensor: which one is valid for which is decided by
# `services.validate_parameters`, which is the one that knows the table.
INDICES = sorted({index for indices in services.SENSOR_WATER_INDICES.values() for index in indices})

MIN_YEAR = min(services.SENSOR_MIN_YEAR.values())


def _choices(codes, labels):
    return [(code, labels[code]) for code in codes]


def _current_year():
    return date.today().year


def _default_end_year():
    """The last closed hydrological cycle, which is not simply last year's.

    Since the hydrological year starts on 1 September, between January and August the
    cycle that started last year is still half-way through.
    """
    return services.last_closed_cycle()


def _default_start_year():
    return _default_end_year() - 4


class ParametersForm(forms.Form):
    """What defines the time series, shared by hydroperiod and anomalies."""

    sensor = forms.ChoiceField(
        label='Sensor',
        choices=_choices(services.SENSORS, SENSOR_LABELS),
        initial='S2',
    )
    start_year = forms.IntegerField(
        label='Start year',
        min_value=MIN_YEAR,
        max_value=_current_year,
        initial=_default_start_year,
    )
    end_year = forms.IntegerField(
        label='End year',
        min_value=MIN_YEAR,
        max_value=_current_year,
        initial=_default_end_year,
    )
    index = forms.ChoiceField(
        label='Water index',
        choices=_choices(INDICES, INDEX_LABELS),
        initial='mndwi',
    )
    threshold = forms.FloatField(
        label='Threshold',
        min_value=-1,
        max_value=1,
        initial=0,
        help_text='Above this value there is water.',
        widget=forms.NumberInput(attrs={'step': '0.01'}),
    )
    max_clouds = forms.IntegerField(
        label='Max cloud cover (%)',
        min_value=0,
        max_value=100,
        initial=20,
    )

    def clean(self):
        data = super().clean()
        # `validate_parameters` cross-checks sensor, years and index, so it needs all three.
        if {'sensor', 'start_year', 'end_year', 'index'} <= data.keys():
            error = services.validate_parameters(
                data['sensor'], data['start_year'], data['end_year'], data['index'],
            )
            if error:
                raise forms.ValidationError(error)
        return data

    def validate_cycle(self, data, field):
        """Checks that the chosen cycle is among those about to be computed."""
        year = data.get(field)
        if year is None or 'start_year' not in data or 'end_year' not in data:
            return
        if not data['start_year'] <= year <= data['end_year']:
            self.add_error(field, 'The chosen cycle falls outside the period.')


class HydroperiodForm(ParametersForm):
    band = forms.ChoiceField(
        label='Layer',
        choices=_choices(services.BANDS, BAND_LABELS),
        # The normalized band is the one to open on: it corrects the flooded-day count
        # for how many valid observations the pixel actually had, so it is comparable
        # between pixels and between years, which the raw count is not.
        initial='normalized',
    )
    year = forms.IntegerField(label='Hydrological cycle', initial=_default_end_year)

    def clean(self):
        data = super().clean()
        # The IRT summarizes the whole period, so it does not hang off a single cycle.
        if data.get('band') != 'irt':
            self.validate_cycle(data, 'year')
        return data


class AnomaliesForm(ParametersForm):
    reference = forms.ChoiceField(
        label='Reference',
        choices=_choices(services.ANOMALY_REFERENCES, REFERENCE_LABELS),
        initial='period',
    )
    layer = forms.ChoiceField(
        label='Layer',
        choices=list(ANOMALY_LAYER_LABELS.items()),
        initial='anomaly',
    )
    # A different name from `HydroperiodForm`'s: the two dropdowns live in the same
    # panel `<form>` and are sent together.
    anomaly_year = forms.IntegerField(label='Hydrological cycle', initial=_default_end_year)

    def clean(self):
        data = super().clean()
        if data.get('layer') == 'anomaly':
            self.validate_cycle(data, 'anomaly_year')
        return data


class TwiForm(forms.Form):
    """The TWI depends only on the terrain, so it ignores sensor and period."""

    dem_source = forms.ChoiceField(
        label='Elevation model',
        choices=_choices(services.DEM_SOURCES, DEM_LABELS),
        initial='MERIT',
    )


class PointForm(forms.Form):
    """Where on the map the user clicked, when reading a pixel value."""

    longitude = forms.FloatField(min_value=-180, max_value=180)
    latitude = forms.FloatField(min_value=-90, max_value=90)


def _clean_drive_folder(folder):
    """Keeps a Drive folder name to something Drive will take verbatim."""
    folder = folder.strip()
    if not folder:
        raise forms.ValidationError('Give a folder name.')
    if not all(character.isalnum() or character in '-_ .' for character in folder):
        raise forms.ValidationError('Use only letters, digits, spaces, dots, hyphens and underscores.')
    return folder


class StatsForm(forms.Form):
    """What zonal statistics need on top of the product being measured.

    Which image gets measured is decided by the same product forms as the map layers,
    so this form only carries the geometries to measure over and how finely to sample.
    """

    geometries = forms.FileField(
        label='Points or polygons',
        help_text='.geojson, .json or .zip (shapefile bundle).',
        widget=forms.FileInput(attrs={'accept': '.geojson,.json,.zip'}),
    )
    scale = forms.IntegerField(
        label='Scale (m)',
        min_value=1,
        max_value=5000,
        required=False,
        help_text='Leave empty to sample at the product\'s native resolution.',
    )
    # Set by the "Send to Drive" button rather than by a control of its own: it is the
    # same computation, only handed to Earth Engine instead of waited on.
    to_drive = forms.BooleanField(required=False)
    # Rendered once, in the Export tab. Declared here too because a Drive export of the
    # statistics needs somewhere to put the CSV, and the panel has a single folder.
    folder = forms.CharField(required=False, max_length=100)

    def clean_folder(self):
        folder = self.cleaned_data['folder']
        return _clean_drive_folder(folder) if folder else services.DEFAULT_DRIVE_FOLDER


# Exporting every cycle of the period is a different job from exporting the one product
# on screen, and the difference is worth spelling out rather than inferring.
EXPORT_TARGET_LABELS = {
    'cycles': 'Every hydrological cycle of the period',
    'product': 'Only the product currently selected',
}


class ExportForm(forms.Form):
    """Where a Drive export goes and at what resolution."""

    target = forms.ChoiceField(
        label='What to export',
        choices=list(EXPORT_TARGET_LABELS.items()),
        initial='cycles',
    )
    folder = forms.CharField(
        label='Drive folder',
        initial=services.DEFAULT_DRIVE_FOLDER,
        max_length=100,
    )
    # A different name from `StatsForm`'s: both live in the same panel `<form>` and are
    # sent together, so a shared `scale` would have them overwrite each other.
    export_scale = forms.ChoiceField(
        label='Scale (m)',
        choices=[(str(scale), f'{scale} m') for scale in services.EXPORT_SCALES],
        initial='30',
    )

    def clean_folder(self):
        return _clean_drive_folder(self.cleaned_data['folder'])

    def clean_export_scale(self):
        return int(self.cleaned_data['export_scale'])
