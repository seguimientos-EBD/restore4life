/* Hydroperiod panel on the study area detail page.
 *
 * The server keeps nothing between requests: every "Add data" sends all the panel
 * parameters and receives an Earth Engine tile URL. All that is handled here is which
 * layer is on the map and which options make sense for the chosen sensor.
 */

const HYDRO = {map: null, layer: null, layers: [], inspecting: false, compare: null, lastId: 0};
const HYDRO_PRODUCTS = {hydroperiod: 'the hydroperiod', anomalies: 'the anomalies', twi: 'the TWI'};

/* Sentinel-2 cannot see before 2017 and MODIS does not compute every index: the valid
 * combinations come from the server so as not to repeat them here. */
function hydroOptions() {
    const el = document.getElementById('hydroperiod-options');
    return el ? JSON.parse(el.textContent) : null;
}

/* Rebuilds the index dropdown, keeping the previous one if it is still there. */
function hydroAdjustIndices(form, options) {
    const sensor = form.elements.sensor.value;
    const indices = options.indices[sensor] || [];
    const select = form.elements.index;
    const previous = select.value;

    select.replaceChildren();
    indices.forEach(function(index) {
        const option = new Option(index.label, index.value);
        select.add(option);
    });
    select.value = indices.some(function(i) { return i.value === previous; }) ? previous : indices[0].value;
}

/* Raises the years to the first one the chosen sensor has data for. */
function hydroAdjustYears(form, options) {
    const minimum = options.minYear[form.elements.sensor.value];
    ['start_year', 'end_year'].forEach(function(name) {
        const field = form.elements[name];
        field.min = minimum;
        if (Number(field.value) < minimum) {
            field.value = minimum;
        }
    });
}

/* Hydrological cycles are those of the period, one per start year: 2019/2020… */
function hydroAdjustCycles(form) {
    const start = Number(form.elements.start_year.value);
    const end = Number(form.elements.end_year.value);
    if (!(start <= end)) {
        return;
    }

    form.querySelectorAll('.js-cycle select, .js-cycle input').forEach(function(field) {
        const previous = Number(field.value);
        const select = document.createElement('select');
        select.className = 'form-select form-select-sm';
        select.name = field.name;
        select.id = field.id;

        for (let year = start; year <= end; year++) {
            select.add(new Option(year + '/' + (year + 1), year));
        }
        select.value = (previous >= start && previous <= end) ? previous : end;
        field.replaceWith(select);
    });
}

/* The panel log. No replacing the previous message: the user has to be able to
 * reconstruct what they asked for and in what order, which is what the console of the
 * notebook this app comes from used to give. */
const HYDRO_LOG_MAX = 200;
const HYDRO_LOG_CLASSES = {error: 'text-danger', ok: 'text-success'};

function hydroLog(message, type) {
    const log = document.querySelector('.js-log');
    if (!log) {
        return;
    }
    /* Only chase the latest message if it was already at the bottom: if the user has
       scrolled up to read something, moving the scroll under their feet is worse than
       not following. */
    const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 24;

    const line = document.createElement('li');
    line.className = 'd-flex gap-2 ' + (HYDRO_LOG_CLASSES[type] || 'text-body-secondary');

    const time = document.createElement('span');
    time.className = 'text-muted flex-shrink-0';
    time.textContent = new Date().toLocaleTimeString();
    const text = document.createElement('span');
    text.textContent = message;

    line.append(time, text);
    log.append(line);

    while (log.childElementCount > HYDRO_LOG_MAX) {
        log.firstElementChild.remove();
    }
    if (atBottom) {
        log.scrollTop = log.scrollHeight;
    }
}

function hydroWetlandName(form) {
    const option = form.querySelector('.js-wetland').selectedOptions[0];
    return option && option.value ? option.textContent.trim() : null;
}

