# Restore4Life — Danube Wetlands HydroApp

Web application for hydroperiod analysis of Danube basin wetlands, running on Google
Earth Engine. It is a Django port of the [`ndvi2gif`](https://github.com/Digdgeo/Ndvi2Gif)-based
notebook widget in [`diego/`](diego/), keeping the same computation engine and dropping
the ipywidgets interface.

## What it does

Pick a wetland, or draw an area on the map, and compute over it:

- **Hydroperiod** — flooded days per hydrological year (Sentinel-2, Landsat or MODIS),
  with configurable water index and threshold.
- **Anomalies** — each cycle against the period mean or the sensor's full archive.
- **TWI** — topographic wetness index from MERIT Hydro or a NASADEM/MERIT hybrid.
- **Stats** — zonal statistics over points or polygons you upload, as a table, a CSV or
  a Drive export.
- **Export** — GeoTIFFs to Google Drive, per cycle or for the product on screen.

Every user connects their **own** Earth Engine account: computation runs on their
credentials and quota, and their refresh token is stored encrypted.

## Requirements

- Python 3.13, PostgreSQL with **PostGIS**, Node with **yarn**
- System libraries for GeoDjango: `libgdal`, `libgeos_c`, `libproj`
- `libpq-dev`, to build `psycopg2`

On Debian/Ubuntu the two that are easy to miss:

```bash
sudo apt install libpq-dev gdal-bin libgdal-dev
```

## Setup

```bash
uv sync                      # or: python -m venv .venv && pip install -e .
```

Create the database and enable PostGIS (the extension needs a superuser):

```bash
createdb restore4life
sudo -u postgres psql -d restore4life -c "CREATE EXTENSION postgis;"
```

Write a `.env` at the repo root. Seven of these have no default at all and the app will
not start without them; `DEBUG` and `STATIC_ROOT` fall back to what the comment says,
but you want both set anyway:

```ini
SECRET_KEY=...
DJANGO_CONFIGURATION=Dev          # 'Prod' turns on HSTS, secure cookies and Sentry
DEBUG=True                        # defaults to False
STATIC_ROOT=/path/to/staticfiles  # defaults to None; sass_processor writes the compiled CSS here
MEDIA_ROOT=/path/to/media
EE_TOKEN_ENCRYPTION_KEY=...       # Fernet key: Fernet.generate_key()
APP_URL=https://restore4life.icts-donana.es   # defaults to this; the manuals print it
DATABASE_NAME=restore4life
DATABASE_USER=...
DATABASE_PASSWORD=...
```

Then:

```bash
python manage.py yarn install     # front-end deps, from YARN_INSTALLED_APPS in settings
python manage.py migrate
python manage.py create_study_area "Danube Basin" data/humedales_danubio.shp \
    --boundary data/DRBD_2021.shp
python manage.py import_elter_sites "Danube Basin" data/elter_danube.geojson
python manage.py runserver
```

Both loading commands are needed. The eLTER sites are a second registry attached to the
study area the first one creates, and skipping them fails silently: with none in the
database the panel drops the "eLTER sites" source from the dropdown altogether, so the
app looks complete and is simply missing half its areas.

Login is passwordless: enter an email and follow the link. In development
`EMAIL_BACKEND` defaults to the console, so the link is printed to the server log.

See [`data/README.md`](data/README.md) for what the two sets of source files are.

## Layout

```
apps/areas/        StudyArea and Wetland, the map's GeoJSON endpoints
apps/hydroperiod/  the panel: tiles, zonal statistics, Drive exports, pixel inspector
apps/earthengine/  per-user OAuth against Earth Engine, encrypted token storage
apps/accounts/     email-link authentication
apps/generic/      landing page, FAQ, citation, manuals, login-required middleware
static/js/areas.js       owns the map: basemaps, layer switcher, drawing tools
static/js/hydroperiod.js owns the panel and the layers it puts on the map
templates/manual/  the two manuals; their figures live in apps/generic/manual.py
diego/             the original notebook app, for reference
```

## Manuals

Two of them, public so that they can be read before there is an account to read them
with — the first is about how to get one:

- `/manual/earth-engine/` — creating the Cloud project and connecting it.
- `/manual/` — using the application.

Each is a page of the site and a PDF printed from that same page, so there is one
source and no second copy to fall out of step. Both are linked from the *Help* menu.

**Screenshots** go in `static/img/manual/` under the name their figure declares. A
figure whose file is not there draws a placeholder naming it, so the pages themselves
are the list of what is still to capture — open them and look for the dashed boxes.

**The numbered marks** on each screenshot live in `apps/generic/manual.py`, as
percentages of the image. To find those numbers rather than guess them, open a manual
with `?markers=1` and click where a mark belongs: the line to paste is printed at the
foot of the window and copied to the clipboard.

Whole-window screenshots want the full column width, which is the default. Use
`width='narrow'` only for a cropped panel or dialog: a whole window shrunk into that
column stops being legible, which is the one thing a screenshot has to be.

**The PDFs** are built artefacts and are committed, because the site serves them from
`static/` and the deploy does not run a browser. Regenerate them after adding
screenshots, against a running server:

```bash
python manage.py runserver 8000
scripts/build_manual_pdfs.sh          # or against another host: scripts/build_manual_pdfs.sh https://…
```

Until a PDF exists, its page simply does not offer the download.

## How it fits together

**Nothing is kept between requests.** Every call rebuilds the Earth Engine graph from
the form parameters. This is cheap because EE is lazy: `getMapId()` returns a tile URL
without computing a pixel, and the real work is triggered by the browser one tile at a
time. It is what lets the server do without the state the notebook kept in its kernel.

**The panel is one `<form>` for five tabs.** Every request carries every field and each
endpoint keeps only what its own form declares. Fields that would collide across forms
are named apart — `anomaly_year`, `export_scale`.

**The area analysed travels as a parameter**, not in the URL: it is either `wetland=<pk>`
or a drawn `geometry=<geojson>`, and only one of those has a primary key. When both are
present the drawing wins.

## Known gotchas

- **`ee.Initialize()` sets process-global state, not per-request state.** The server must
  run sync/process-based workers (gunicorn's `sync` class), never threaded, or concurrent
  users' requests can race onto each other's Earth Engine credentials.
- **Templates are cached even with `DEBUG=True`** (Django 4.1+). The autoreloader clears
  that cache, so `runserver --noreload` will not pick up template edits.
- The SCSS imports Bootstrap as `node_modules/node_modules/...`. The doubled directory is
  correct: it is how `django-yarnpkg` lays the folder out.
- `manage.py yarn install` needs a valid `name` in `node_modules/package.json`. Yarn 1.x
  blacklists `node_modules`, which is what it generates by default there.

## Testing

There are no tests yet. `hydroperiod/services.py` has pure functions that are the obvious
place to start — `last_closed_cycle()` and `validate_parameters()` need no Earth Engine.
