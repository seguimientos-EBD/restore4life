/* Study area map: basemaps, wetlands, drawing tools and the layer switcher.
 *
 * This file owns the map. Anything that wants to put something on it — the hydroperiod
 * panel and its Earth Engine layers — goes through `R4L_MAP`, so the map stays the one
 * place that knows about Leaflet.
 */

/* Esri serves its tiles as {z}/{y}/{x}; everyone else uses {z}/{x}/{y}. Getting that
 * backwards is the classic way to end up with a mirrored world. */
const AREA_BASEMAPS = [
    {
        name: 'Satellite (Esri)',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        options: {attribution: 'Imagery: Esri, Maxar, Earthstar Geographics', maxZoom: 19},
        thumbnail: true,
    },
    {
        name: 'Topographic (Esri)',
        url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        options: {attribution: 'Esri, HERE, Garmin, USGS, NGA', maxZoom: 19},
    },
    {
        name: 'OpenStreetMap',
        url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
        options: {attribution: '© OpenStreetMap contributors', maxZoom: 19},
    },
    {
        name: 'Terrain (OpenTopoMap)',
        url: 'https://tile.opentopomap.org/{z}/{x}/{y}.png',
        options: {attribution: '© OpenTopoMap (CC-BY-SA), © OpenStreetMap contributors', maxZoom: 17},
    },
    {
        name: 'Light (Carto)',
        url: 'https://basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        options: {attribution: '© OpenStreetMap contributors, © CARTO', maxZoom: 19},
    },
];

/* Gold and unfilled, as in the notebook widget: the boundary is context, not a layer
 * you read anything off, so it must not tint what is underneath it. */
const AREA_STYLE_BOUNDARY = {color: '#E8B44A', weight: 2, fill: false, interactive: false};

/* How much slack to leave around the boundary before panning stops. Zero would pin the
 * outline to the very edge of the viewport, which feels broken rather than deliberate. */
const AREA_BOUNDS_PADDING = 0.35;

const AREA_STYLE = {color: '#51727C', weight: 2, fillOpacity: 0.15};
const AREA_STYLE_SELECTED = {color: '#729277', weight: 3, fillOpacity: 0.35};
const AREA_STYLE_DRAWN = {color: '#C08A3E', weight: 2, fillOpacity: 0.15};

/* Options that leave the map as a plain image: no controls, no interaction. */
const AREA_THUMBNAIL_OPTIONS = {
    zoomControl: false,
    attributionControl: false,
    dragging: false,
    scrollWheelZoom: false,
    doubleClickZoom: false,
    boxZoom: false,
    keyboard: false,
    touchZoom: false,
};

/* The one handle on the map. `control` is the layer switcher, so computed layers can be
 * registered on it; `drawn` holds the shape being used as the region of interest. */
const R4L_MAP = {map: null, control: null, wetlands: null, boundary: null, drawnItems: null,
                 drawn: null, inspecting: false, inspectButton: null};

/* Wetlands drawn on the study area map, by key, and which one is selected. */
const AREA_WETLANDS = {layers: {}, selected: null};

function areaBasemaps(thumbnailOnly) {
    const layers = {};
    AREA_BASEMAPS.forEach(function(basemap) {
        if (!thumbnailOnly || basemap.thumbnail) {
            layers[basemap.name] = L.tileLayer(basemap.url, basemap.options);
        }
    });
    return layers;
}

/* Every wetland can be picked from the map; the rest of the GeoJSON is left alone. */
function prepareWetland(feature, layer) {
    const properties = feature.properties;
    if (!properties || !properties.pk) {
        return;
    }

    AREA_WETLANDS.layers[properties.pk] = layer;
    layer.bindTooltip(properties.name, {sticky: true});
    layer.on('click', function() {
        if (R4L_MAP.inspecting) {
            return;
        }
        selectWetland(properties.pk, false);
        /* The hydroperiod panel is the one that knows what to do with the selected
           wetland: here it is only announced, same as with the map. */
        document.dispatchEvent(new CustomEvent('wetland:selected', {detail: {pk: properties.pk}}));
    });
}