/* Colour bar with the ends of the palette Earth Engine used. */
function hydroDrawLegend(panel, legend) {
    const colors = legend.palette.map(function(color) { return '#' + color; }).join(', ');
    panel.querySelector('.js-legend').innerHTML =
        '<div class="rounded" style="height: 8px; background: linear-gradient(to right, ' + colors + ')"></div>' +
        '<div class="d-flex justify-content-between small text-muted"><span>' + legend.min +
        '</span><span>' + legend.max + '</span></div>';
}

/* Computed layers stack up rather than replacing each other: comparing two cycles side
 * by side is the whole reason for having a layer switcher, and each one costs another
 * Earth Engine computation to get back. `HYDRO.layer` is only the most recent, which is
 * what the bar underneath the map drives. */
function hydroRemoveLayer() {
    if (!HYDRO.layer) {
        return;
    }
    /* Half a curtain is not a comparison, and the clip has to come off while the layer
       still has a container to take it off. */
    if (HYDRO.compare &&
        (HYDRO.layer === HYDRO.compare.left.layer || HYDRO.layer === HYDRO.compare.right.layer)) {
        hydroStopCompare(true);
        hydroLog('Curtain off: one of the two layers was removed.');
    }
    removeOverlay(HYDRO.layer);
    HYDRO.layers = HYDRO.layers.filter(function(entry) { return entry.layer !== HYDRO.layer; });
    hydroRefreshCompare();

    const previous = HYDRO.layers[HYDRO.layers.length - 1];
    HYDRO.layer = previous ? previous.layer : null;
    if (previous) {
        hydroShowLayerBar(previous.name, previous.legend, previous.layer.options.opacity);
    } else {
        document.querySelector('.hydroperiod-layer').classList.add('d-none');
    }
}

function hydroRemoveAllLayers() {
    hydroStopCompare(true);
    HYDRO.layers.forEach(function(entry) { removeOverlay(entry.layer); });
    HYDRO.layers = [];
    HYDRO.layer = null;
    document.querySelector('.hydroperiod-layer').classList.add('d-none');
    hydroRefreshCompare();
}

function hydroShowLayerBar(name, legend, opacity) {
    const panel = document.querySelector('.hydroperiod-layer');
    panel.classList.remove('d-none');
    panel.querySelector('.js-name').textContent = name;
    panel.querySelector('.js-opacity').value = opacity;
    hydroDrawLegend(panel, legend);
}

/* The switcher lists layers by name, so two runs of the same product need telling
 * apart — otherwise the second entry is indistinguishable from the first. */
function hydroLayerName(data) {
    const taken = HYDRO.layers.filter(function(entry) { return entry.base === data.name; }).length;
    return taken ? data.name + ' (' + (taken + 1) + ')' : data.name;
}

function hydroAddLayer(data, parameters) {
    const name = hydroLayerName(data);
    const layer = L.tileLayer(data.url, {opacity: 0.8, maxZoom: 18}).addTo(HYDRO.map);
    addOverlay(layer, name);

    /* The parameters are kept with the layer so the inspector can rebuild exactly this
       image later, rather than whatever the panel happens to have selected by then. */
    /* An id of its own rather than its position: the comparison dropdowns hold a
       reference to a layer that has to survive other layers being removed under it. */
    const entry = {
        id: ++HYDRO.lastId, layer: layer, name: name, base: data.name,
        legend: data.legend, parameters: parameters,
    };
    HYDRO.layers.push(entry);
    HYDRO.layer = layer;
    hydroShowLayerBar(name, data.legend, 0.8);
    hydroRefreshCompare();
    return entry;
}

function hydroCurrentEntry() {
    return HYDRO.layers.find(function(entry) { return entry.layer === HYDRO.layer; }) || null;
}

/* One URL per endpoint, on the form itself: the area being analysed travels as a
 * parameter, because it may be a wetland from the database or a shape drawn on the map
 * and only one of those has a primary key. */
function hydroUrl(form, key) {
    return form.dataset[key];
}

/* Which area the computation will run on, for the messages. The server applies the same
 * precedence: a drawing beats the dropdown. */
