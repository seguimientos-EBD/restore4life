"""Etiquetas del panel de hidroperiodo.

El panel es un trozo del detalle del ámbito, pero se monta a sí mismo para que la
app `ambitos` no tenga que saber nada de hidroperiodo ni de Earth Engine.
"""

from django import template

from hidroperiodo import forms, services

register = template.Library()


@register.inclusion_tag('hidroperiodo/panel.html', takes_context=True)
def panel_hidroperiodo(context, ambito):
    return {
        'ambito': ambito,
        # El ROI es un humedal, no el ámbito entero: el panel empieza por elegirlo.
        'humedales': ambito.humedales.defer('geom'),
        'form_hidroperiodo': forms.HidroperiodoForm(),
        'form_anomalias': forms.AnomaliasForm(),
        'form_twi': forms.TwiForm(),
        # Qué combinaciones son válidas, para que el navegador ajuste los
        # desplegables sin ir al servidor. El servidor las vuelve a comprobar.
        'opciones': {
            'anioMinimo': services.ANIO_MINIMO_SENSOR,
            'indices': {
                sensor: [{'valor': indice, 'etiqueta': forms.ETIQUETAS_INDICE[indice]} for indice in indices]
                for sensor, indices in services.INDICES_AGUA_SENSOR.items()
            },
        },
        'earthengine_account': context.get('earthengine_account'),
    }
