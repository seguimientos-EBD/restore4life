"""
restore4life/app.py - Restore4Life Hydroperiod App
===================================================

Interactive leafmap/geemap widget for hydroperiod analysis of Danube
basin wetlands. Uses ndvi2gif (NdviSeasonality + HydroperiodAnalyzer)
as the computation backend.

Usage
-----
::

    import ee
    import geemap
    from restore4life import HydroperiodApp

    ee.Initialize()

    Map = geemap.Map()
    HydroperiodApp(Map)
    Map

Author: Diego García Díaz
"""

import base64
import io
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

import ee
import geopandas as gpd
import ipyevents
import ipyleaflet
import ipywidgets as widgets
import pandas as pd
from IPython.display import display
from ndvi2gif import HydroperiodAnalyzer, NdviSeasonality

# --------------------------------------------------------------------------- #
# Paths                                                                        #
# --------------------------------------------------------------------------- #

DATA_DIR = Path(__file__).parent.parent

# --------------------------------------------------------------------------- #
# Visualization parameters                                                     #
# --------------------------------------------------------------------------- #

_VIS = {
    "hydroperiod": {
        "min": 0, "max": 365,
        "palette": ["ffffff", "ffffcc", "c7e9b4", "7fcdbb",
                    "41b6c4", "1d91c0", "225ea8", "0c2c84"],
    },
    "normalized": {
        "min": 0, "max": 365,
        "palette": ["ffffff", "ffffcc", "c7e9b4", "7fcdbb",
                    "41b6c4", "1d91c0", "225ea8", "0c2c84"],
    },
    "valid_days": {
        "min": 0, "max": 365,
        "palette": ["f7fbff", "deebf7", "9ecae1", "3182bd", "08306b"],
    },
    "first_flood_doy": {
        "min": 0, "max": 365,
        "palette": ["440154", "31688e", "35b779", "fde725"],
    },
    "last_flood_doy": {
        "min": 0, "max": 365,
        "palette": ["fde725", "35b779", "31688e", "440154"],
    },
    "irt": {
        "min": 0, "max": 1,
        "palette": ["d73027", "fc8d59", "fee08b", "d9ef8b", "91cf60", "1a9850"],
    },
    "mean_hydroperiod": {
        "min": 0, "max": 365,
        "palette": ["ffffff", "ffffcc", "c7e9b4", "7fcdbb",
                    "41b6c4", "1d91c0", "225ea8", "0c2c84"],
    },
    "anomaly": {
        "min": -180, "max": 180,
        "palette": ["8b0000", "d73027", "fc8d59", "fee08b",
                    "ffffff",
                    "d9ef8b", "91cf60", "1a9850", "00441b"],
    },
    "twi": {
        "min": 2, "max": 20,
        "palette": ["f7fbff", "deebf7", "c6dbef", "9ecae1", "6baed6",
                    "4292c6", "2171b5", "08519c", "08306b"],
    },
}

# Minimum sensor start years
_SENSOR_MIN_YEAR = {"S2": 2017, "Landsat": 1984, "MODIS": 2000}

# Water indices available per sensor
_SENSOR_WATER_INDICES = {
    "S2":      ["mndwi", "ndwi", "awei", "aweinsh", "wi2015"],
    "Landsat": ["mndwi", "ndwi", "awei", "aweinsh", "wi2015"],
    "MODIS":   ["mndwi", "ndwi"],
}

# Legend dropdown options  (label → _VIS key)
_LEGEND_OPTIONS = [
    ("Hydroperiod (days)",       "hydroperiod"),
    ("Hydroperiod (normalized)", "normalized"),
    ("Valid observations",       "valid_days"),
    ("First flood (DOY)",        "first_flood_doy"),
    ("Last flood (DOY)",         "last_flood_doy"),
    ("IRT (0–1)",                "irt"),
    ("Mean hydroperiod",         "mean_hydroperiod"),
    ("Anomaly (days)",           "anomaly"),
]

# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _gdf_to_ee(gdf):
    """Convert a GeoDataFrame to an ee.FeatureCollection via GeoJSON."""
    return ee.FeatureCollection(json.loads(gdf.to_json()))


def _detect_name_col(gdf):
    """Return the first plausible name column found in *gdf*."""
    candidates = ["officialna", "name", "Name", "NAME", "nombre", "NOMBRE",
                  "site", "Site", "SITE", "wetland", "id", "ID"]
    for col in candidates:
        if col in gdf.columns:
            return col
    return gdf.columns[0]


def _read_upload(uploaded):
    """Parse a FileUpload widget value → GeoDataFrame.

    Supports .geojson, .json and .zip (shapefile bundle).
    Works with both ipywidgets ≥8 (tuple of dicts) and older dict-style API.
    """
    if isinstance(uploaded, (list, tuple)) and len(uploaded) > 0:
        item = uploaded[0]
        fname   = item.get("name", "file")
        content = bytes(item.get("content", b""))
    elif isinstance(uploaded, dict) and uploaded:
        fname   = list(uploaded.keys())[0]
        content = bytes(uploaded[fname]["content"])
    else:
        raise ValueError("No file data received")

    fname_lower = fname.lower()
    if fname_lower.endswith((".geojson", ".json")):
        return gpd.read_file(io.BytesIO(content)).to_crs(4326), fname
    elif fname_lower.endswith(".zip"):
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / "upload.zip"
            zip_path.write_bytes(content)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(tmpdir)
            shp_files = list(Path(tmpdir).glob("**/*.shp"))
            if not shp_files:
                raise ValueError("No .shp file found inside the ZIP")
            return gpd.read_file(shp_files[0]).to_crs(4326), fname
    else:
        raise ValueError(f"Unsupported file type: {fname}. Use .geojson or .zip")