function hydroRoiLabel(form) {
    if (form.elements.geometry.value) {
        return 'the area you drew';
    }
    const option = form.querySelector('.js-wetland').selectedOptions[0];
    return option && option.value ? '"' + option.textContent.trim() + '"' : null;
}

function hydroCsrf(form) {
    const field = form.querySelector('[name=csrfmiddlewaretoken]');
    return field ? field.value : '';
}

/* The panel is one form for five tabs, so every request carries every field and the
 * server keeps only what its own form declares. Files and the CSRF token are dropped:
 * the first cannot go in a query string, the second travels in its own header. */
function hydroParams(form) {
    const params = new URLSearchParams();
    new FormData(form).forEach(function(value, key) {
        if (key !== 'csrfmiddlewaretoken' && !(value instanceof File)) {
            params.set(key, value);
        }
    });
    return params;
}

function hydroPost(form, url, extra, withFile) {
    const body = new FormData(form);
    body.delete('csrfmiddlewaretoken');
    /* Only the statistics endpoint reads the upload; an export would be shipping the
       file across for nothing. */
    if (!withFile) {
        body.delete('geometries');
    }
    Object.keys(extra).forEach(function(key) { body.set(key, extra[key]); });
    return hydroJson(fetch(url, {
        method: 'POST',
        headers: {'X-CSRFToken': hydroCsrf(form)},
        body: body,
    }));
}

/* Errors come back as JSON with the reason in `error`; anything else is a bug. */
function hydroJson(request) {
    return request.then(function(response) {
        return response.json().then(function(data) {
            if (!response.ok) {
                throw new Error(data.error || 'The request failed.');
            }
            return data;
        });
    });
}

function hydroBusy(form, busy) {
    /* The comparison button is not in here: it does not reach Earth Engine, and whether
       it can be pressed depends on how many layers there are, which is not this to say. */
    form.querySelectorAll(
        '.js-show-layer, .js-compute-stats, .js-stats-to-drive, .js-start-export',
    ).forEach(function(b) {
        b.disabled = busy;
    });
}

/* Reports which series a product was computed from. The TWI comes from the terrain, so
 * the time series plays no part, and saying so keeps the user from believing it
 * computed with the period they have in view. */
function hydroLogSeries(form, product) {
    if (product === 'twi') {
        return;
    }
    hydroLog('Series ' + form.elements.sensor.value + ' ' + form.elements.start_year.value +
        '–' + form.elements.end_year.value + ', index ' + form.elements.index.value +
        ', threshold ' + form.elements.threshold.value + ', clouds ≤ ' + form.elements.max_clouds.value + '%.');
}

/* Every tab needs an area to analyse and, for the map, a map to draw on. */
function hydroReady(form, needsMap) {
    if (needsMap && !HYDRO.map) {
        /* A study area's wetlands are several MB, so the map may take longer than the
           user does to click. */
        hydroLog('Wait for the map to finish loading.', 'error');
        return false;
    }
    if (!hydroRoiLabel(form)) {
        hydroLog('Pick a wetland or draw an area on the map first.', 'error');
        return false;
    }
    return true;
}

function hydroRequestLayer(form, button) {
    if (!hydroReady(form, true)) {
        return;
    }

    const product = button.dataset.product;
    const parameters = hydroParams(form);
    parameters.set('product', product);

    hydroBusy(form, true);
    hydroLog('Computing ' + (HYDRO_PRODUCTS[product] || product) +
        ' of ' + hydroRoiLabel(form) + ' on Earth Engine…');
    hydroLogSeries(form, product);

    hydroJson(fetch(hydroUrl(form, 'tilesUrl') + '?' + parameters.toString()))
        .then(function(data) {
            /* Hydroperiod products come masked to the pixels that ever held water:
               outside the area there is nothing to draw. */
            hydroLog('Layer added: ' + hydroAddLayer(data, parameters.toString()).name +
                '. Toggle it from the switcher on the map.', 'ok');
        })
        .catch(function(error) {
            hydroLog(error.message, 'error');
        })
        .finally(function() {
            hydroBusy(form, false);
        });
}

