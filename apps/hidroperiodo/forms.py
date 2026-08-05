"""Validación de los parámetros del panel de hidroperiodo.

Un formulario por producto, porque cada uno reconstruye un grafo distinto de Earth
Engine, pero todos comparten los parámetros de la serie temporal: el panel es un
único `<form>` y cada pestaña manda el mismo bloque común más lo suyo.

Aquí viven también las etiquetas de los desplegables, que son interfaz y no tienen
sitio en `services.py`.
"""

from datetime import date

from django import forms

from hidroperiodo import services

ETIQUETAS_SENSOR = {
    'S2': 'Sentinel-2 (10 m, desde 2017)',
    'Landsat': 'Landsat (30 m, desde 1984)',
    'MODIS': 'MODIS (500 m, desde 2000)',
}

ETIQUETAS_INDICE = {
    'mndwi': 'MNDWI',
    'ndwi': 'NDWI',
    'awei': 'AWEI',
    'aweinsh': 'AWEI (sin sombras)',
    'wi2015': 'WI2015',
}

ETIQUETAS_BANDA = {
    'normalized': 'Hidroperiodo normalizado',
    'hydroperiod': 'Hidroperiodo (días inundados)',
    'valid_days': 'Días con dato válido',
    'first_flood_doy': 'Primer día de inundación',
    'last_flood_doy': 'Último día de inundación',
    'irt': 'IRT (regularidad temporal)',
}

ETIQUETAS_REFERENCIA = {
    'period': 'Media del periodo seleccionado',
    'historical': 'Media histórica (archivo completo)',
}

ETIQUETAS_DEM = {
    'MERIT': 'MERIT Hydro (~90 m)',
    'HYBRID_30M': 'Híbrido 30 m (pendiente NASADEM)',
}

ETIQUETAS_CAPA_ANOMALIA = {
    'media': 'Hidroperiodo medio de referencia',
    'anomalia': 'Anomalía de un ciclo',
}

# Todos los índices de todos los sensores: cuál vale para cuál lo decide
# `services.valida_parametros`, que es quien conoce la tabla.
INDICES = sorted({indice for indices in services.INDICES_AGUA_SENSOR.values() for indice in indices})

ANIO_MINIMO = min(services.ANIO_MINIMO_SENSOR.values())


def _opciones(codigos, etiquetas):
    return [(codigo, etiquetas[codigo]) for codigo in codigos]


def _anio_actual():
    return date.today().year


def _anio_fin_por_defecto():
    """El último ciclo hidrológico cerrado, que no es el del año pasado sin más.

    Como el año hidrológico arranca el 1 de septiembre, entre enero y agosto el
    ciclo que empezó el año pasado todavía está a medias.
    """
    return services.ultimo_ciclo_cerrado()


def _anio_inicio_por_defecto():
    return _anio_fin_por_defecto() - 4


class ParametrosForm(forms.Form):
    """Lo que define la serie temporal, común a hidroperiodo y anomalías."""

    sensor = forms.ChoiceField(
        label='Sensor',
        choices=_opciones(services.SENSORES, ETIQUETAS_SENSOR),
        initial='S2',
    )
    anio_inicio = forms.IntegerField(
        label='Año inicial',
        min_value=ANIO_MINIMO,
        max_value=_anio_actual,
        initial=_anio_inicio_por_defecto,
    )
    anio_fin = forms.IntegerField(
        label='Año final',
        min_value=ANIO_MINIMO,
        max_value=_anio_actual,
        initial=_anio_fin_por_defecto,
    )
    indice = forms.ChoiceField(
        label='Índice de agua',
        choices=_opciones(INDICES, ETIQUETAS_INDICE),
        initial='mndwi',
    )
    umbral = forms.FloatField(
        label='Umbral',
        min_value=-1,
        max_value=1,
        initial=0,
        help_text='Por encima de este valor hay agua.',
        widget=forms.NumberInput(attrs={'step': '0.01'}),
    )
    max_nubes = forms.IntegerField(
        label='Nubosidad máxima (%)',
        min_value=0,
        max_value=100,
        initial=20,
    )

    def clean(self):
        datos = super().clean()
        # `valida_parametros` cruza sensor, años e índice, así que necesita los tres.
        if {'sensor', 'anio_inicio', 'anio_fin', 'indice'} <= datos.keys():
            error = services.valida_parametros(
                datos['sensor'], datos['anio_inicio'], datos['anio_fin'], datos['indice'],
            )
            if error:
                raise forms.ValidationError(error)
        return datos

    def valida_ciclo(self, datos, campo):
        """Comprueba que el ciclo elegido esté entre los que se van a calcular."""
        anio = datos.get(campo)
        if anio is None or 'anio_inicio' not in datos or 'anio_fin' not in datos:
            return
        if not datos['anio_inicio'] <= anio <= datos['anio_fin']:
            self.add_error(campo, 'El ciclo elegido queda fuera del periodo.')


class HidroperiodoForm(ParametrosForm):
    banda = forms.ChoiceField(
        label='Capa',
        choices=_opciones(services.BANDAS, ETIQUETAS_BANDA),
        initial='hydroperiod',
    )
    anio = forms.IntegerField(label='Ciclo hidrológico', initial=_anio_fin_por_defecto)

    def clean(self):
        datos = super().clean()
        # El IRT resume todo el periodo, así que no cuelga de un ciclo concreto.
        if datos.get('banda') != 'irt':
            self.valida_ciclo(datos, 'anio')
        return datos


class AnomaliasForm(ParametrosForm):
    referencia = forms.ChoiceField(
        label='Referencia',
        choices=_opciones(services.REFERENCIAS_ANOMALIA, ETIQUETAS_REFERENCIA),
        initial='period',
    )
    capa = forms.ChoiceField(
        label='Capa',
        choices=list(ETIQUETAS_CAPA_ANOMALIA.items()),
        initial='anomalia',
    )
    # Nombre distinto del de `HidroperiodoForm`: los dos desplegables conviven en el
    # mismo `<form>` del panel y se mandan juntos.
    anio_anomalia = forms.IntegerField(label='Ciclo hidrológico', initial=_anio_fin_por_defecto)

    def clean(self):
        datos = super().clean()
        if datos.get('capa') == 'anomalia':
            self.valida_ciclo(datos, 'anio_anomalia')
        return datos


class TwiForm(forms.Form):
    """El TWI solo depende del terreno, así que ignora sensor y periodo."""

    fuente_dem = forms.ChoiceField(
        label='Modelo de elevación',
        choices=_opciones(services.FUENTES_DEM, ETIQUETAS_DEM),
        initial='MERIT',
    )
