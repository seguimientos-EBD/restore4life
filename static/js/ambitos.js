const AMBITO_TILES_URL = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';
const AMBITO_TILES_ATTR = 'Imágenes: Esri, Maxar, Earthstar Geographics';
const AMBITO_ESTILO = {color: '#efa125', weight: 2, fillOpacity: 0.15};
const AMBITO_ESTILO_ELEGIDO = {color: '#0d6efd', weight: 3, fillOpacity: 0.35};

/* Opciones que dejan el mapa como una simple imagen: sin controles ni interacción. */
const AMBITO_OPCIONES_MINIATURA = {
    zoomControl: false,
    attributionControl: false,
    dragging: false,
    scrollWheelZoom: false,
    doubleClickZoom: false,
    boxZoom: false,
    keyboard: false,
    touchZoom: false,
};

/* Humedales dibujados en el mapa de la zona de trabajo, por clave, y cuál está elegido. */
const AMBITO_HUMEDALES = {mapa: null, capas: {}, elegido: null};

/* Crea el mapa base y le añade la geometría, ajustando la vista a su extensión.
   El GeoJSON puede ser un humedal suelto (admin) o la colección del ámbito. */
function dibujarAmbito(el, geojson, opciones) {
    const mapa = L.map(el, opciones);
    L.tileLayer(AMBITO_TILES_URL, {attribution: AMBITO_TILES_ATTR, maxZoom: 18}).addTo(mapa);

    const capa = L.geoJSON(geojson, {style: AMBITO_ESTILO, onEachFeature: prepararHumedal}).addTo(mapa);
    mapa.fitBounds(capa.getBounds(), {padding: [8, 8]});
    return mapa;
}

/* Cada humedal se puede elegir desde el mapa; el resto del GeoJSON se deja quieto. */
function prepararHumedal(feature, capa) {
    const propiedades = feature.properties;
    if (!propiedades || !propiedades.pk) {
        return;
    }

    AMBITO_HUMEDALES.capas[propiedades.pk] = capa;
    capa.bindTooltip(propiedades.nombre, {sticky: true});
    capa.on('click', function() {
        elegirHumedal(propiedades.pk, false);
        /* El panel de hidroperiodo es quien sabe qué hacer con el humedal elegido:
           aquí solo se anuncia, igual que con el mapa. */
        document.dispatchEvent(new CustomEvent('humedal:elegido', {detail: {pk: propiedades.pk}}));
    });
}

/* Resalta el humedal y, si se ha elegido desde el panel, lleva el mapa hasta él. */
function elegirHumedal(pk, encuadrar) {
    if (AMBITO_HUMEDALES.elegido) {
        AMBITO_HUMEDALES.elegido.setStyle(AMBITO_ESTILO);
    }

    const capa = AMBITO_HUMEDALES.capas[pk];
    AMBITO_HUMEDALES.elegido = capa || null;
    if (!capa) {
        return;
    }

    capa.setStyle(AMBITO_ESTILO_ELEGIDO);
    capa.bringToFront();
    if (encuadrar && AMBITO_HUMEDALES.mapa) {
        AMBITO_HUMEDALES.mapa.fitBounds(capa.getBounds(), {padding: [16, 16]});
    }
}

/* Sin jQuery a propósito: este fichero también se carga desde el admin, que no expone `$`. */
document.addEventListener('DOMContentLoaded', function() {
    /* Las miniaturas llevan la geometría ya simplificada dentro del propio HTML. */
    document.querySelectorAll('.ambito-miniatura').forEach(function(el) {
        dibujarAmbito(el, JSON.parse(el.dataset.geojson), AMBITO_OPCIONES_MINIATURA);
    });

    /* El mapa de la zona de trabajo la pide aparte, porque pesa bastante más. */
    document.querySelectorAll('.ambito-mapa').forEach(function(el) {
        fetch(el.dataset.geojsonUrl)
            .then(function(respuesta) { return respuesta.json(); })
            .then(function(geojson) {
                const mapa = dibujarAmbito(el, geojson, {fullscreenControl: true});
                AMBITO_HUMEDALES.mapa = mapa;
                /* El mapa llega tarde y por eso se anuncia: quien quiera añadirle capas
                   (el panel de hidroperiodo) no puede limitarse a esperar al DOM. */
                el.dispatchEvent(new CustomEvent('ambito:mapa-listo', {detail: {mapa: mapa}, bubbles: true}));
            });
    });
});

/* Elegido desde el panel: además de resaltarlo hay que ir a buscarlo en el mapa. */
document.addEventListener('humedal:enfocar', function(evento) {
    elegirHumedal(evento.detail.pk, true);
});