/* --------------------------------------------------------------------------- *
 * Comparing two cycles under a curtain                                         *
 * --------------------------------------------------------------------------- */

/* Both cycles are drawn over the whole map and each one is then clipped to its side of
 * the divider. The rectangle is given in layer coordinates rather than screen ones,
 * which is the system the tile containers are already positioned in: panning then moves
 * the clip along with the tiles instead of against them. */
function hydroClipCurtain() {
    const compare = HYDRO.compare;
    if (!compare) {
        return;
    }

    const size = HYDRO.map.getSize();
    const topLeft = HYDRO.map.containerPointToLayerPoint([0, 0]);
    const bottomRight = HYDRO.map.containerPointToLayerPoint([size.x, size.y]);
    const split = topLeft.x + size.x * compare.ratio;

    compare.left.layer.getContainer().style.clip =
        'rect(' + [topLeft.y, split, bottomRight.y, topLeft.x].join('px,') + 'px)';
    compare.right.layer.getContainer().style.clip =
        'rect(' + [topLeft.y, bottomRight.x, bottomRight.y, split].join('px,') + 'px)';
    compare.divider.style.left = (size.x * compare.ratio) + 'px';
}

function hydroDragCurtain(event) {
    if (!HYDRO.compare) {
        return;
    }
    const point = event.touches ? event.touches[0] : event;
    const box = HYDRO.map.getContainer().getBoundingClientRect();
    HYDRO.compare.ratio = Math.min(1, Math.max(0, (point.clientX - box.left) / box.width));
    hydroClipCurtain();
}

function hydroBuildDivider() {
    const divider = L.DomUtil.create('div', 'map-curtain', HYDRO.map.getContainer());
    divider.innerHTML = '<span class="map-curtain-grip"><i class="bi bi-arrows"></i></span>';
    L.DomEvent.disableClickPropagation(divider);

    const stop = function() {
        document.removeEventListener('mousemove', hydroDragCurtain);
        document.removeEventListener('touchmove', hydroDragCurtain);
        document.removeEventListener('mouseup', stop);
        document.removeEventListener('touchend', stop);
        HYDRO.map.dragging.enable();
    };
    const start = function(event) {
        event.preventDefault();
        /* Without this the map pans underneath the divider being dragged. */
        HYDRO.map.dragging.disable();
        document.addEventListener('mousemove', hydroDragCurtain);
        document.addEventListener('touchmove', hydroDragCurtain);
        document.addEventListener('mouseup', stop);
        document.addEventListener('touchend', stop);
    };

    divider.addEventListener('mousedown', start);
    divider.addEventListener('touchstart', start);
    return divider;
}

function hydroEntryById(id) {
    return HYDRO.layers.find(function(entry) { return entry.id === Number(id); }) || null;
}

/* The two dropdowns list what is on the map right now, so the pair being compared can be
 * a hydroperiod against its anomaly, two cycles of the same band, or the TWI against
 * either — whatever has been computed. Below two layers there is nothing to compare, but
 * the block stays on screen greyed out rather than hidden: something that only appears
 * once you have already done the right thing is something nobody finds. */
function hydroRefreshCompare() {
    const block = document.querySelector('.hydroperiod-compare');
    if (!block) {
        return;
    }

    const enough = HYDRO.layers.length >= 2;
    block.querySelector('.js-compare-hint').classList.toggle('d-none', enough);
    block.querySelectorAll('.js-compare-left, .js-compare-right, .js-compare').forEach(
        function(field) { field.disabled = !enough; });

    ['.js-compare-left', '.js-compare-right'].forEach(function(selector, side) {
        const select = block.querySelector(selector);
        const previous = select.value;
        select.replaceChildren();
        HYDRO.layers.forEach(function(entry) {
            select.add(new Option(entry.name, entry.id));
        });

        /* A choice of the user's is kept as long as its layer is still there. An
           untouched dropdown keeps following the two most recent layers instead, one
           each way round: left on the older, right on the newer. Preserving the value
           there too would leave both ends on the first layer computed. */
        if (select.dataset.chosen === '1' && hydroEntryById(previous)) {
            select.value = previous;
        } else if (HYDRO.layers.length) {
            const fallback = HYDRO.layers[side ? HYDRO.layers.length - 1 : HYDRO.layers.length - 2];
            select.value = (fallback || HYDRO.layers[0]).id;
        }
    });
}

