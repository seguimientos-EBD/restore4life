# Restore4Life — Danube Wetlands HydroApp

Interactive widget for hydroperiod analysis of Danube basin wetlands, powered by [ndvi2gif](https://github.com/Digdgeo/Ndvi2Gif) and running on Google Earth Engine.

![HydroApp overview](imgs/Overview.png)

## What it does

A collapsible panel on the map with 5 tabs:

- **Hydroperiod** — compute hydrological cycles (S2, Landsat, MODIS) with configurable water indices and threshold.
- **Anomalies** — anomalies relative to the period mean or the full historical archive.
- **TWI** — Topographic Wetness Index (MERIT Hydro or a hybrid NASADEM + MERIT setup).
- **Stats** — zonal statistics over points or polygons for any computed product.
- **Export** — export results to Google Drive.

ROI selection via dropdown (Danube wetlands or eLTER sites), shapefile/GeoJSON/ZIP upload, or on-map drawing.

See [`FEATURES.md`](FEATURES.md) for the full breakdown.

## Installation

```bash
pip install ndvi2gif geemap ipyevents geopandas
```

## Data

The following files must be present at the repo root (already included):

- `DRBD_2021.shp` (+ sidecars) — Danube basin boundary
- `humedales_danubio.shp` (+ sidecars) — wetlands to analyse
- `elter_danube.geojson` — eLTER sites within the basin (optional; regenerate with `scripts/build_elter_danube.py`)
- `logo.png` — widget logo

## Usage

```python
import ee
import geemap
from restore4life import HydroperiodApp

ee.Initialize()

Map = geemap.Map()
HydroperiodApp(Map)
Map
```

See `notebooks/demo.ipynb` for a full walkthrough.
