"""Cálculo de hidroperiodo sobre Earth Engine.

Portado de `diego/restore4life/app.py` (Diego García Díaz), que es un widget de
ipywidgets para notebook: aquí queda solo la lógica de cálculo, sin interfaz y sin
estado vivo entre llamadas. El motor sigue siendo `ndvi2gif`.

Casi nada de esto calcula de verdad: Earth Engine es perezoso y lo que devuelven
estas funciones son grafos `ee.Image`. El cálculo lo dispara EE cuando se le piden
teselas (`url_teselas`), valores concretos (`estadisticas_zonales`) o una
exportación. Por eso reconstruir el grafo en cada petición sale barato, que es lo
que permite prescindir del estado que el widget guardaba en el kernel.

Todas las funciones dan por hecho que Earth Engine ya está inicializado para el
usuario en curso; de eso se encarga `earthengine.services.ee_initialize_for_user`.
"""

import json
from datetime import date

import ee
from ndvi2gif import HydroperiodAnalyzer, NdviSeasonality

# --------------------------------------------------------------------------- #
# Constantes                                                                   #
# --------------------------------------------------------------------------- #

SENSORES = ('S2', 'Landsat', 'MODIS')

# Día en que arranca el año hidrológico, (mes, día). Es el valor por defecto de
# `HydroperiodAnalyzer`, pero se pasa explícito para que ndvi2gif y el formulario no
# puedan discrepar sobre cuándo se cierra un ciclo.
INICIO_ANIO_HIDROLOGICO = (9, 1)

# Primer año con datos de cada sensor
ANIO_MINIMO_SENSOR = {'S2': 2017, 'Landsat': 1984, 'MODIS': 2000}

# Índices de agua disponibles según el sensor
INDICES_AGUA_SENSOR = {
    'S2': ('mndwi', 'ndwi', 'awei', 'aweinsh', 'wi2015'),
    'Landsat': ('mndwi', 'ndwi', 'awei', 'aweinsh', 'wi2015'),
    'MODIS': ('mndwi', 'ndwi'),
}

# Bandas que produce el cálculo de un ciclo hidrológico
BANDAS = ('normalized', 'hydroperiod', 'valid_days', 'first_flood_doy', 'last_flood_doy', 'irt')

FUENTES_DEM = ('MERIT', 'HYBRID_30M')

REFERENCIAS_ANOMALIA = ('period', 'historical')

# Resolución nativa de cada sensor, para muestrear estadísticas sin sobremuestrear
ESCALA_SENSOR = {'S2': 10, 'Landsat': 30, 'MODIS': 500}
ESCALA_TWI = 90

CARPETA_DRIVE_POR_DEFECTO = 'restore4life_hydroperiod'

# Simplificación de la geometría del humedal antes de mandarla a Earth Engine. Los
# humedales vienen de shapefiles con miles de vértices y EE los cobra caros en cada
# petición; ~10 m es el píxel más fino que analizamos (Sentinel-2).
TOLERANCIA_ROI = 0.0001

# Paletas de visualización por banda/producto
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
    'anomaly': {
        'min': -180, 'max': 180,
        'palette': ['8b0000', 'd73027', 'fc8d59', 'fee08b', 'ffffff', 'd9ef8b', '91cf60', '1a9850', '00441b'],
    },
    'twi': {
        'min': 2, 'max': 20,
        'palette': ['f7fbff', 'deebf7', 'c6dbef', '9ecae1', '6baed6', '4292c6', '2171b5', '08519c', '08306b'],
    },
}


# --------------------------------------------------------------------------- #
# Región de interés                                                            #
# --------------------------------------------------------------------------- #

def roi_de_humedal(humedal, tolerancia=TOLERANCIA_ROI):
    """Convierte la geometría de un `Humedal` en la `ee.Geometry` a analizar.

    Con `tolerancia=None` se manda la geometría íntegra, que para los humedales
    grandes son varios cientos de KB por petición.
    """
    geom = humedal.geom.simplify(tolerancia, preserve_topology=True) if tolerancia else humedal.geom
    return ee.Geometry(json.loads(geom.geojson))


# --------------------------------------------------------------------------- #
# Hidroperiodo                                                                 #
# --------------------------------------------------------------------------- #