def _compute_twi(roi, dem_source="MERIT"):
    """Compute Topographic Wetness Index over an ROI.

    TWI = ln(a / tan(β)), with a = upstream area per unit contour length
    and β = local slope.

    Parameters
    ----------
    roi : ee.Geometry
    dem_source : {"MERIT", "HYBRID_30M"}
        - "MERIT": MERIT Hydro v1.0.1 (~90 m) for both elevation/slope and
          flow accumulation. Internally consistent.
        - "HYBRID_30M": NASADEM (30 m) for elevation/slope, MERIT `upa`
          reprojected for flow accumulation. The accumulation component
          remains from the 90 m MERIT data — true on-the-fly sink-filling +
          D8 routing at 30 m is not practical in GEE.
    """
    merit = ee.Image("MERIT/Hydro/v1_0_1")
    upa   = merit.select("upa")  # upstream drainage area, km²

    if dem_source == "HYBRID_30M":
        elev = ee.Image("NASA/NASADEM_HGT/001").select("elevation")
    else:
        elev = merit.select("elv")

    slope_deg = ee.Terrain.slope(elev)
    tan_slope = slope_deg.multiply(ee.Number(3.141592653589793).divide(180)) \
                         .tan().max(0.001)

    # Specific catchment area: upa (km²) → m², divided by contour length
    # approximated as sqrt(pixel area) at the local projection.
    cell_width = ee.Image.pixelArea().sqrt()
    a = upa.multiply(1e6).divide(cell_width)

    return a.divide(tan_slope).log().rename("twi").clip(roi)


# --------------------------------------------------------------------------- #
# Main widget                                                                  #
# --------------------------------------------------------------------------- #

