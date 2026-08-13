# Source data

The files a fresh deployment needs to populate the database. They are loaded with
`create_study_area`, not read at runtime — once a study area is in PostGIS, nothing here
is touched again.

| File | What it is | Loaded as |
|---|---|---|
| `humedales_danubio.shp` (+ `.dbf`/`.prj`/`.shx`/`.cpg`) | Danube basin wetlands, from the Ramsar inventory | one `Wetland` per feature |
| `DRBD_2021.shp` (+ `.dbf`/`.prj`/`.shx`/`.cst`) | Danube River Basin District outline | the `StudyArea.boundary` the map is framed by |
| `elter_danube.geojson` | eLTER sites intersecting the basin, from DEIMS-SDR | not loaded yet — see below |

## Loading them

```bash
python manage.py create_study_area "Danube Basin" data/humedales_danubio.shp \
    --boundary data/DRBD_2021.shp
```

Re-running is safe and is the normal way to refresh: the study area is matched by name
and its wetlands are rebuilt wholesale.

The wetland names come from the `officialna` column, which is the ten-character
truncation the shapefile `.dbf` imposes; the mapping onto readable field names lives in
`COLUMNS` in the command.

## What is not wired up yet

`elter_danube.geojson` came from the notebook app, where eLTER sites were a second
source of regions to analyse. The web app has no equivalent yet — the area analysed is
either a wetland or a shape drawn on the map. The file is kept here because regenerating
it means querying DEIMS-SDR again (`diego/scripts/build_elter_danube.py`).