def ultimo_ciclo_cerrado(hoy=None):
    """Año en que empieza el último ciclo hidrológico ya terminado.

    El ciclo Y/Y+1 va del 1 de septiembre de Y al 1 de septiembre de Y+1, así que
    hasta esa fecha el ciclo que empezó el año pasado sigue abierto y sus días
    inundados todavía no cuentan un año completo.
    """
    hoy = hoy or date.today()
    mes, dia = INICIO_ANIO_HIDROLOGICO
    return hoy.year - 1 if (hoy.month, hoy.day) >= (mes, dia) else hoy.year - 2


def valida_parametros(sensor, anio_inicio, anio_fin, indice):
    """Comprueba la combinación sensor/años/índice y devuelve un mensaje o None."""
    if sensor not in SENSORES:
        return f'Sensor desconocido: {sensor}.'
    if anio_inicio > anio_fin:
        return 'El año inicial debe ser menor o igual que el final.'
    if anio_inicio < ANIO_MINIMO_SENSOR[sensor]:
        return f'{sensor} no tiene datos antes de {ANIO_MINIMO_SENSOR[sensor]}.'
    if indice not in INDICES_AGUA_SENSOR[sensor]:
        return f'El índice {indice} no está disponible para {sensor}.'
    return None


def calcula_ciclos(roi, sensor, anio_inicio, anio_fin, indice, umbral, max_nubes=100):
    """Construye el analizador y los ciclos hidrológicos del periodo.

    Devuelve `(analizador, ciclos)`, donde `ciclos` es `{año: ee.Image}` con un
    ciclo por año hidrológico. El analizador hace falta después para las anomalías
    y el IRT, y se reconstruye igual a partir de estos mismos parámetros.
    """
    error = valida_parametros(sensor, anio_inicio, anio_fin, indice)
    if error:
        raise ValueError(error)

    serie = NdviSeasonality(
        roi=roi,
        sat=sensor,
        start_year=anio_inicio,
        end_year=anio_fin,
        max_cloud_cover=max_nubes,
    )
    analizador = HydroperiodAnalyzer(serie, hydrological_year_start=INICIO_ANIO_HIDROLOGICO)
    return analizador, analizador.compute_all_cycles(index=indice, threshold=umbral)


def calcula_irt(analizador):
    """Imagen de IRT (índice de regularidad temporal) por píxel."""
    return analizador.compute_irt_image()


def calcula_anomalias(analizador, ciclos, referencia='period'):
    """Anomalías respecto a la media del periodo o a la del archivo histórico.

    Devuelve `{'mean': ee.Image, 'anomalies': {año: ee.Image}}`.
    """
    if referencia not in REFERENCIAS_ANOMALIA:
        raise ValueError(f'Referencia desconocida: {referencia}.')
    return analizador.compute_anomalies(cycles=ciclos, reference=referencia)


# --------------------------------------------------------------------------- #
# TWI                                                                          #
# --------------------------------------------------------------------------- #

def calcula_twi(roi, fuente_dem='MERIT'):
    """Índice topográfico de humedad: TWI = ln(a / tan β).

    `a` es el área drenante aguas arriba por unidad de longitud de contorno y `β`
    la pendiente local.

    - `MERIT`: MERIT Hydro v1.0.1 (~90 m) para pendiente y acumulación, coherente
      entre sí.
    - `HYBRID_30M`: NASADEM (30 m) para la pendiente y `upa` de MERIT reproyectado
      para la acumulación. La acumulación sigue siendo de 90 m: rellenar sumideros
      y enrutar D8 a 30 m al vuelo no es viable en GEE.
    """
    if fuente_dem not in FUENTES_DEM:
        raise ValueError(f'Fuente de DEM desconocida: {fuente_dem}.')

    merit = ee.Image('MERIT/Hydro/v1_0_1')
    upa = merit.select('upa')  # área drenante aguas arriba, km²

    elevacion = ee.Image('NASA/NASADEM_HGT/001').select('elevation') if fuente_dem == 'HYBRID_30M' \
        else merit.select('elv')

    pendiente = ee.Terrain.slope(elevacion)
    tangente = pendiente.multiply(ee.Number(3.141592653589793).divide(180)).tan().max(0.001)

    # Área específica de captación: upa (km²) → m², dividida por la longitud de
    # contorno, aproximada como la raíz del área de píxel en la proyección local.
    ancho_celda = ee.Image.pixelArea().sqrt()
    area = upa.multiply(1e6).divide(ancho_celda)

    return area.divide(tangente).log().rename('twi').clip(roi)