/* Highlights the wetland and, if it was picked from the panel, takes the map to it. */
function selectWetland(pk, fit) {
    if (AREA_WETLANDS.selected) {
        AREA_WETLANDS.selected.setStyle(AREA_STYLE);
    }

    const layer = AREA_WETLANDS.layers[pk];
    AREA_WETLANDS.selected = layer || null;
    if (!layer) {
        return;
    }

    layer.setStyle(AREA_STYLE_SELECTED);
    layer.bringToFront();
    if (fit && R4L_MAP.map) {
        R4L_MAP.map.fitBounds(layer.getBounds(), {padding: [16, 16]});
    }
}

/* --------------------------------------------------------------------------- *
 * Drawing an area of interest                                                  *
 * --------------------------------------------------------------------------- */

/* Only one drawn shape at a time: the region of interest is singular, and letting two
 * accumulate would leave it ambiguous which one the computation used. */
function setDrawnRoi(layer) {
    R4L_MAP.drawnItems.clearLayers();
    R4L_MAP.drawnItems.addLayer(layer);
    R4L_MAP.drawn = layer.toGeoJSON().geometry;
    document.dispatchEvent(new CustomEvent('roi:drawn', {detail: {geometry: R4L_MAP.drawn}}));
}

function clearDrawnRoi() {
    R4L_MAP.drawnItems.clearLayers();
    R4L_MAP.drawn = null;
    document.dispatchEvent(new CustomEvent('roi:cleared'));
}

function addDrawControls(map) {
    R4L_MAP.drawnItems = new L.FeatureGroup().addTo(map);

    map.addControl(new L.Control.Draw({
        position: 'topleft',
        edit: {featureGroup: R4L_MAP.drawnItems, remove: true},
        draw: {
            /* A hydroperiod is measured over an area, so the line and point tools would
               only produce geometries the server has to reject. */
            polyline: false,
            circle: false,
            circlemarker: false,
            marker: false,
            polygon: {shapeOptions: AREA_STYLE_DRAWN, allowIntersection: false},
            rectangle: {shapeOptions: AREA_STYLE_DRAWN},
        },
    }));

    map.on(L.Draw.Event.CREATED, function(event) { setDrawnRoi(event.layer); });
    map.on(L.Draw.Event.EDITED, function(event) {
        event.layers.eachLayer(function(layer) { setDrawnRoi(layer); });
    });
    map.on(L.Draw.Event.DELETED, function() {
        if (!R4L_MAP.drawnItems.getLayers().length) {
            clearDrawnRoi();
        }
    });
}

/* --------------------------------------------------------------------------- *
 * Map construction                                                             *
 * --------------------------------------------------------------------------- */

/* Creates the base map and adds the geometry to it, fitting the view to its extent.
   The GeoJSON may be a single wetland (admin) or the study area's collection. */
function drawStudyArea(el, geojson, options, interactive) {
    const basemaps = areaBasemaps(!interactive);
    const first = Object.values(basemaps)[0];
    const map = L.map(el, Object.assign({layers: [first]}, options));

    const wetlands = L.geoJSON(geojson, {style: AREA_STYLE, onEachFeature: prepareWetland}).addTo(map);
    map.fitBounds(wetlands.getBounds(), {padding: [8, 8]});

    /* Beside the panel the map is as tall as the panel is, and the panel grows and
       shrinks on its own: blocks appear once there are layers to compare, the log fills
       up, tabs of different heights come and go. Leaflet sizes itself once and would
       otherwise leave the new strip blank, with no tiles in it. */
    if (window.ResizeObserver) {
        new ResizeObserver(function() { map.invalidateSize(false); }).observe(el);
    }

    if (interactive) {
        R4L_MAP.map = map;
        R4L_MAP.wetlands = wetlands;
        /* `collapsed` off because the whole point of asking for this control was to see
           at a glance which layers are on. */
        R4L_MAP.control = L.control.layers(basemaps, {'Wetlands': wetlands},
            {collapsed: false, position: 'topright'}).addTo(map);
        addDrawControls(map);
        addInspectControl(map);
        map.on('click', function(event) {
            if (R4L_MAP.inspecting) {
                document.dispatchEvent(new CustomEvent('map:inspect', {detail: {latlng: event.latlng}}));
            }
        });
    }
    return map;
}

/* While inspecting, a click means "what is the value here?", so the map says where it
 * was clicked and the panel decides what to ask. */
function setInspectMode(on) {
    if (!R4L_MAP.map) {
        return;
    }
    R4L_MAP.inspecting = on;
    R4L_MAP.map.getContainer().classList.toggle('map-inspecting', on);
    if (R4L_MAP.inspectButton) {
        R4L_MAP.inspectButton.classList.toggle('active', on);
        R4L_MAP.inspectButton.title = on ? 'Stop reading values' : 'Read the value of the current layer';
    }
}

