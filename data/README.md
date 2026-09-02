# Source data

The files a fresh deployment needs to populate the database. They are loaded with
`create_study_area`, not read at runtime — once a study area is in PostGIS, nothing here
is touched again.

| File | What it is | Loaded as |
|---|---|---|
| `humedales_danubio.shp` (+ `.dbf`/`.prj`/`.shx`/`.cpg`) | Danube basin wetlands, from the Ramsar inventory | one `Wetland` per feature |
| `DRBD_2021.shp` (+ `.dbf`/`.prj`/`.shx`/`.cst`) | Danube River Basin District outline | the `StudyArea.boundary` the map is framed by |
| `elter_danube.geojson` | eLTER sites intersecting the basin, from DEIMS-SDR | one `Wetland` per feature, `kind='elter'` |

## Loading them

```bash
python manage.py create_study_area "Danube Basin" data/humedales_danubio.shp \
    --boundary data/DRBD_2021.shp
python manage.py import_elter_sites "Danube Basin" data/elter_danube.geojson
```

The order matters only in that the study area has to exist before the eLTER sites can be
attached to it. Re-running either is safe and is the normal way to refresh: the study
area is matched by name and its areas are rebuilt wholesale — each command rebuilding
only the registry it owns, so refreshing the wetlands leaves the eLTER sites alone and
the other way round.

The wetland names come from the `officialna` column, which is the ten-character
truncation the shapefile `.dbf` imposes; the mapping onto readable field names lives in
`COLUMNS` in the command.

## The two registries

Both files land in the same `Wetland` table and are told apart by `kind`. They live
together because what the app does with one it does with the other — a name and an
outline to hand to Earth Engine — and the panel offers them as two sources of the same
choice, alongside drawing on the map.

Only the eLTER sites carry a `deims_id`, which is the DEIMS-SDR record they come from and
the id they are known by elsewhere. Regenerating the file means querying DEIMS-SDR again
(`diego/scripts/build_elter_danube.py`); the sites it keeps are those that *intersect*
the basin, so a handful straddle its edge.