# --------------------------------------------------------------------------- #
# Visualización                                                                #
# --------------------------------------------------------------------------- #

def url_teselas(imagen, clave_vis):
    """URL de teselas XYZ para pintar la imagen en Leaflet.

    Es lo que hacía `Map.addLayer` por dentro. La respuesta es inmediata: EE no
    calcula nada hasta que el navegador le pide cada tesela.
    """
    return imagen.getMapId(VIS[clave_vis])['tile_fetcher'].url_format


# --------------------------------------------------------------------------- #
# Estadísticas zonales                                                         #
# --------------------------------------------------------------------------- #

def reductor(es_puntual):
    """Valor del píxel para puntos; el resumen habitual para polígonos."""
    if es_puntual:
        return ee.Reducer.first()
    return (ee.Reducer.mean()
            .combine(ee.Reducer.median(), sharedInputs=True)
            .combine(ee.Reducer.min(), sharedInputs=True)
            .combine(ee.Reducer.max(), sharedInputs=True)
            .combine(ee.Reducer.stdDev(), sharedInputs=True)
            .combine(ee.Reducer.count(), sharedInputs=True))


def escala_por_defecto(producto, sensor):
    """Resolución de muestreo acorde al producto que se está midiendo."""
    return ESCALA_TWI if producto == 'twi' else ESCALA_SENSOR.get(sensor, 30)


def estadisticas_zonales(imagen, coleccion, escala, es_puntual):
    """Estadísticas por elemento de `coleccion`, como lista de diccionarios.

    Es la única función del módulo que espera a Earth Engine (`getInfo`), así que
    bloquea mientras dure el cálculo.
    """
    resultado = imagen.reduceRegions(collection=coleccion, reducer=reductor(es_puntual), scale=escala)
    filas = []
    for elemento in resultado.getInfo().get('features', []):
        propiedades = dict(elemento.get('properties', {}))
        propiedades['_fid'] = elemento.get('id', '')
        filas.append(propiedades)
    return filas


# --------------------------------------------------------------------------- #
# Exportación a Drive                                                          #
# --------------------------------------------------------------------------- #

def exporta_imagen(imagen, roi, descripcion, escala, carpeta=CARPETA_DRIVE_POR_DEFECTO):
    """Lanza la exportación de una imagen como GeoTIFF y devuelve la tarea."""
    tarea = ee.batch.Export.image.toDrive(
        image=imagen,
        description=descripcion,
        folder=carpeta,
        fileNamePrefix=descripcion,
        region=roi,
        scale=escala,
        maxPixels=1e13,
    )
    tarea.start()
    return tarea


def exporta_ciclos(analizador, ciclos, etiqueta, escala, carpeta=CARPETA_DRIVE_POR_DEFECTO):
    """Lanza una exportación por ciclo hidrológico y devuelve sus descripciones."""
    etiqueta = etiqueta.replace(' ', '_').replace('/', '-')
    descripciones = []
    for anio, imagen in ciclos.items():
        descripcion = f'hydroperiod_{etiqueta}_{anio}_{anio + 1}'
        analizador.export_to_drive(image=imagen, folder=carpeta, description=descripcion, scale=escala)
        descripciones.append(descripcion)
    return descripciones


def exporta_tabla(imagen, coleccion, escala, es_puntual, descripcion, carpeta=CARPETA_DRIVE_POR_DEFECTO):
    """Exporta las estadísticas zonales como CSV, sin esperar al resultado.

    Es la alternativa a `estadisticas_zonales` cuando la colección es grande: EE lo
    calcula por su cuenta y deja el fichero en Drive.
    """
    resultado = imagen.reduceRegions(collection=coleccion, reducer=reductor(es_puntual), scale=escala)
    tarea = ee.batch.Export.table.toDrive(
        collection=resultado,
        description=descripcion,
        folder=carpeta,
        fileNamePrefix=descripcion,
        fileFormat='CSV',
    )
    tarea.start()
    return tarea