function hydroStartCompare() {
    const block = document.querySelector('.hydroperiod-compare');
    const left = hydroEntryById(block.querySelector('.js-compare-left').value);
    const right = hydroEntryById(block.querySelector('.js-compare-right').value);

    if (!left || !right) {
        hydroLog('Add two layers first: the comparison splits ones already on the map.', 'error');
        return;
    }
    if (left === right) {
        hydroLog('Pick two different layers: one against itself shows nothing.', 'error');
        return;
    }

    /* Leaving the previous pair clipped would hide half of each of them for good. */
    hydroStopCompare(true);

    /* Either side may have been switched off from the layer switcher, and a comparison
       against something invisible is just half a map. */
    [left, right].forEach(function(entry) {
        if (!HYDRO.map.hasLayer(entry.layer)) {
            entry.layer.addTo(HYDRO.map);
        }
    });

    HYDRO.compare = {left: left, right: right, ratio: 0.5, divider: hydroBuildDivider()};
    HYDRO.map.on('move zoom zoomend resize', hydroClipCurtain);
    hydroClipCurtain();
    block.querySelector('.js-stop-compare').classList.remove('d-none');
    hydroLog('Curtain on: "' + left.name + '" on the left, "' + right.name +
        '" on the right. Drag the divider across the map.', 'ok');
}

/* Only the split is undone. The layers stay: they cost an Earth Engine computation
 * each, and wanting them whole again is not wanting them gone. */
function hydroStopCompare(quiet) {
    const compare = HYDRO.compare;
    if (!compare) {
        return;
    }

    HYDRO.map.off('move zoom zoomend resize', hydroClipCurtain);
    compare.divider.remove();
    [compare.left, compare.right].forEach(function(entry) {
        const container = entry.layer.getContainer();
        if (container) {
            container.style.clip = '';
        }
    });
    HYDRO.compare = null;

    const button = document.querySelector('.js-stop-compare');
    if (button) {
        button.classList.add('d-none');
    }
    if (!quiet) {
        hydroLog('Curtain off. Both layers are still on the map.');
    }
}

/* --------------------------------------------------------------------------- *
 * Reading pixel values off the map                                             *
 * --------------------------------------------------------------------------- */

/* While inspecting, a click on the map means "what is the value here?" rather than
 * "select this wetland", so the wetland handler stands down. */
function hydroToggleInspect() {
    if (!hydroCurrentEntry()) {
        hydroLog('Add data first: there is nothing to read a value from.', 'error');
        return;
    }

    HYDRO.inspecting = !HYDRO.inspecting;
    setInspectMode(HYDRO.inspecting);
    hydroLog(HYDRO.inspecting
        ? 'Inspect mode on: click the map to read the value of "' + hydroCurrentEntry().name + '".'
        : 'Inspect mode off.');
}

function hydroFormatValue(value) {
    if (value === null || value === undefined) {
        /* Earth Engine masks pixels the product says nothing about, and that is not the
           same as a zero: a pixel that never flooded has no hydroperiod, it is not a
           hydroperiod of zero days. */
        return 'no data (masked)';
    }
    return typeof value === 'number' && !Number.isInteger(value) ? value.toFixed(4) : String(value);
}

