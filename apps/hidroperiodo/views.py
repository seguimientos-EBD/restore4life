"""Endpoint de teselas del panel de hidroperiodo.

No guarda nada entre peticiones: cada llamada reconstruye el grafo de Earth Engine
a partir de los parámetros del formulario. Sale barato porque EE es perezoso —
`getMapId()` devuelve una URL de teselas sin calcular ningún píxel, y el cálculo de
verdad lo dispara el navegador tesela a tesela.
"""

import logging

import ee
from ambitos.models import Humedal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from earthengine.services import NotConnected, ee_initialize_for_user
from google.auth.exceptions import RefreshError

from hidroperiodo import services
from hidroperiodo.forms import AnomaliasForm, HidroperiodoForm, TwiForm

logger = logging.getLogger(__name__)


def capa_hidroperiodo(roi, datos):
    analizador, ciclos = services.calcula_ciclos(
        roi, datos['sensor'], datos['anio_inicio'], datos['anio_fin'],
        datos['indice'], datos['umbral'], datos['max_nubes'],
    )
    if datos['banda'] == 'irt':
        return services.calcula_irt(analizador), 'irt', 'IRT'

    anio = datos['anio']
    if anio not in ciclos:
        raise ValueError(f'El ciclo {anio}/{anio + 1} no ha llegado a calcularse.')
    return ciclos[anio].select(datos['banda']), datos['banda'], f'{datos["banda"]} {anio}/{anio + 1}'


def capa_anomalias(roi, datos):
    analizador, ciclos = services.calcula_ciclos(
        roi, datos['sensor'], datos['anio_inicio'], datos['anio_fin'],
        datos['indice'], datos['umbral'], datos['max_nubes'],
    )
    anomalias = services.calcula_anomalias(analizador, ciclos, datos['referencia'])

    if datos['capa'] == 'media':
        return anomalias['mean'], 'mean_hydroperiod', 'Hidroperiodo medio'

    anio = datos['anio_anomalia']
    if anio not in anomalias['anomalies']:
        raise ValueError(f'El ciclo {anio}/{anio + 1} no ha llegado a calcularse.')
    return anomalias['anomalies'][anio], 'anomaly', f'Anomalía {anio}/{anio + 1}'


def capa_twi(roi, datos):
    return services.calcula_twi(roi, datos['fuente_dem']), 'twi', 'TWI'


# Cada producto: formulario que valida sus parámetros y función que arma la imagen.
PRODUCTOS = {
    'hidroperiodo': (HidroperiodoForm, capa_hidroperiodo),
    'anomalias': (AnomaliasForm, capa_anomalias),
    'twi': (TwiForm, capa_twi),
}


def _primer_error(form):
    for errores in form.errors.values():
        return errores[0]
    return 'Parámetros no válidos.'


class TeselasView(LoginRequiredMixin, View):
    """Devuelve la URL XYZ con la que Leaflet pinta el producto sobre el humedal."""

    def get(self, request, humedal_pk):
        producto = PRODUCTOS.get(request.GET.get('producto'))
        if producto is None:
            return JsonResponse({'error': 'Producto desconocido.'}, status=400)
        form_class, construye_capa = producto

        form = form_class(request.GET)
        if not form.is_valid():
            return JsonResponse({'error': _primer_error(form)}, status=400)

        humedal = get_object_or_404(Humedal, pk=humedal_pk)
        try:
            ee_initialize_for_user(request.user)
            imagen, clave_vis, nombre = construye_capa(services.roi_de_humedal(humedal), form.cleaned_data)
            url = services.url_teselas(imagen, clave_vis)
        except NotConnected:
            return JsonResponse(
                {'error': 'No tienes una cuenta de Earth Engine conectada.'}, status=409,
            )
        except RefreshError:
            # El token guardado ya no sirve: no es un fallo del cálculo y se
            # arregla volviendo a autorizar, así que conviene decirlo aparte.
            logger.warning('Credenciales de Earth Engine caducadas para %s', request.user)
            return JsonResponse(
                {'error': 'Tu autorización de Earth Engine ha caducado: vuelve a conectar la cuenta.'},
                status=409,
            )
        except ValueError as error:
            return JsonResponse({'error': str(error)}, status=400)
        except ee.EEException as error:
            # El límite de memoria salta con periodos largos sobre humedales grandes,
            # y se arregla pidiendo menos: merece decirlo en vez de un error genérico.
            logger.warning('Earth Engine rechazó la capa del humedal %s: %s', humedal_pk, error)
            if 'memory' in str(error).lower():
                return JsonResponse({'error': (
                    'El cálculo no cabe en Earth Engine: acorta el periodo de años '
                    'o usa un sensor de menos resolución.'
                )}, status=400)
            return JsonResponse({'error': f'Earth Engine ha rechazado el cálculo: {error}'}, status=502)
        except Exception:
            logger.exception('Error calculando la capa %s del humedal %s', request.GET.get('producto'), humedal_pk)
            return JsonResponse({'error': 'Earth Engine no ha podido calcular la capa.'}, status=502)

        return JsonResponse({'url': url, 'nombre': nombre, 'leyenda': services.VIS[clave_vis]})
