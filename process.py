"""Builds the scored facility dataset the dashboard reads.

Pipeline:
  1. Load the three critical-facility layers (hospitals, fire/EMS, shelters)
     and tag each with a facility_type.
  2. Measure distance from each facility to the nearest electric substation
     (grid exposure proxy).
  3. Check whether each facility sits inside a FEMA flood hazard zone
     (hazard exposure).
  4. Combine into one 0-100 Resilience Priority Score, grouped into
     Low/Moderate/High/Critical tiers.
  5. Measure how much existing solar capacity sits near each facility, and
     flag high-priority facilities with none nearby as DER siting candidates.

Run after fetch_data.py:
    python process.py
"""
import os

import geopandas as gpd
import pandas as pd

from config import (
    CRITICALITY_WEIGHTS,
    DER_OPPORTUNITY_MIN_TIER,
    DISTANCE_CRS,
    OUTPUT_PATH,
    PRIORITY_TIERS,
    RAW_DIR,
    SCORE_WEIGHTS,
    SOLAR_OUTPUT_PATH,
    SOLAR_PROXIMITY_RADIUS_MILES,
)

FACILITY_LAYERS = {
    "hospitals.geojson": "Hospital",
    "fire_ems_stations.geojson": "Fire/EMS Station",
    "homeless_shelters.geojson": "Homeless Shelter",
}

FEET_PER_MILE = 5280


def load_facilities():
    """Load and combine the three facility layers into one GeoDataFrame."""
    frames = []
    for filename, facility_type in FACILITY_LAYERS.items():
        path = os.path.join(RAW_DIR, filename)
        gdf = gpd.read_file(path)
        gdf = gdf[["NAME", "ADDRESS", "WARD", "geometry"]].copy()
        gdf["facility_type"] = facility_type
        frames.append(gdf)

    facilities = pd.concat(frames, ignore_index=True)
    facilities = gpd.GeoDataFrame(facilities, geometry="geometry", crs=frames[0].crs)
    facilities = facilities.rename(columns={"NAME": "name", "ADDRESS": "address", "WARD": "ward"})
    facilities["facility_id"] = range(len(facilities))
    return facilities


def add_grid_exposure(facilities):
    """Distance in miles to the nearest electric substation, then a 0-100
    normalized score where farther away = higher exposure."""
    substations = gpd.read_file(os.path.join(RAW_DIR, "electric_substations.geojson"))

    facilities_ft = facilities.to_crs(DISTANCE_CRS)
    substations_ft = substations.to_crs(DISTANCE_CRS)

    nearest = gpd.sjoin_nearest(facilities_ft, substations_ft, distance_col="distance_ft")
    nearest = nearest.drop_duplicates(subset="facility_id").set_index("facility_id")

    facilities = facilities.set_index("facility_id")
    facilities["distance_to_substation_miles"] = (nearest["distance_ft"] / FEET_PER_MILE).round(2)

    d = facilities["distance_to_substation_miles"]
    facilities["grid_exposure_score"] = ((d - d.min()) / (d.max() - d.min()) * 100).round(1)
    return facilities.reset_index()


def add_hazard_exposure(facilities):
    """Flags whether each facility falls inside a FEMA flood hazard zone."""
    floodplains = gpd.read_file(os.path.join(RAW_DIR, "floodplains.geojson"))
    floodplains = floodplains[["FLD_ZONE", "SFHA_TF", "geometry"]]

    joined = gpd.sjoin(facilities, floodplains, how="left", predicate="within")
    joined = joined.drop_duplicates(subset="facility_id").set_index("facility_id")

    def score_zone(sfha_flag, zone_label):
        if sfha_flag == "T":
            return 100, "High risk (Special Flood Hazard Area)"
        if isinstance(zone_label, str) and "0.2 PCT" in zone_label:
            return 50, "Moderate risk (0.2% annual chance)"
        return 0, "Minimal risk"

    scores, labels = zip(*[
        score_zone(sfha, zone)
        for sfha, zone in zip(joined["SFHA_TF"], joined["FLD_ZONE"])
    ])
    facilities = facilities.set_index("facility_id")
    facilities["hazard_exposure_score"] = pd.Series(scores, index=joined.index)
    facilities["flood_risk_label"] = pd.Series(labels, index=joined.index)
    return facilities.reset_index()