function hydroInspectAt(form, latlng) {
    const entry = hydroCurrentEntry();
    if (!entry) {
        return;
    }

    const parameters = new URLSearchParams(entry.parameters);
    parameters.set('longitude', latlng.lng.toFixed(6));
    parameters.set('latitude', latlng.lat.toFixed(6));

    const popup = L.popup({closeButton: true})
        .setLatLng(latlng)
        .setContent('Reading value…')
        .openOn(HYDRO.map);

    hydroJson(fetch(hydroUrl(form, 'inspectUrl') + '?' + parameters.toString()))
        .then(function(data) {
            const rows = Object.keys(data.values).map(function(band) {
                return '<tr><th class="pe-2 fw-normal text-muted">' + band +
                    '</th><td class="text-end">' + hydroFormatValue(data.values[band]) + '</td></tr>';
            });
            popup.setContent(
                '<strong>' + data.product + '</strong>' +
                '<table class="table table-sm mb-1 mt-1">' + (rows.join('') || '<tr><td>No bands</td></tr>') + '</table>' +
                '<span class="text-muted small">' + data.latitude.toFixed(5) + ', ' +
                data.longitude.toFixed(5) + ' · sampled at ' + data.scale + ' m</span>'
            );
        })
        .catch(function(error) {
            popup.setContent('<span class="text-danger">' + error.message + '</span>');
            hydroLog(error.message, 'error');
        });
}

/* --------------------------------------------------------------------------- *
 * Zonal statistics                                                             *
 * --------------------------------------------------------------------------- */

/* Rows are kept as they arrived so the CSV costs nothing: asking Earth Engine a second
 * time for numbers already on screen would be the expensive way to do this. */
const HYDRO_STATS = {columns: [], rows: [], caption: ''};

function hydroFormatCell(value) {
    if (value === null || value === undefined) {
        return '';
    }
    /* Reducer outputs run to a dozen decimals, which is noise at any sampling scale. */
    return typeof value === 'number' && !Number.isInteger(value) ? value.toFixed(4) : String(value);
}

/* Built with the DOM API rather than a string of HTML: the names come from a file the
 * user uploaded, so they are never treated as markup. */
function hydroDrawStats(data) {
    const panel = document.querySelector('.hydroperiod-stats');
    const table = document.createElement('table');
    table.className = 'table table-sm table-striped mb-0 small';

    const head = table.createTHead().insertRow();
    data.columns.forEach(function(column) {
        const cell = document.createElement('th');
        cell.scope = 'col';
        cell.textContent = column;
        head.append(cell);
    });

    const body = table.createTBody();
    data.rows.forEach(function(row) {
        const line = body.insertRow();
        data.columns.forEach(function(column) {
            line.insertCell().textContent = hydroFormatCell(row[column]);
        });
    });

    panel.querySelector('.js-stats-table').replaceChildren(table);
    panel.querySelector('.js-stats-caption').textContent =
        data.product + ' — ' + data.rows.length + ' ' + data.geometry + ' at ' + data.scale + ' m';
    panel.classList.remove('d-none');
    panel.scrollIntoView({behavior: 'smooth', block: 'nearest'});
}

/* The same computation either way: `toDrive` decides whether we wait for the numbers or
 * let Earth Engine drop a CSV in Drive on its own time. */
function hydroComputeStats(form, toDrive) {
    if (!hydroReady(form, false)) {
        return;
    }
    if (!form.elements.geometries.files.length) {
        hydroLog('Upload the points or polygons to measure over first.', 'error');
        return;
    }

    const product = form.querySelector('.js-stats-product').value;
    hydroBusy(form, true);
    hydroLog('Measuring ' + (HYDRO_PRODUCTS[product] || product) + ' of ' + hydroRoiLabel(form) +
        ' over "' + form.elements.geometries.files[0].name + '"' + (toDrive ? ', to Drive' : '') + '…');
    hydroLogSeries(form, product);

    hydroPost(form, hydroUrl(form, 'statsUrl'), {product: product, to_drive: toDrive ? '1' : ''}, true)
        .then(function(data) {
            if (toDrive) {
                hydroLog('Queued ' + data.tasks[0] + ' for ' + data.features + ' ' + data.geometry +
                    ' to Drive folder "' + data.folder + '" at ' + data.scale + ' m.', 'ok');
                hydroLog('Earth Engine runs it on its own time: follow progress from its task manager.');
                return;
            }
            HYDRO_STATS.columns = data.columns;
            HYDRO_STATS.rows = data.rows;
            HYDRO_STATS.caption = data.product;
            hydroDrawStats(data);
            hydroLog('Statistics computed for ' + data.rows.length + ' ' + data.geometry +
                ' at ' + data.scale + ' m.', 'ok');
        })
        .catch(function(error) {
            hydroLog(error.message, 'error');
        })
        .finally(function() {
            hydroBusy(form, false);
        });
}