/* The value reader lives on the map, next to the drawing tools: it is a map tool, and
 * putting it in the panel under the map meant nobody found it. */
function addInspectControl(map) {
    const Control = L.Control.extend({
        options: {position: 'topleft'},
        onAdd: function() {
            const container = L.DomUtil.create('div', 'leaflet-bar leaflet-control map-inspect-control');
            const button = L.DomUtil.create('a', '', container);
            button.href = '#';
            button.role = 'button';
            button.title = 'Read the value of the current layer';
            button.innerHTML = '<i class="bi bi-eyedropper"></i>';

            L.DomEvent.disableClickPropagation(container);
            L.DomEvent.on(button, 'click', function(event) {
                L.DomEvent.preventDefault(event);
                document.dispatchEvent(new CustomEvent('inspect:toggle'));
            });

            R4L_MAP.inspectButton = button;
            return container;
        },
    });
    map.addControl(new Control());
}

/* Frames the map on the study area outline and keeps it there: you can pan and zoom,
 * but not wander off the basin. The minimum zoom is derived from the outline rather
 * than hardcoded, so a smaller study area is bounded just as tightly. */
function applyBoundary(map, geojson) {
    const boundary = L.geoJSON(geojson, {style: AREA_STYLE_BOUNDARY}).addTo(map);
    const bounds = boundary.getBounds();

    map.fitBounds(bounds, {padding: [8, 8]});
    map.setMaxBounds(bounds.pad(AREA_BOUNDS_PADDING));
    /* Without viscosity the edge is a suggestion: you can drag past it and get sprung
       back, which reads as a glitch. At 1 it is a wall. */
    map.options.maxBoundsViscosity = 1.0;
    map.setMinZoom(map.getBoundsZoom(bounds));

    addOverlay(boundary, 'Study area boundary');
    R4L_MAP.boundary = boundary;
    return boundary;
}

/* Registers a layer on the switcher so it can be toggled off without losing it. */
function addOverlay(layer, name) {
    if (R4L_MAP.control) {
        R4L_MAP.control.addOverlay(layer, name);
    }
}

function removeOverlay(layer) {
    if (R4L_MAP.control) {
        R4L_MAP.control.removeLayer(layer);
    }
    if (R4L_MAP.map && R4L_MAP.map.hasLayer(layer)) {
        R4L_MAP.map.removeLayer(layer);
    }
}

/* No jQuery on purpose: this file is also loaded from the admin, which exposes no `$`. */
document.addEventListener('DOMContentLoaded', function() {
    /* Thumbnails carry the already-simplified geometry inside the HTML itself. */
    document.querySelectorAll('.study-area-thumbnail').forEach(function(el) {
        drawStudyArea(el, JSON.parse(el.dataset.geojson), AREA_THUMBNAIL_OPTIONS, false);
    });

    /* The study area map requests it separately, because it weighs a good deal more. */
    document.querySelectorAll('.study-area-map').forEach(function(el) {
        fetch(el.dataset.geojsonUrl)
            .then(function(response) { return response.json(); })
            .then(function(geojson) {
                const map = drawStudyArea(el, geojson, {fullscreenControl: true}, true);
                /* The map arrives late and that is why it is announced: whoever wants to
                   add layers to it (the hydroperiod panel) cannot just wait for the DOM. */
                el.dispatchEvent(new CustomEvent('area:map-ready', {detail: {map: map}, bubbles: true}));

                /* The boundary reframes the map once it lands, so it comes second: the
                   wetlands are what the map is for, and waiting on the outline would
                   leave the user staring at nothing. */
                if (el.dataset.boundaryUrl) {
                    fetch(el.dataset.boundaryUrl)
                        .then(function(response) { return response.json(); })
                        .then(function(outline) { applyBoundary(map, outline); });
                }
            });
    });
});

/* Picked from the panel: besides highlighting it, the map has to go and find it. */
document.addEventListener('wetland:focus', function(event) {
    selectWetland(event.detail.pk, true);
});

/* The panel can drop the drawn area too, so the two stay in step. */
document.addEventListener('roi:clear-request', function() {
    if (R4L_MAP.drawnItems && R4L_MAP.drawnItems.getLayers().length) {
        clearDrawnRoi();
    }
});
