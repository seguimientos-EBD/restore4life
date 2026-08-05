"""
build_elter_danube.py — one-shot builder for data/elter_danube.geojson.

Queries DEIMS-SDR for the national networks of Danube-basin countries,
fetches each site's boundary, keeps only the sites that intersect the
Danube River Basin District (DRBD_2021.shp), and writes the result as
a GeoJSON consumed at runtime by restore4life.HydroperiodApp.

Run whenever you want to refresh the cached list:

    python scripts/build_elter_danube.py

Requires: deims, geopandas, shapely.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import deims
import geopandas as gpd
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
BASIN_SHP = REPO_ROOT / "DRBD_2021.shp"
OUT_PATH  = REPO_ROOT / "elter_danube.geojson"

# Networks covering countries that (partly) overlap the Danube basin.
# Network UUIDs taken from the eLTER DEIMS-SDR registry.
DANUBE_NETWORKS = {
    "Austria":     "d45c2690-dbef-4dbc-a742-26ea846edf28",
    "Bulgaria":    "20ad4fa2-cc07-4848-b9ed-8952c55f1a3f",
    "Germany":     "e904354a-f3a0-40ce-a9b5-61741f66c824",
    "Hungary":     "0615a89f-2883-47ab-8cd0-2508f413cab7",
    "Italy":       "7fef6b73-e5cb-4cd2-b438-ed32eb1504b3",
    "Poland":      "67763729-45a7-4248-a70d-622b1d0a3d41",
    "Romania":     "4260f964-0ac4-4406-8adc-5afc06e31779",
    "Slovakia":    "3d6a8d72-9f86-4082-ad56-a361b4cdc8a0",
    "Slovenia":    "fda2984f-9aea-4abf-9f6c-c3eca0f82eb8",
    "Switzerland": "cedf695c-c6dc-4660-b944-3c22f12ad0d9",
}


def _fetch_country_sites(country: str, network_id: str) -> gpd.GeoDataFrame:
    print(f"  [{country}] listing sites…", flush=True)
    site_ids = deims.getListOfSites(network_id)
    print(f"  [{country}] {len(site_ids)} sites, fetching boundaries…", flush=True)

    rows = []
    for i, sid in enumerate(site_ids, 1):
        try:
            gdf = deims.getSiteBoundaries(sid)
        except Exception as exc:
            print(f"    skip {sid}: {exc}", flush=True)
            continue
        if gdf is None or gdf.empty:
            continue
        gdf = gdf.copy()
        gdf["country"] = country
        rows.append(gdf)
        if i % 25 == 0:
            print(f"    {country}: {i}/{len(site_ids)}", flush=True)

    if not rows:
        return gpd.GeoDataFrame(
            columns=["name", "deimsid", "country", "geometry"], crs=4326
        )
    return gpd.GeoDataFrame(pd.concat(rows, ignore_index=True), crs=4326)


def main() -> int:
    if not BASIN_SHP.exists():
        print(f"ERROR: basin shapefile not found at {BASIN_SHP}", file=sys.stderr)
        return 1

    basin = gpd.read_file(BASIN_SHP).to_crs(4326)
    basin_union = basin.geometry.union_all() if hasattr(basin.geometry, "union_all") \
        else basin.geometry.unary_union

    all_sites: list[gpd.GeoDataFrame] = []
    t0 = time.time()
    for country, net_id in DANUBE_NETWORKS.items():
        try:
            country_gdf = _fetch_country_sites(country, net_id)
        except Exception as exc:
            print(f"  [{country}] network query failed: {exc}", file=sys.stderr)
            continue
        if not country_gdf.empty:
            all_sites.append(country_gdf)

    if not all_sites:
        print("No sites fetched. Aborting.", file=sys.stderr)
        return 2

    sites = gpd.GeoDataFrame(pd.concat(all_sites, ignore_index=True), crs=4326)
    sites = sites[~sites.geometry.is_empty & sites.geometry.notna()]
    print(f"Total sites fetched: {len(sites)}")

    mask = sites.geometry.intersects(basin_union)
    in_basin = sites[mask].copy()
    print(f"Sites intersecting Danube basin: {len(in_basin)}")

    keep_cols = [c for c in ("name", "deimsid", "country", "geometry") if c in in_basin.columns]
    in_basin = in_basin[keep_cols]
    in_basin = in_basin.sort_values("name").reset_index(drop=True)

    if OUT_PATH.exists():
        OUT_PATH.unlink()
    in_basin.to_file(OUT_PATH, driver="GeoJSON")
    print(f"Wrote {OUT_PATH} ({len(in_basin)} features) in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