/* RFC 4180: quotes are doubled, and any field holding a separator, quote or newline is
 * quoted. Wetland names carry commas often enough for this to matter. */
function hydroCsvField(value) {
    const text = hydroFormatCell(value);
    return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
}

function hydroDownloadCsv() {
    if (!HYDRO_STATS.rows.length) {
        return;
    }
    const lines = [HYDRO_STATS.columns.map(hydroCsvField).join(',')];
    HYDRO_STATS.rows.forEach(function(row) {
        lines.push(HYDRO_STATS.columns.map(function(column) { return hydroCsvField(row[column]); }).join(','));
    });

    /* The BOM is what makes Excel read the accents in the wetland names correctly. */
    const blob = new Blob(['﻿' + lines.join('\r\n')], {type: 'text/csv;charset=utf-8;'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const stamp = new Date().toISOString().slice(0, 19).replace(/[-:]/g, '').replace('T', '_');
    link.href = url;
    link.download = 'stats_' + stamp + '.csv';
    link.click();
    URL.revokeObjectURL(url);
}

/* --------------------------------------------------------------------------- *
 * Drive export                                                                 *
 * --------------------------------------------------------------------------- */

function hydroStartExport(form) {
    if (!hydroReady(form, false)) {
        return;
    }

    const target = form.elements.target.value;
    const product = form.querySelector('.js-export-product').value;
    hydroBusy(form, true);
    hydroLog(target === 'cycles'
        ? 'Queueing one export per hydrological cycle of the period…'
        : 'Queueing the export of ' + (HYDRO_PRODUCTS[product] || product) + '…');

    hydroPost(form, hydroUrl(form, 'exportUrl'), {product: product}, false)
        .then(function(data) {
            hydroLog(data.tasks.length + ' task' + (data.tasks.length === 1 ? '' : 's') +
                ' queued to Drive folder "' + data.folder + '" at ' + data.scale + ' m.', 'ok');
            data.tasks.forEach(function(task) { hydroLog('  · ' + task); });
            hydroLog('Earth Engine runs them on its own time: follow progress from its task manager.');
        })
        .catch(function(error) {
            hydroLog(error.message, 'error');
        })
        .finally(function() {
            hydroBusy(form, false);
        });
}

/* Which product to export only matters when exporting one, not the whole cycle stack. */
function hydroToggleExportProduct(form) {
    const single = form.elements.target.value === 'product';
    form.querySelector('.js-export-product-row').classList.toggle('d-none', !single);
}

document.addEventListener('area:map-ready', function(event) {
    HYDRO.map = event.detail.map;
    hydroLog('Study area map loaded.');
});

/* A shape drawn on the map becomes the area of interest, and the server prefers it over
 * the dropdown, so the dropdown is cleared to match what will actually be computed. */
document.addEventListener('roi:drawn', function(event) {
    const form = document.querySelector('.hydroperiod-panel');
    if (!form) {
        return;
    }
    form.elements.geometry.value = JSON.stringify(event.detail.geometry);
    form.querySelector('.js-wetland').value = '';
    hydroLog('Area drawn on the map: it is now what gets analysed.', 'ok');
});

document.addEventListener('roi:cleared', function() {
    const form = document.querySelector('.hydroperiod-panel');
    if (!form) {
        return;
    }
    form.elements.geometry.value = '';
    hydroLog('Drawn area removed: pick a wetland to carry on.');
});

document.addEventListener('inspect:toggle', function() {
    if (document.querySelector('.hydroperiod-panel')) {
        hydroToggleInspect();
    }
});

document.addEventListener('map:inspect', function(event) {
    const form = document.querySelector('.hydroperiod-panel');
    if (form) {
        hydroInspectAt(form, event.detail.latlng);
    }
});

/* Picking a wetland on the map is the same as picking it in the dropdown. */
document.addEventListener('wetland:selected', function(event) {
    const form = document.querySelector('.hydroperiod-panel');
    if (!form) {
        return;
    }
    form.querySelector('.js-wetland').value = event.detail.pk;
    hydroLog('Wetland picked on the map: ' + hydroWetlandName(form) + '.');
});

document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('.hydroperiod-panel');
    const options = hydroOptions();
    if (!form || !options) {
        return;
    }

    hydroAdjustIndices(form, options);
    hydroAdjustYears(form, options);
    hydroAdjustCycles(form);
    hydroRefreshCompare();

    hydroLog('Panel ready: pick a wetland to start.');

    /* Changing the sensor rewrites indices and years on its own, so it is reported:
       otherwise the user sees fields move that they never touched. */
    form.elements.sensor.addEventListener('change', function() {
        hydroAdjustIndices(form, options);
        hydroAdjustYears(form, options);
        hydroAdjustCycles(form);
        hydroLog('Sensor ' + this.value + ': indices and years adjusted to what it covers.');
    });
    ['start_year', 'end_year'].forEach(function(name) {
        form.elements[name].addEventListener('change', function() { hydroAdjustCycles(form); });
    });

    /* On changing wetland the layer on the map no longer belongs to it, and the map has
       to go and find it: that is the map's job, since it holds the geometry. */
    /* Picking from the dropdown drops the drawn area: the two are alternative ways of
       saying the same thing, and the server would silently prefer the drawing. */
    form.querySelector('.js-wetland').addEventListener('change', function() {
        if (this.value) {
            document.dispatchEvent(new CustomEvent('roi:clear-request'));
            hydroLog('Wetland picked: ' + hydroWetlandName(form) + '.');
            document.dispatchEvent(new CustomEvent('wetland:focus', {detail: {pk: Number(this.value)}}));
        }
    });

    form.querySelector('.js-clear-log').addEventListener('click', function() {
        form.querySelector('.js-log').replaceChildren();
    });

    form.querySelectorAll('.js-compare-left, .js-compare-right').forEach(function(select) {
        select.addEventListener('change', function() { this.dataset.chosen = '1'; });
    });
    form.querySelector('.js-compare').addEventListener('click', function() {
        hydroStartCompare();
    });
    form.querySelector('.js-stop-compare').addEventListener('click', function() {
        hydroStopCompare(false);
    });

    form.querySelectorAll('.js-show-layer').forEach(function(button) {
        button.addEventListener('click', function() { hydroRequestLayer(form, button); });
    });

    form.querySelector('.js-compute-stats').addEventListener('click', function() {
        hydroComputeStats(form, false);
    });
    form.querySelector('.js-stats-to-drive').addEventListener('click', function() {
        hydroComputeStats(form, true);
    });

    hydroToggleExportProduct(form);
    form.elements.target.addEventListener('change', function() { hydroToggleExportProduct(form); });
    form.querySelector('.js-start-export').addEventListener('click', function() {
        hydroStartExport(form);
    });

    const stats = document.querySelector('.hydroperiod-stats');
    stats.querySelector('.js-download-csv').addEventListener('click', hydroDownloadCsv);
    stats.querySelector('.js-close-stats').addEventListener('click', function() {
        stats.classList.add('d-none');
    });

    const panel = document.querySelector('.hydroperiod-layer');
    panel.querySelector('.js-opacity').addEventListener('input', function() {
        if (HYDRO.layer) {
            HYDRO.layer.setOpacity(Number(this.value));
        }
    });
    panel.querySelector('.js-remove-layer').addEventListener('click', function() {
        hydroRemoveLayer();
        hydroLog('Layer removed from the map.');
    });
    panel.querySelector('.js-remove-all-layers').addEventListener('click', function() {
        hydroRemoveAllLayers();
        hydroLog('All computed layers removed.');
    });
});