def HydroperiodApp(
    m=None,
    basin_shp=None,
    wetlands_shp=None,
    elter_geojson=None,
    wetland_name_col=None,
):
    """Interactive hydroperiod analysis widget for Danube basin wetlands.

    Parameters
    ----------
    m : geemap.Map
        A geemap Map instance to attach the widget to.
    basin_shp : str or Path, optional
        Danube basin shapefile. Defaults to ``DRBD_2021.shp`` in the repo root.
    wetlands_shp : str or Path, optional
        Wetlands shapefile. Defaults to ``humedales_danubio.shp`` in the repo root.
    elter_geojson : str or Path, optional
        Pre-computed eLTER sites within the Danube basin. Defaults to
        ``elter_danube.geojson`` in the repo root. Regenerate via
        ``scripts/build_elter_danube.py``.
    wetland_name_col : str, optional
        Column in *wetlands_shp* to use as display label. Auto-detected if None.
    """

    # ------------------------------------------------------------------ #
    # Load shapefiles (local — no EE call at startup)                      #
    # ------------------------------------------------------------------ #
    basin_path    = Path(basin_shp)    if basin_shp    else DATA_DIR / "DRBD_2021.shp"
    wetlands_path = Path(wetlands_shp) if wetlands_shp else DATA_DIR / "humedales_danubio.shp"
    elter_path    = Path(elter_geojson) if elter_geojson else DATA_DIR / "elter_danube.geojson"

    basin_gdf    = gpd.read_file(basin_path).to_crs(4326)
    wetlands_gdf = gpd.read_file(wetlands_path).to_crs(4326)

    if elter_path.exists():
        elter_gdf = gpd.read_file(elter_path).to_crs(4326)
        elter_names = sorted(elter_gdf["name"].astype(str).tolist())
    else:
        elter_gdf = None
        elter_names = []

    if wetland_name_col is None:
        wetland_name_col = _detect_name_col(wetlands_gdf)

    wetland_names = sorted(wetlands_gdf[wetland_name_col].astype(str).tolist())

    # ------------------------------------------------------------------ #
    # Map setup                                                            #
    # ------------------------------------------------------------------ #
    minx, miny, maxx, maxy = basin_gdf.total_bounds
    pad = 1.5

    # ipyleaflet max_bounds must be a tuple-of-tuples: ((lat_sw, lng_sw), (lat_ne, lng_ne))
    basin_max_bounds = ((miny - pad, minx - pad), (maxy + pad, maxx + pad))

    if m is not None:
        m.add_basemap("Esri.WorldImagery")

        # Hard-stop panning/zooming outside the Danube basin
        m.max_bounds = basin_max_bounds
        m.min_zoom   = 5          # prevents zooming out past basin scale

        # Load layers locally (GeoJSON, instant — no EE round-trip)
        m.add_gdf(
            basin_gdf,
            layer_name="Danube Basin",
            style={"color": "#FFD700", "fillOpacity": 0, "weight": 3},
        )
        m.add_gdf(
            wetlands_gdf,
            layer_name="Wetlands",
            style={"color": "#00BFFF", "fillColor": "#00BFFF", "fillOpacity": 0.15, "weight": 2},
        )
        if elter_gdf is not None and not elter_gdf.empty:
            m.add_gdf(
                elter_gdf,
                layer_name="eLTER sites (Danube)",
                style={"color": "#2ecc71", "fillColor": "#2ecc71",
                       "fillOpacity": 0.10, "weight": 2},
            )

        # Centre on basin
        m.fit_bounds([[miny, minx], [maxy, maxx]])

        # DrawControl — always present, activated via button
        draw_control = ipyleaflet.DrawControl(
            polygon  ={"shapeOptions": {"color": "#e74c3c", "fillOpacity": 0.10, "weight": 2}},
            rectangle={"shapeOptions": {"color": "#e74c3c", "fillOpacity": 0.10, "weight": 2}},
            circle={}, polyline={}, marker={}, circlemarker={},
        )
        m.add_control(draw_control)
    else:
        draw_control = None

    # ------------------------------------------------------------------ #
    # Widget layout constants                                              #
    # ------------------------------------------------------------------ #
    W    = "370px"
    PAD  = "0px 0px 0px 4px"
    STYLE = {"description_width": "initial"}
    BTN_W = "85px"

    # ------------------------------------------------------------------ #
    # Toolbar toggle buttons                                               #
    # ------------------------------------------------------------------ #
    toolbar_button = widgets.ToggleButton(
        value=False,
        tooltip="Restore4Life HydroApp",
        icon="tint",
        button_style="info",
        layout=widgets.Layout(width="28px", height="28px", padding="0px 0px 0px 4px"),
    )
    close_button = widgets.ToggleButton(
        value=False,
        tooltip="Close",
        icon="times",
        button_style="primary",
        layout=widgets.Layout(width="28px", height="28px", padding="0px 0px 0px 4px"),
    )

    # ------------------------------------------------------------------ #
    # Controls — Hydroperiod tab                                           #
    # ------------------------------------------------------------------ #
    logo_path = DATA_DIR / "logo.png"
    if logo_path.exists():
        logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()
        logo_html = (
            f'<img src="data:image/png;base64,{logo_b64}" '
            'style="height:20px;vertical-align:middle;margin-right:6px"/>'
        )
    else:
        logo_html = "🌊 "

    title_html = widgets.HTML(
        value=f'<b style="font-size:13px;color:#0d47a1">{logo_html}Restore4Life — HydroApp</b>',
        layout=widgets.Layout(padding="4px 0px 6px 4px"),
    )

    wetland_dd = widgets.Dropdown(
        options=["— select wetland —"] + wetland_names,
        value="— select wetland —",
        description="Wetland:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    elter_placeholder = "— select eLTER site —"
    elter_dd = widgets.Dropdown(
        options=[elter_placeholder] + elter_names,
        value=elter_placeholder,
        description="eLTER site:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
        disabled=not elter_names,
    )

    # ------------------------------------------------------------------ #
    # Custom ROI section                                                   #
    # ------------------------------------------------------------------ #
    roi_section_html = widgets.HTML(
        value='<small style="color:#555;font-weight:bold">— or use a custom ROI —</small>',
        layout=widgets.Layout(padding="6px 0px 2px 4px"),
    )

    upload_w = widgets.FileUpload(
        accept=".geojson,.json,.zip",
        multiple=False,
        description="Upload",
        layout=widgets.Layout(width="140px"),
    )

    draw_btn = widgets.ToggleButton(
        value=False,
        description="Draw on map",
        icon="pencil",
        button_style="",
        layout=widgets.Layout(width="130px", height="32px"),
    )

    clear_roi_btn = widgets.Button(
        description="Clear ROI",
        button_style="warning",
        icon="trash",
        layout=widgets.Layout(width="100px", height="32px"),
    )

    roi_lbl = widgets.Label(
        value="",
        layout=widgets.Layout(width=W, padding=PAD),
    )

    dataset_dd = widgets.Dropdown(
        options=["S2", "Landsat", "MODIS"],
        value="S2",
        description="Dataset:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    start_year_w = widgets.BoundedIntText(
        value=2019, min=2017, max=2025,
        description="Start year:",
        style=STYLE,
        layout=widgets.Layout(width="175px", padding=PAD),
    )
    end_year_w = widgets.BoundedIntText(
        value=2023, min=2017, max=2025,
        description="End year:",
        style=STYLE,
        layout=widgets.Layout(width="175px", padding=PAD),
    )

    clouds_w = widgets.IntSlider(
        description="Max clouds %:", value=20, min=0, max=100,
        readout=False, style=STYLE,
        layout=widgets.Layout(width="295px", padding=PAD),
    )
    clouds_lbl = widgets.Label(value="20")

    windex_dd = widgets.Dropdown(
        options=_SENSOR_WATER_INDICES["S2"],
        value="mndwi",
        description="Water index:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    threshold_w = widgets.FloatSlider(
        description="Threshold:", value=0.0, min=-1.0, max=1.0, step=0.01,
        readout_format=".2f", readout=False, style=STYLE,
        layout=widgets.Layout(width="295px", padding=PAD),
    )
    threshold_lbl = widgets.Label(value="0.00")

    band_dd = widgets.Dropdown(
        options=["normalized", "hydroperiod", "valid_days",
                 "first_flood_doy", "last_flood_doy", "irt"],
        value="normalized",
        description="Band:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    year_dd = widgets.Dropdown(
        options=[], value=None,
        description="Hyd. year:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    # ------------------------------------------------------------------ #
    # Controls — Anomalies tab                                             #
    # ------------------------------------------------------------------ #
    anom_ref_dd = widgets.Dropdown(
        options=[
            ("Period mean (selected years)", "period"),
            ("Historical (full archive)", "historical"),
        ],
        value="period",
        description="Reference:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    anom_year_dd = widgets.Dropdown(
        options=[], value=None,
        description="Hyd. year:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    anom_run_btn = widgets.Button(
        description="Compute anomalies",
        button_style="warning",
        tooltip="Compute anomalies relative to the selected reference",
        layout=widgets.Layout(width="180px"),
    )
    anom_show_mean_btn = widgets.Button(
        description="Show mean",
        button_style="primary",
        layout=widgets.Layout(width="110px"),
    )
    anom_show_anom_btn = widgets.Button(
        description="Show anomaly",
        button_style="primary",
        layout=widgets.Layout(width="120px"),
    )

    anom_output_w = widgets.Output(
        layout=widgets.Layout(width=W, padding=PAD, max_height="120px", overflow_y="auto")
    )

    # ------------------------------------------------------------------ #
    # Export tab                                                           #
    # ------------------------------------------------------------------ #
    exp_folder_w = widgets.Text(
        value="restore4life_hydroperiod",
        description="Drive folder:",
        style=STYLE,
        layout=widgets.Layout(width="280px", padding=PAD),
    )
    exp_scale_w = widgets.Dropdown(
        options=[10, 20, 30, 100, 250, 500],
        value=10,
        description="Scale (m):",
        style=STYLE,
        layout=widgets.Layout(width="200px", padding=PAD),
    )

    # ------------------------------------------------------------------ #
    # Controls — TWI tab                                                   #
    # ------------------------------------------------------------------ #
    twi_source_dd = widgets.Dropdown(
        options=[
            ("MERIT Hydro (~90 m, consistent)", "MERIT"),
            ("Hybrid 30 m (NASADEM slope + MERIT acc.)", "HYBRID_30M"),
        ],
        value="MERIT",
        description="DEM:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    twi_run_btn = widgets.Button(
        description="Compute TWI", button_style="success",
        tooltip="Compute Topographic Wetness Index for current ROI",
        layout=widgets.Layout(width="130px"),
    )
    twi_show_btn = widgets.Button(
        description="Show", button_style="primary",
        layout=widgets.Layout(width="80px"),
    )
    twi_export_btn = widgets.Button(
        description="Export", button_style="warning",
        tooltip="Export TWI to Google Drive",
        layout=widgets.Layout(width="90px"),
    )

    twi_export_scale_w = widgets.Dropdown(
        options=[30, 60, 90, 250, 500],
        value=90,
        description="Export scale (m):",
        style=STYLE,
        layout=widgets.Layout(width="220px", padding=PAD),
    )

    twi_output_w = widgets.Output(
        layout=widgets.Layout(
            width=W, padding=PAD, max_height="140px", overflow_y="auto",
        )
    )

    # ------------------------------------------------------------------ #
    # Controls — Stats tab                                                 #
    # ------------------------------------------------------------------ #
    stats_upload_w = widgets.FileUpload(
        accept=".geojson,.json,.zip",
        multiple=False,
        description="Upload",
        layout=widgets.Layout(width="140px"),
    )
    stats_upload_lbl = widgets.Label(
        value="",
        layout=widgets.Layout(width=W, padding=PAD),
    )

    stats_product_dd = widgets.Dropdown(
        options=[
            ("Hydroperiod (selected year + band)", "hydroperiod"),
            ("IRT",                                 "irt"),
            ("Mean hydroperiod (anomaly tab)",      "mean_hydroperiod"),
            ("Anomaly (selected year)",             "anomaly"),
            ("TWI",                                 "twi"),
        ],
        value="hydroperiod",
        description="Product:",
        layout=widgets.Layout(width=W, padding=PAD),
        style=STYLE,
    )

    stats_scale_w = widgets.BoundedIntText(
        value=10, min=1, max=1000,
        description="Scale (m):",
        style=STYLE,
        layout=widgets.Layout(width="200px", padding=PAD),
    )

    stats_compute_btn = widgets.Button(
        description="Compute stats", button_style="success",
        layout=widgets.Layout(width="140px"),
    )
    stats_save_btn = widgets.Button(
        description="Save CSV", button_style="primary",
        tooltip="Write CSV locally next to the notebook",
        layout=widgets.Layout(width="100px"),
    )
    stats_drive_btn = widgets.Button(
        description="Export to Drive", button_style="warning",
        tooltip="Server-side export (recommended for >1000 features)",
        layout=widgets.Layout(width="150px"),
    )

    stats_output_w = widgets.Output(
        layout=widgets.Layout(width=W, padding=PAD, max_height="120px", overflow_y="auto")
    )
    stats_table_w = widgets.Output(
        layout=widgets.Layout(width=W, padding=PAD, max_height="260px",
                              overflow_y="auto", overflow_x="auto")
    )

    # Main buttons
    run_btn = widgets.Button(
        description="Compute", button_style="success",
        tooltip="Compute hydroperiod cycles",
        layout=widgets.Layout(width=BTN_W),
    )
    show_btn = widgets.Button(
        description="Show", button_style="primary",
        tooltip="Add selected band to map",
        layout=widgets.Layout(width=BTN_W),
    )
    export_btn = widgets.Button(
        description="Export", button_style="warning",
        tooltip="Export all cycles to Google Drive",
        layout=widgets.Layout(width=BTN_W),
    )
    reset_btn = widgets.Button(
        description="Reset", button_style="danger",
        layout=widgets.Layout(width=BTN_W),
    )

    output_w = widgets.Output(
        layout=widgets.Layout(
            width=W, padding=PAD, max_height="160px", overflow_y="auto",
        )
    )

    # ------------------------------------------------------------------ #
    # Shared state                                                         #
    # ------------------------------------------------------------------ #
    _st = {
        "ha":        None,
        "cycles":    None,
        "anomalies": None,    # {'mean': ee.Image, 'anomalies': {yr: ee.Image}}
        "irt_img":   None,
        "year_map":  {},       # "2022/2023" → 2022
        "roi":       None,
        "custom_roi": False,  # True when ROI comes from upload/draw (not wetland)
        "twi_img":    None,
        "twi_source": None,
        "stats_fc":      None,    # ee.FeatureCollection
        "stats_gdf":     None,    # local GeoDataFrame
        "stats_geom":    None,    # "Point" or "Polygon"
        "stats_namecol": None,
        "stats_df":      None,    # pandas DataFrame with last results
    }

    # ------------------------------------------------------------------ #
    # Callbacks — sliders                                                  #
    # ------------------------------------------------------------------ #

    def _update_clouds_lbl(change):
        clouds_lbl.value = str(change["new"])
    clouds_w.observe(_update_clouds_lbl, names="value")

    def _update_threshold_lbl(change):
        threshold_lbl.value = f"{change['new']:.2f}"
    threshold_w.observe(_update_threshold_lbl, names="value")

    def _dataset_change(change):
        sat = change["new"]
        mn = _SENSOR_MIN_YEAR[sat]
        start_year_w.min = mn
        end_year_w.min = mn
        if start_year_w.value < mn:
            start_year_w.value = mn
        if end_year_w.value < mn:
            end_year_w.value = mn
        current = windex_dd.value
        new_opts = _SENSOR_WATER_INDICES[sat]
        windex_dd.options = new_opts
        windex_dd.value = current if current in new_opts else new_opts[0]
        exp_scale_w.value = 500 if sat == "MODIS" else (30 if sat == "Landsat" else 10)

    dataset_dd.observe(_dataset_change, "value")

    # ------------------------------------------------------------------ #
    # Callbacks — ROI                                                      #
    # ------------------------------------------------------------------ #

    def _wetland_change(change):
        val = change["new"]
        if val and val != "— select wetland —":
            row = wetlands_gdf[wetlands_gdf[wetland_name_col].astype(str) == val].iloc[0]
            single = gpd.GeoDataFrame([row], crs=wetlands_gdf.crs)
            _st["roi"]        = _gdf_to_ee(single).geometry()
            _st["custom_roi"] = False
            roi_lbl.value     = ""
            draw_btn.value    = False
            if elter_dd.value != elter_placeholder:
                elter_dd.value = elter_placeholder
            if m is not None:
                m.centerObject(_st["roi"], 11)
        else:
            if not _st["custom_roi"]:
                _st["roi"] = None

    wetland_dd.observe(_wetland_change, "value")

    def _elter_change(change):
        val = change["new"]
        if val and val != elter_placeholder and elter_gdf is not None:
            row = elter_gdf[elter_gdf["name"].astype(str) == val].iloc[0]
            single = gpd.GeoDataFrame([row], crs=elter_gdf.crs)
            _st["roi"]        = _gdf_to_ee(single).geometry()
            _st["custom_roi"] = False
            roi_lbl.value     = ""
            draw_btn.value    = False
            if wetland_dd.value != "— select wetland —":
                wetland_dd.value = "— select wetland —"
            if m is not None:
                m.centerObject(_st["roi"], 11)
        else:
            if not _st["custom_roi"] and wetland_dd.value == "— select wetland —":
                _st["roi"] = None

    elter_dd.observe(_elter_change, "value")

    def _handle_upload(change):
        uploaded = change["new"]
        if not uploaded:
            return
        try:
            gdf, fname = _read_upload(uploaded)
            _st["roi"]        = _gdf_to_ee(gdf).geometry()
            _st["custom_roi"] = True
            roi_lbl.value     = f"ROI: {fname} ({len(gdf)} feature(s))"
            wetland_dd.value  = "— select wetland —"
            elter_dd.value    = elter_placeholder
            draw_btn.value    = False
            if m is not None:
                m.add_gdf(
                    gdf,
                    layer_name="Custom ROI",
                    style={"color": "#e74c3c", "fillColor": "#e74c3c",
                           "fillOpacity": 0.10, "weight": 2},
                )
                b = gdf.total_bounds   # minx, miny, maxx, maxy
                m.fit_bounds([[b[1], b[0]], [b[3], b[2]]])
        except Exception as exc:
            roi_lbl.value = f"Upload error: {exc}"

    upload_w.observe(_handle_upload, names="value")

    # DrawControl callback
    if draw_control is not None:
        def _on_draw(self, action, geo_json):
            if action == "created":
                geom              = geo_json["geometry"]
                _st["roi"]        = ee.Geometry(geom)
                _st["custom_roi"] = True
                roi_lbl.value     = f"ROI: drawn {geom['type']}"
                wetland_dd.value  = "— select wetland —"
                elter_dd.value    = elter_placeholder
                draw_btn.value    = False

        draw_control.on_draw(_on_draw)

    def _draw_btn_click(change):
        if change["new"]:
            roi_lbl.value = "Draw a polygon or rectangle on the map…"
        else:
            if roi_lbl.value == "Draw a polygon or rectangle on the map…":
                roi_lbl.value = ""

    draw_btn.observe(_draw_btn_click, "value")

    def _clear_roi_clicked(b):
        _st["roi"]        = None
        _st["custom_roi"] = False
        roi_lbl.value     = ""
        draw_btn.value    = False
        wetland_dd.value  = "— select wetland —"
        elter_dd.value    = elter_placeholder
        if draw_control is not None:
            draw_control.clear()

    clear_roi_btn.on_click(_clear_roi_clicked)

    # ------------------------------------------------------------------ #
    # Callbacks — Compute / Show / Export / Reset                          #
    # ------------------------------------------------------------------ #

    def _run_clicked(b):
        with output_w:
            output_w.clear_output()

            if _st["roi"] is None:
                print("Select a wetland or set a custom ROI first.")
                return

            sy = start_year_w.value
            ey = end_year_w.value
            if sy > ey:
                print("Start year must be ≤ end year.")
                return

            sat = dataset_dd.value
            idx = windex_dd.value
            thr = threshold_w.value
            cl  = clouds_w.value
            roi = _st["roi"]

            print(f"[1/3] Building NdviSeasonality ({sat}, {sy}–{ey}, clouds≤{cl}%)…")
            try:
                ns = NdviSeasonality(
                    roi=roi,
                    sat=sat,
                    start_year=sy,
                    end_year=ey,
                    max_cloud_cover=cl,
                )
                ha = HydroperiodAnalyzer(ns)
                _st["ha"]        = ha
                _st["anomalies"] = None
                _st["irt_img"]   = None

                print(f"[2/3] Computing hydroperiod cycles with index='{idx}', threshold={thr:.2f}…")
                cycles = ha.compute_all_cycles(index=idx, threshold=thr)
                _st["cycles"] = cycles

                years    = sorted(cycles.keys())
                year_map = {f"{y}/{y+1}": y for y in years}
                _st["year_map"] = year_map

                year_dd.options      = list(year_map.keys())
                year_dd.value        = year_dd.options[-1]
                anom_year_dd.options = list(year_map.keys())
                anom_year_dd.value   = anom_year_dd.options[-1]

                print(f"[3/3] Done! {len(cycles)} cycle(s) ready.")
                print("→ Use 'Show' to visualize or switch to the Anomalies / Export tabs.")

            except Exception as exc:
                print(f"Error: {exc}")

    run_btn.on_click(_run_clicked)

    def _current_site_label():
        if elter_dd.value and elter_dd.value != elter_placeholder:
            return elter_dd.value
        if wetland_dd.value and wetland_dd.value != "— select wetland —":
            return wetland_dd.value
        return "custom"

    def _show_clicked(b):
        with output_w:
            output_w.clear_output()

            if _st["cycles"] is None:
                print("No results yet — click 'Compute' first.")
                return

            yr_label = year_dd.value
            if yr_label is None:
                print("Select a hydrological year.")
                return

            band = band_dd.value
            site = _current_site_label()

            if band == "irt":
                if _st["irt_img"] is None:
                    print("Computing per-pixel IRT…")
                    try:
                        _st["irt_img"] = _st["ha"].compute_irt_image()
                        print("IRT ready.")
                    except Exception as exc:
                        print(f"Error: {exc}")
                        return
                img        = _st["irt_img"]
                layer_name = f"IRT — {site}"
            else:
                yr         = _st["year_map"][yr_label]
                img        = _st["cycles"][yr].select(band)
                layer_name = f"{band} {yr_label} — {site}"

            vis = _VIS.get(band, {"min": 0, "max": 365})
            if m is not None:
                m.addLayer(img, vis, layer_name)
                print(f"Layer added: '{layer_name}'")

    show_btn.on_click(_show_clicked)

    # -- Anomaly callbacks ------------------------------------------------

    def _anom_run_clicked(b):
        with anom_output_w:
            anom_output_w.clear_output()

            if _st["ha"] is None or _st["cycles"] is None:
                print("Run 'Compute' (hydroperiod tab) first.")
                return

            ref = anom_ref_dd.value
            print(f"Computing anomalies (reference='{ref}')…")
            try:
                result = _st["ha"].compute_anomalies(
                    cycles=_st["cycles"],
                    reference=ref,
                )
                _st["anomalies"] = result
                print("Anomalies ready.")
                print("→ 'Show mean' for the reference mean hydroperiod.")
                print("→ 'Show anomaly' for the selected cycle anomaly.")
            except Exception as exc:
                print(f"Error: {exc}")

    anom_run_btn.on_click(_anom_run_clicked)

    def _anom_show_mean_clicked(b):
        with anom_output_w:
            anom_output_w.clear_output()
            if _st["anomalies"] is None:
                print("Compute anomalies first.")
                return
            img        = _st["anomalies"]["mean"]
            layer_name = f"Mean hydroperiod ({anom_ref_dd.value}) — {_current_site_label()}"
            if m is not None:
                m.addLayer(img, _VIS["mean_hydroperiod"], layer_name)
                print(f"Layer added: '{layer_name}'")

    anom_show_mean_btn.on_click(_anom_show_mean_clicked)

    def _anom_show_anom_clicked(b):
        with anom_output_w:
            anom_output_w.clear_output()
            if _st["anomalies"] is None:
                print("Compute anomalies first.")
                return
            yr_label = anom_year_dd.value
            if yr_label is None:
                print("Select a hydrological year.")
                return
            yr         = _st["year_map"][yr_label]
            img        = _st["anomalies"]["anomalies"][yr]
            layer_name = f"Anomaly {yr_label} ({anom_ref_dd.value}) — {_current_site_label()}"
            if m is not None:
                m.addLayer(img, _VIS["anomaly"], layer_name)
                print(f"Layer added: '{layer_name}'")

    anom_show_anom_btn.on_click(_anom_show_anom_clicked)

    # -- TWI callbacks ----------------------------------------------------

    def _twi_roi_label():
        if _st["custom_roi"]:
            return roi_lbl.value.replace("ROI: ", "").split(" (")[0] or "custom"
        return _current_site_label()

    def _twi_run_clicked(b):
        with twi_output_w:
            twi_output_w.clear_output()
            if _st["roi"] is None:
                print("Select a wetland or set a custom ROI first.")
                return
            src = twi_source_dd.value
            print(f"Computing TWI (source='{src}')…")
            try:
                img = _compute_twi(_st["roi"], dem_source=src)
                _st["twi_img"]    = img
                _st["twi_source"] = src
                print("TWI ready. Click 'Show' to add it to the map.")
            except Exception as exc:
                print(f"Error: {exc}")

    twi_run_btn.on_click(_twi_run_clicked)

    def _twi_show_clicked(b):
        with twi_output_w:
            twi_output_w.clear_output()
            if _st["twi_img"] is None:
                print("Compute TWI first.")
                return
            layer_name = f"TWI ({_st['twi_source']}) — {_twi_roi_label()}"
            if m is not None:
                m.addLayer(_st["twi_img"], _VIS["twi"], layer_name)
                print(f"Layer added: '{layer_name}'")

    twi_show_btn.on_click(_twi_show_clicked)

    def _twi_export_clicked(b):
        with twi_output_w:
            twi_output_w.clear_output()
            if _st["twi_img"] is None:
                print("Compute TWI first.")
                return
            folder = exp_folder_w.value.strip() or "restore4life_hydroperiod"
            scale  = twi_export_scale_w.value
            label  = _twi_roi_label().replace(" ", "_").replace("/", "-")
            desc   = f"twi_{_st['twi_source']}_{label}"
            try:
                task = ee.batch.Export.image.toDrive(
                    image=_st["twi_img"],
                    description=desc,
                    folder=folder,
                    fileNamePrefix=desc,
                    region=_st["roi"],
                    scale=scale,
                    maxPixels=1e13,
                )
                task.start()
                print(f"Export task '{desc}' started → Drive folder '{folder}'")
            except Exception as exc:
                print(f"Error: {exc}")

    twi_export_btn.on_click(_twi_export_clicked)

    # -- Stats callbacks --------------------------------------------------

    def _stats_upload_change(change):
        val = change["new"]
        if not val:
            return
        try:
            gdf, fname = _read_upload(val)
            gtype = str(gdf.geom_type.iloc[0])
            if "Point" in gtype:
                geom = "Point"
            elif "Polygon" in gtype:
                geom = "Polygon"
            else:
                raise ValueError(f"Unsupported geometry: {gtype}")
            name_col = _detect_name_col(gdf)
            _st["stats_gdf"]     = gdf
            _st["stats_fc"]      = _gdf_to_ee(gdf)
            _st["stats_geom"]    = geom
            _st["stats_namecol"] = name_col
            stats_upload_lbl.value = (
                f"{fname} — {len(gdf)} {geom.lower()}(s), label col: '{name_col}'"
            )
        except Exception as exc:
            stats_upload_lbl.value = f"Upload error: {exc}"

    stats_upload_w.observe(_stats_upload_change, names="value")

    def _stats_resolve():
        """Resolve current product selection to (ee.Image, label)."""
        prod = stats_product_dd.value
        if prod == "hydroperiod":
            if _st["cycles"] is None:
                raise ValueError("Run 'Compute' (Hydroperiod) first.")
            if year_dd.value is None:
                raise ValueError("Select a hyd. year in the Hydroperiod tab.")
            band = band_dd.value
            if band == "irt":
                if _st["irt_img"] is None:
                    raise ValueError(
                        "Click 'Show' with band='irt' first, or switch the band."
                    )
                return _st["irt_img"].rename("irt"), "irt"
            yr = _st["year_map"][year_dd.value]
            return _st["cycles"][yr].select(band).rename(band), f"{band}_{yr}_{yr+1}"
        if prod == "irt":
            if _st["irt_img"] is None:
                raise ValueError("Click 'Show' with band='irt' in the Hydroperiod tab first.")
            return _st["irt_img"].rename("irt"), "irt"
        if prod == "mean_hydroperiod":
            if _st["anomalies"] is None:
                raise ValueError("Run 'Compute anomalies' first.")
            return _st["anomalies"]["mean"].rename("mean_hydroperiod"), "mean_hydroperiod"
        if prod == "anomaly":
            if _st["anomalies"] is None:
                raise ValueError("Run 'Compute anomalies' first.")
            if anom_year_dd.value is None:
                raise ValueError("Select a hyd. year in the Anomalies tab.")
            yr = _st["year_map"][anom_year_dd.value]
            return _st["anomalies"]["anomalies"][yr].rename("anomaly"), f"anomaly_{yr}_{yr+1}"
        if prod == "twi":
            if _st["twi_img"] is None:
                raise ValueError("Compute TWI first.")
            return _st["twi_img"].rename("twi"), f"twi_{_st['twi_source']}"
        raise ValueError(f"Unknown product: {prod}")

    def _stats_product_change(change):
        prod = change["new"]
        if prod == "twi":
            stats_scale_w.value = 90
        else:
            sensor = dataset_dd.value
            stats_scale_w.value = {"S2": 10, "Landsat": 30, "MODIS": 500}.get(sensor, 30)

    stats_product_dd.observe(_stats_product_change, "value")

    def _stats_reducer(geom):
        if geom == "Point":
            return ee.Reducer.first()
        return (ee.Reducer.mean()
                .combine(ee.Reducer.median(), sharedInputs=True)
                .combine(ee.Reducer.min(),    sharedInputs=True)
                .combine(ee.Reducer.max(),    sharedInputs=True)
                .combine(ee.Reducer.stdDev(), sharedInputs=True)
                .combine(ee.Reducer.count(),  sharedInputs=True))

    def _stats_compute_clicked(b):
        with stats_output_w:
            stats_output_w.clear_output()
            if _st["stats_fc"] is None:
                print("Upload a shapefile / GeoJSON first.")
                return
            try:
                img, label = _stats_resolve()
            except Exception as exc:
                print(f"Error: {exc}")
                return

            fc       = _st["stats_fc"]
            geom     = _st["stats_geom"]
            name_col = _st["stats_namecol"]
            scale    = stats_scale_w.value
            n        = len(_st["stats_gdf"])

            if n > 1000:
                print(f"{n} features — that's large for an in-browser fetch. "
                      "Consider 'Export to Drive' instead.")

            print(f"Computing {label} stats on {n} {geom.lower()}(s) at {scale} m…")
            try:
                result = img.reduceRegions(
                    collection=fc,
                    reducer=_stats_reducer(geom),
                    scale=scale,
                )
                data = result.getInfo()
                rows = []
                for feat in data.get("features", []):
                    props = dict(feat.get("properties", {}))
                    props["_fid"] = feat.get("id", "")
                    if name_col and name_col in props and "name" not in props:
                        props["name"] = props[name_col]
                    rows.append(props)
                df = pd.DataFrame(rows)
                _st["stats_df"] = df
                print(f"Done: {len(df)} row(s), {len(df.columns)} column(s).")
                with stats_table_w:
                    stats_table_w.clear_output()
                    display(df)
            except Exception as exc:
                print(f"Error: {exc}")

    stats_compute_btn.on_click(_stats_compute_clicked)

    def _stats_save_clicked(b):
        with stats_output_w:
            if _st["stats_df"] is None:
                print("Compute stats first.")
                return
            ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = Path.cwd() / f"stats_{ts}.csv"
            _st["stats_df"].to_csv(path, index=False)
            print(f"Saved: {path}")

    stats_save_btn.on_click(_stats_save_clicked)

    def _stats_drive_clicked(b):
        with stats_output_w:
            stats_output_w.clear_output()
            if _st["stats_fc"] is None:
                print("Upload a shapefile / GeoJSON first.")
                return
            try:
                img, label = _stats_resolve()
            except Exception as exc:
                print(f"Error: {exc}")
                return
            result = img.reduceRegions(
                collection=_st["stats_fc"],
                reducer=_stats_reducer(_st["stats_geom"]),
                scale=stats_scale_w.value,
            )
            folder = exp_folder_w.value.strip() or "restore4life_hydroperiod"
            desc   = f"stats_{label}"
            try:
                task = ee.batch.Export.table.toDrive(
                    collection=result,
                    description=desc,
                    folder=folder,
                    fileNamePrefix=desc,
                    fileFormat="CSV",
                )
                task.start()
                print(f"Export task '{desc}' started → Drive folder '{folder}'")
            except Exception as exc:
                print(f"Error: {exc}")

    stats_drive_btn.on_click(_stats_drive_clicked)

    # -- Export callback --------------------------------------------------

    def _export_clicked(b):
        with output_w:
            output_w.clear_output()
            if _st["ha"] is None or _st["cycles"] is None:
                print("No results — click 'Compute' first.")
                return
            folder     = exp_folder_w.value.strip() or "restore4life_hydroperiod"
            scale      = exp_scale_w.value
            site_label = _current_site_label().replace(" ", "_").replace("/", "-")
            for yr, img in _st["cycles"].items():
                desc = f"hydroperiod_{site_label}_{yr}_{yr + 1}"
                _st["ha"].export_to_drive(image=img, folder=folder,
                                          description=desc, scale=scale)
            print(f"{len(_st['cycles'])} export task(s) started → Drive folder '{folder}'")

    export_btn.on_click(_export_clicked)

    def _reset_clicked(b):
        output_w.clear_output()
        anom_output_w.clear_output()
        _st.update(ha=None, cycles=None, anomalies=None, irt_img=None,
                   year_map={}, roi=None, custom_roi=False,
                   twi_img=None, twi_source=None,
                   stats_fc=None, stats_gdf=None, stats_geom=None,
                   stats_namecol=None, stats_df=None)
        twi_output_w.clear_output()
        stats_output_w.clear_output()
        stats_table_w.clear_output()
        stats_upload_lbl.value = ""
        year_dd.options      = []
        year_dd.value        = None
        anom_year_dd.options = []
        anom_year_dd.value   = None
        roi_lbl.value        = ""
        draw_btn.value       = False
        wetland_dd.value     = "— select wetland —"
        elter_dd.value       = elter_placeholder
        if draw_control is not None:
            draw_control.clear()

    reset_btn.on_click(_reset_clicked)

    # ------------------------------------------------------------------ #
    # Layout assembly                                                      #
    # ------------------------------------------------------------------ #

    # Tab 0 — Hydroperiod
    hydro_tab = widgets.VBox([
        wetland_dd,
        elter_dd,
        roi_section_html,
        widgets.HBox([upload_w, draw_btn, clear_roi_btn]),
        roi_lbl,
        dataset_dd,
        widgets.HBox([start_year_w, end_year_w]),
        widgets.HBox([clouds_w, clouds_lbl]),
        windex_dd,
        widgets.HBox([threshold_w, threshold_lbl]),
        band_dd,
        year_dd,
        widgets.HBox([run_btn, show_btn, reset_btn]),
        output_w,
    ])

    # Tab 1 — Anomalies
    anom_tab = widgets.VBox([
        widgets.HTML(
            value='<small style="color:#555">Run <b>Compute</b> in the Hydroperiod tab first.</small>',
            layout=widgets.Layout(padding="2px 0px 4px 4px"),
        ),
        anom_ref_dd,
        anom_year_dd,
        anom_run_btn,
        widgets.HBox([anom_show_mean_btn, anom_show_anom_btn]),
        anom_output_w,
    ])

    # Tab 2 — TWI
    twi_tab = widgets.VBox([
        widgets.HTML(
            value='<small style="color:#555">Uses the ROI from the Hydroperiod tab '
                  '(wetland / upload / draw).<br>Hybrid 30 m mixes NASADEM slope with '
                  'MERIT flow accumulation (still ~90 m).</small>',
            layout=widgets.Layout(padding="2px 0px 4px 4px"),
        ),
        twi_source_dd,
        widgets.HBox([twi_run_btn, twi_show_btn]),
        twi_export_scale_w,
        twi_export_btn,
        twi_output_w,
    ])

    # Tab 3 — Stats
    stats_tab = widgets.VBox([
        widgets.HTML(
            value='<small style="color:#555">Upload points or polygons and compute '
                  'per-feature stats over any product already computed in the other tabs.<br>'
                  'Uses the year/band currently selected in Hydroperiod / Anomalies.</small>',
            layout=widgets.Layout(padding="2px 0px 4px 4px"),
        ),
        widgets.HBox([stats_upload_w]),
        stats_upload_lbl,
        stats_product_dd,
        stats_scale_w,
        widgets.HBox([stats_compute_btn, stats_save_btn, stats_drive_btn]),
        stats_output_w,
        stats_table_w,
    ])

    # Tab 4 — Export
    export_tab = widgets.VBox([
        widgets.HTML(
            value='<small style="color:#555">Exports all computed hydroperiod cycles to Drive.</small>',
            layout=widgets.Layout(padding="2px 0px 4px 4px"),
        ),
        exp_folder_w,
        exp_scale_w,
        export_btn,
    ])

    tabs = widgets.Tab(children=[hydro_tab, anom_tab, twi_tab, stats_tab, export_tab])
    tabs.set_title(0, "Hydroperiod")
    tabs.set_title(1, "Anomalies")
    tabs.set_title(2, "TWI")
    tabs.set_title(3, "Stats")
    tabs.set_title(4, "Export")

    toolbar_footer = widgets.VBox(children=[title_html, tabs])

    toolbar_widget = widgets.VBox(
        layout=widgets.Layout(border="solid 1px #1565C0", border_radius="4px")
    )
    toolbar_widget.children = [toolbar_button]
    toolbar_header = widgets.HBox(children=[close_button, toolbar_button])

    toolbar_event = ipyevents.Event(
        source=toolbar_widget, watched_events=["mouseenter", "mouseleave"]
    )

    def _handle_toolbar_event(event):
        if event["type"] == "mouseenter":
            toolbar_widget.children = [toolbar_header, toolbar_footer]
        elif event["type"] == "mouseleave":
            if not toolbar_button.value:
                toolbar_widget.children = [toolbar_button]
                toolbar_button.value = False
                close_button.value   = False

    toolbar_event.on_dom_event(_handle_toolbar_event)

    def _toolbar_btn_click(change):
        if change["new"]:
            close_button.value = False
            toolbar_widget.children = [toolbar_header, toolbar_footer]
        else:
            if not close_button.value:
                toolbar_widget.children = [toolbar_button]

    toolbar_button.observe(_toolbar_btn_click, "value")

    def _close_btn_click(change):
        if change["new"]:
            toolbar_button.value = False
            if m is not None:
                tc = getattr(m, "tool_control", None)
                if tc is not None and tc in m.controls:
                    m.remove_control(tc)
                    m.tool_control = None
            toolbar_widget.close()

    close_button.observe(_close_btn_click, "value")

    toolbar_button.value = True

    if m is not None:
        toolbar_control = ipyleaflet.WidgetControl(
            widget=toolbar_widget, position="topright"
        )
        if toolbar_control not in m.controls:
            m.add_control(toolbar_control)
            m.tool_control = toolbar_control
    else:
        return toolbar_widget