def add_resilience_score(facilities):
    facilities["criticality_score"] = facilities["facility_type"].map(CRITICALITY_WEIGHTS)

    facilities["resilience_score"] = (
        facilities["criticality_score"] * SCORE_WEIGHTS["criticality"]
        + facilities["grid_exposure_score"] * SCORE_WEIGHTS["grid_exposure"]
        + facilities["hazard_exposure_score"] * SCORE_WEIGHTS["hazard_exposure"]
    ).round(0).astype(int)

    def tier_for(score):
        for lo, hi, label in PRIORITY_TIERS:
            if lo <= score <= hi:
                return label
        return PRIORITY_TIERS[-1][2]

    facilities["priority_tier"] = facilities["resilience_score"].apply(tier_for)
    return facilities


def load_solar_projects():
    solar = gpd.read_file(os.path.join(RAW_DIR, "solar_projects.geojson"))
    solar = solar[["Site_Name", "Ward", "Capacity_k", "HH_Served", "Type_of_in", "geometry"]].copy()
    solar = solar.rename(columns={
        "Site_Name": "site_name",
        "Ward": "ward",
        "Capacity_k": "capacity_kw",
        "HH_Served": "households_served",
        "Type_of_in": "installation_type",
    })
    solar["capacity_kw"] = solar["capacity_kw"].fillna(0)
    solar["ward"] = solar["ward"].apply(_normalize_ward)
    return solar


def _normalize_ward(value):
    """The raw ward field is inconsistent ('Ward 7', '7', blank, or a
    non-DC city for a handful of records) — normalize to 'Ward N' or
    'Other/Unspecified' so the ward chart only shows DC's 8 wards."""
    if not isinstance(value, str):
        return "Other/Unspecified"
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits and digits in {"1", "2", "3", "4", "5", "6", "7", "8"}:
        return f"Ward {digits}"
    return "Other/Unspecified"


def add_clean_energy_proximity(facilities, solar):
    """For each facility: distance to the nearest existing solar project,
    and total solar capacity already installed within the proximity radius."""
    radius_ft = SOLAR_PROXIMITY_RADIUS_MILES * FEET_PER_MILE

    facilities_ft = facilities.to_crs(DISTANCE_CRS)
    solar_ft = solar.to_crs(DISTANCE_CRS)

    nearest = gpd.sjoin_nearest(facilities_ft, solar_ft, distance_col="distance_ft")
    nearest = nearest.drop_duplicates(subset="facility_id").set_index("facility_id")

    buffers = facilities_ft.set_index("facility_id").copy()
    buffers["geometry"] = buffers.geometry.buffer(radius_ft)
    nearby = gpd.sjoin(solar_ft, buffers[["geometry"]], how="inner", predicate="within")
    nearby_capacity = nearby.groupby("facility_id")["capacity_kw"].sum()

    facilities = facilities.set_index("facility_id")
    facilities["distance_to_solar_miles"] = (nearest["distance_ft"] / FEET_PER_MILE).round(2)
    facilities["nearby_solar_capacity_kw"] = nearby_capacity.reindex(facilities.index).fillna(0).round(1)
    return facilities.reset_index()


def add_der_opportunity_flag(facilities):
    tier_order = [label for _, _, label in PRIORITY_TIERS]
    min_tier_rank = tier_order.index(DER_OPPORTUNITY_MIN_TIER)
    facilities["der_opportunity"] = facilities.apply(
        lambda row: (
            tier_order.index(row["priority_tier"]) >= min_tier_rank
            and row["nearby_solar_capacity_kw"] == 0
        ),
        axis=1,
    )
    return facilities


def main():
    facilities = load_facilities()
    facilities = add_grid_exposure(facilities)
    facilities = add_hazard_exposure(facilities)
    facilities = add_resilience_score(facilities)

    solar = load_solar_projects()
    facilities = add_clean_energy_proximity(facilities, solar)
    facilities = add_der_opportunity_flag(facilities)

    facilities["lon"] = facilities.geometry.x
    facilities["lat"] = facilities.geometry.y

    facilities = facilities.sort_values("resilience_score", ascending=False)
    facilities.to_file(OUTPUT_PATH, driver="GeoJSON")
    print(f"Scored {len(facilities)} facilities -> {OUTPUT_PATH}")

    solar.to_file(SOLAR_OUTPUT_PATH, driver="GeoJSON")
    print(f"Saved {len(solar)} solar projects -> {SOLAR_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
