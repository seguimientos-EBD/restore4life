/* Panel de hidroperiodo del detalle del ámbito.
 *
 * El servidor no guarda nada entre peticiones: cada "Ver capa" manda todos los
 * parámetros del panel y recibe una URL de teselas de Earth Engine. Aquí solo se
 * gestiona qué capa está puesta y qué opciones tienen sentido según el sensor.
 */

const HIDRO = {mapa: null, capa: null};
const HIDRO_PRODUCTOS = {hidroperiodo: 'el hidroperiodo', anomalias: 'las anomalías', twi: 'el TWI'};

/* Sentinel-2 no ve antes de 2017 y MODIS no calcula todos los índices: las
 * combinaciones válidas vienen del servidor para no repetirlas aquí. */
function hidroOpciones() {
    const el = document.getElementById('hidroperiodo-opciones');
    return el ? JSON.parse(el.textContent) : null;
}

/* Rehace el desplegable de índices dejando el que hubiera si sigue estando. */
function hidroAjustarIndices(form, opciones) {
    const sensor = form.elements.sensor.value;
    const indices = opciones.indices[sensor] || [];
    const select = form.elements.indice;
    const anterior = select.value;

    select.replaceChildren();
    indices.forEach(function(indice) {
        const opcion = new Option(indice.etiqueta, indice.valor);
        select.add(opcion);
    });
    select.value = indices.some(function(i) { return i.valor === anterior; }) ? anterior : indices[0].valor;
}

/* Sube los años al primero que tenga datos el sensor elegido. */
function hidroAjustarAnios(form, opciones) {
    const minimo = opciones.anioMinimo[form.elements.sensor.value];
    ['anio_inicio', 'anio_fin'].forEach(function(nombre) {
        const campo = form.elements[nombre];
        campo.min = minimo;
        if (Number(campo.value) < minimo) {
            campo.value = minimo;
        }
    });
}

/* Los ciclos hidrológicos son los del periodo, uno por año inicial: 2019/2020… */
function hidroAjustarCiclos(form) {
    const inicio = Number(form.elements.anio_inicio.value);
    const fin = Number(form.elements.anio_fin.value);
    if (!(inicio <= fin)) {
        return;
    }

    form.querySelectorAll('.js-ciclo select, .js-ciclo input').forEach(function(campo) {
        const anterior = Number(campo.value);
        const select = document.createElement('select');
        select.className = 'form-select form-select-sm';
        select.name = campo.name;
        select.id = campo.id;

        for (let anio = inicio; anio <= fin; anio++) {
            select.add(new Option(anio + '/' + (anio + 1), anio));
        }
        select.value = (anterior >= inicio && anterior <= fin) ? anterior : fin;
        campo.replaceWith(select);
    });
}

/* La bitácora del panel. Nada de sustituir el mensaje anterior: el usuario tiene que
 * poder reconstruir qué pidió y en qué orden, que es lo que daba la consola del
 * notebook del que viene esta app. */
const HIDRO_REGISTRO_MAXIMO = 200;
const HIDRO_REGISTRO_CLASES = {error: 'text-danger', ok: 'text-success'};

function hidroRegistrar(mensaje, tipo) {
    const registro = document.querySelector('.js-registro');
    if (!registro) {
        return;
    }
    /* Solo persigue el último mensaje si ya estaba abajo: si el usuario ha subido a
       leer algo, moverle el scroll bajo los pies es peor que no seguir. */
    const alFinal = registro.scrollHeight - registro.scrollTop - registro.clientHeight < 24;

    const linea = document.createElement('li');
    linea.className = 'd-flex gap-2 ' + (HIDRO_REGISTRO_CLASES[tipo] || 'text-body-secondary');

    const hora = document.createElement('span');
    hora.className = 'text-muted flex-shrink-0';
    hora.textContent = new Date().toLocaleTimeString();
    const texto = document.createElement('span');
    texto.textContent = mensaje;

    linea.append(hora, texto);
    registro.append(linea);

    while (registro.childElementCount > HIDRO_REGISTRO_MAXIMO) {
        registro.firstElementChild.remove();
    }
    if (alFinal) {
        registro.scrollTop = registro.scrollHeight;
    }
}

function hidroNombreHumedal(form) {
    const opcion = form.querySelector('.js-humedal').selectedOptions[0];
    return opcion && opcion.value ? opcion.textContent.trim() : null;
}

/* Barra de color con los extremos de la paleta que ha usado Earth Engine. */
function hidroPintarLeyenda(panel, leyenda) {
    const colores = leyenda.palette.map(function(color) { return '#' + color; }).join(', ');
    panel.querySelector('.js-leyenda').innerHTML =
        '<div class="rounded" style="height: 8px; background: linear-gradient(to right, ' + colores + ')"></div>' +
        '<div class="d-flex justify-content-between small text-muted"><span>' + leyenda.min +
        '</span><span>' + leyenda.max + '</span></div>';
}

function hidroQuitarCapa() {
    if (HIDRO.capa) {
        HIDRO.mapa.removeLayer(HIDRO.capa);
        HIDRO.capa = null;
    }
    document.querySelector('.hidroperiodo-capa').classList.add('d-none');
}

function hidroPonerCapa(datos) {
    hidroQuitarCapa();
    HIDRO.capa = L.tileLayer(datos.url, {opacity: 0.8, maxZoom: 18}).addTo(HIDRO.mapa);

    const panel = document.querySelector('.hidroperiodo-capa');
    panel.classList.remove('d-none');
    panel.querySelector('.js-nombre').textContent = datos.nombre;
    panel.querySelector('.js-opacidad').value = 0.8;
    hidroPintarLeyenda(panel, datos.leyenda);
}

