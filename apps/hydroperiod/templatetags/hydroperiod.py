"""Hydroperiod panel tags.

The panel is a slice of the study area detail page, but it assembles itself so that
the `areas` app need know nothing about hydroperiod or Earth Engine.
"""

from django import template

from hydroperiod import forms, services

register = template.Library()


@register.inclusion_tag('hydroperiod/panel.html', takes_context=True)
def hydroperiod_panel(context, study_area):
    return {
        'study_area': study_area,
        # The ROI is a wetland, not the whole study area: the panel starts by picking one.
        'wetlands': study_area.wetlands.defer('geom'),
        'form_hydroperiod': forms.HydroperiodForm(),
        'form_anomalies': forms.AnomaliesForm(),
        'form_twi': forms.TwiForm(),
        'form_stats': forms.StatsForm(),
        'form_export': forms.ExportForm(),
        # Which combinations are valid, so the browser can adjust the dropdowns without
        # a round trip. The server checks them again.
        'options': {
            'minYear': services.SENSOR_MIN_YEAR,
            'indices': {
                sensor: [{'value': index, 'label': forms.INDEX_LABELS[index]} for index in indices]
                for sensor, indices in services.SENSOR_WATER_INDICES.items()
            },
        },
        'earthengine_account': context.get('earthengine_account'),
    }