/* La URL de teselas la trae la opción elegida: el cálculo es de un humedal concreto. */
function hidroTeselasUrl(form) {
    const select = form.querySelector('.js-humedal');
    const opcion = select.selectedOptions[0];
    return opcion ? opcion.dataset.teselasUrl : null;
}

function hidroPedirCapa(form, boton) {
    /* Los humedales del ámbito son varios MB, así que el mapa puede tardar más que
       el usuario en pulsar. */
    if (!HIDRO.mapa) {
        hidroRegistrar('Espera a que termine de cargar el mapa.', 'error');
        return;
    }

    const teselasUrl = hidroTeselasUrl(form);
    if (!teselasUrl) {
        hidroRegistrar('Elige primero el humedal que quieres analizar.', 'error');
        return;
    }

    const producto = boton.dataset.producto;
    const parametros = new URLSearchParams(new FormData(form));
    parametros.set('producto', producto);

    form.querySelectorAll('.js-ver-capa').forEach(function(b) { b.disabled = true; });
    hidroRegistrar('Calculando ' + (HIDRO_PRODUCTOS[producto] || producto) +
        ' de «' + hidroNombreHumedal(form) + '» en Earth Engine…');
    /* El TWI sale del terreno: la serie temporal no pinta nada y decirlo evita que
       el usuario crea que ha calculado con el periodo que tiene a la vista. */
    if (producto !== 'twi') {
        hidroRegistrar('Serie ' + form.elements.sensor.value + ' ' + form.elements.anio_inicio.value +
            '–' + form.elements.anio_fin.value + ', índice ' + form.elements.indice.value +
            ', umbral ' + form.elements.umbral.value + ', nubes ≤ ' + form.elements.max_nubes.value + '%.');
    }

    fetch(teselasUrl + '?' + parametros.toString())
        .then(function(respuesta) {
            return respuesta.json().then(function(datos) {
                if (!respuesta.ok) {
                    throw new Error(datos.error || 'No se ha podido calcular la capa.');
                }
                return datos;
            });
        })
        .then(function(datos) {
            hidroPonerCapa(datos);
            /* Los productos de hidroperiodo vienen enmascarados a los píxeles que
               alguna vez tuvieron agua: fuera del humedal no hay nada que pintar. */
            hidroRegistrar('Capa añadida: ' + datos.nombre + '.', 'ok');
        })
        .catch(function(error) {
            hidroRegistrar(error.message, 'error');
        })
        .finally(function() {
            form.querySelectorAll('.js-ver-capa').forEach(function(b) { b.disabled = false; });
        });
}

document.addEventListener('ambito:mapa-listo', function(evento) {
    HIDRO.mapa = evento.detail.mapa;
    hidroRegistrar('Mapa del ámbito cargado.');
});

/* Elegir un humedal en el mapa es lo mismo que elegirlo en el desplegable. */
document.addEventListener('humedal:elegido', function(evento) {
    const form = document.querySelector('.hidroperiodo-panel');
    if (!form) {
        return;
    }
    form.querySelector('.js-humedal').value = evento.detail.pk;
    hidroRegistrar('Humedal elegido en el mapa: ' + hidroNombreHumedal(form) + '.');
});

document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('.hidroperiodo-panel');
    const opciones = hidroOpciones();
    if (!form || !opciones) {
        return;
    }

    hidroAjustarIndices(form, opciones);
    hidroAjustarAnios(form, opciones);
    hidroAjustarCiclos(form);

    hidroRegistrar('Panel listo: elige un humedal para empezar.');

    /* El cambio de sensor reescribe índices y años por su cuenta, así que se cuenta:
       si no, el usuario ve moverse campos que él no ha tocado. */
    form.elements.sensor.addEventListener('change', function() {
        hidroAjustarIndices(form, opciones);
        hidroAjustarAnios(form, opciones);
        hidroAjustarCiclos(form);
        hidroRegistrar('Sensor ' + this.value + ': índices y años ajustados a lo que cubre.');
    });
    ['anio_inicio', 'anio_fin'].forEach(function(nombre) {
        form.elements[nombre].addEventListener('change', function() { hidroAjustarCiclos(form); });
    });

    /* Al cambiar de humedal la capa puesta ya no le corresponde, y el mapa tiene que
       ir a buscarlo: de eso se encarga el mapa, que es quien tiene la geometría. */
    form.querySelector('.js-humedal').addEventListener('change', function() {
        hidroQuitarCapa();
        if (this.value) {
            hidroRegistrar('Humedal elegido: ' + hidroNombreHumedal(form) + '.');
            document.dispatchEvent(new CustomEvent('humedal:enfocar', {detail: {pk: Number(this.value)}}));
        }
    });

    form.querySelector('.js-limpiar-registro').addEventListener('click', function() {
        form.querySelector('.js-registro').replaceChildren();
    });

    form.querySelectorAll('.js-ver-capa').forEach(function(boton) {
        boton.addEventListener('click', function() { hidroPedirCapa(form, boton); });
    });

    const panel = document.querySelector('.hidroperiodo-capa');
    panel.querySelector('.js-opacidad').addEventListener('input', function() {
        if (HIDRO.capa) {
            HIDRO.capa.setOpacity(Number(this.value));
        }
    });
    panel.querySelector('.js-quitar-capa').addEventListener('click', function() {
        hidroQuitarCapa();
        hidroRegistrar('Capa quitada del mapa.');
    });
});
