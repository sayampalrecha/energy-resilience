"""DC Critical Facility Energy Resilience Dashboard.

Identifies which hospitals, fire/EMS stations, and shelters in Washington,
DC most need backup power (a microgrid, battery storage, or generator) if
the electric grid goes down, and cross-references that against where clean
energy (existing community/residential solar) is already deployed — to
flag facilities that are both high-need and currently underserved.

Run with:
    streamlit run app.py
"""
import math

import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st

from config import (
    OUTPUT_PATH,
    PRIORITY_TIERS,
    SEQUENTIAL_BLUE,
    SOLAR_OUTPUT_PATH,
    SOLAR_PROXIMITY_RADIUS_MILES,
    STATUS_COLORS,
)

st.set_page_config(page_title="DC Energy Resilience Dashboard", layout="wide")

TIER_ORDER = [label for _, _, label in PRIORITY_TIERS]

CUSTOM_CSS = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    [data-testid="stToolbar"] {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 2rem; max-width: 1200px;}

    .app-header {
        border-left: 6px solid #2a78d6;
        padding: 0.2rem 0 0.2rem 1.2rem;
        margin-bottom: 1.8rem;
    }
    .app-header h1 {margin-bottom: 0.3rem; font-size: 1.9rem;}
    .app-header p {color: #52514e; margin: 0.2rem 0; font-size: 1.02rem;}
    .app-byline {color: #898781; font-size: 0.82rem; margin-top: 0.5rem;}

    [data-testid="stMetric"] {
        background-color: #f4f6f8;
        border: 1px solid #e1e0d9;
        border-radius: 8px;
        padding: 1rem 1rem 0.7rem 1rem;
    }
    [data-testid="stMetricLabel"] {color: #52514e;}

    .section-note {color: #52514e; font-size: 0.95rem; margin-bottom: 1rem;}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

DC_CENTER = {"lat": 38.9072, "lon": -77.0369}
DC_ZOOM = 11


def fit_bounds(lats, lons, width_px=900, height_px=500, padding=1.15):
    """Center/zoom that fits all given points on screen, so the map
    auto-zooms to whatever facilities are currently filtered in."""
    if len(lats) == 0:
        return DC_CENTER, DC_ZOOM
    if len(lats) == 1:
        return {"lat": lats.iloc[0], "lon": lons.iloc[0]}, 15

    center = {"lat": (lats.min() + lats.max()) / 2, "lon": (lons.min() + lons.max()) / 2}

    def lat_rad(lat):
        s = math.sin(lat * math.pi / 180)
        return math.log((1 + s) / (1 - s)) / 2

    lat_fraction = (lat_rad(lats.max()) - lat_rad(lats.min())) / math.pi
    lon_fraction = (lons.max() - lons.min()) / 360

    lat_zoom = math.log2(height_px / 256 / lat_fraction) if lat_fraction > 0 else 15
    lon_zoom = math.log2(width_px / 256 / lon_fraction) if lon_fraction > 0 else 15

    zoom = min(lat_zoom, lon_zoom) - math.log2(padding)
    return center, max(0, min(zoom, 15))


@st.cache_data
def load_facilities():
    gdf = gpd.read_file(OUTPUT_PATH)
    return gdf.drop(columns="geometry")


@st.cache_data
def load_solar():
    gdf = gpd.read_file(SOLAR_OUTPUT_PATH)
    df = gdf.drop(columns="geometry")
    df["lon"] = gdf.geometry.x
    df["lat"] = gdf.geometry.y
    return df


def style_tier_column(df, column):
    def color_for(val):
        c = STATUS_COLORS.get(val, "#ffffff")
        return f"background-color: {c}; color: white; font-weight: 600;"
    return df.style.map(color_for, subset=[column])


data = load_facilities()
solar = load_solar()

# ---- Header ----
st.markdown(
    """
    <div class="app-header">
        <h1>DC Critical Facility Energy Resilience</h1>
        <p>Identifying which hospitals, fire/EMS stations, and shelters most need backup power —
        and where clean energy investment could close the gap.</p>
        <div class="app-byline">Open-data analysis · Washington, DC · Sources: Open Data DC, DOEE Solar for All (see Methodology & Data tab)</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---- Sidebar filters ----
st.sidebar.header("Filters")
facility_types = st.sidebar.multiselect(
    "Facility type",
    options=sorted(data["facility_type"].unique()),
    default=sorted(data["facility_type"].unique()),
)
tiers_selected = st.sidebar.multiselect(
    "Priority tier",
    options=TIER_ORDER,
    default=TIER_ORDER,
)

filtered = data[
    data["facility_type"].isin(facility_types) & data["priority_tier"].isin(tiers_selected)
]

tab_map, tab_clean, tab_list, tab_method = st.tabs(
    ["Resilience Map", "Clean Energy Landscape", "Ranked List", "Methodology & Data"]
)

# ==================== TAB 1: Resilience Map ====================
with tab_map:
    col1, col2, col3 = st.columns(3)
    col1.metric("Facilities assessed", len(filtered))
    col2.metric(
        "High + Critical priority",
        int(filtered["priority_tier"].isin(["High", "Critical"]).sum()),
    )
    col3.metric("Flagged DER opportunities", int(filtered["der_opportunity"].sum()))

    st.subheader("Where resilience investment is most needed")
    st.caption(
        "The map auto-zooms to whatever facilities are filtered in. Scroll or use the +/- controls to zoom further."
    )

    if len(filtered) == 0:
        st.info("No facilities match the current filters.")
    else:
        center, zoom = fit_bounds(filtered["lat"], filtered["lon"])
        fig = px.scatter_mapbox(
            filtered,
            lat="lat",
            lon="lon",
            color="priority_tier",
            category_orders={"priority_tier": TIER_ORDER},
            color_discrete_map=STATUS_COLORS,
            hover_name="name",
            hover_data={
                "facility_type": True,
                "resilience_score": True,
                "distance_to_substation_miles": True,
                "flood_risk_label": True,
                "lat": False,
                "lon": False,
                "priority_tier": False,
            },
            labels={"priority_tier": "Priority tier"},
        )
        fig.update_traces(marker={"size": 11})
        fig.update_layout(
            mapbox_style="carto-positron",
            mapbox_center=center,
            mapbox_zoom=zoom,
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
            height=520,
            legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "title": None},
        )
        st.plotly_chart(fig, width="stretch", config={"scrollZoom": True})

# ==================== TAB 2: Clean Energy Landscape ====================
with tab_clean:
    st.markdown(
        '<p class="section-note">Existing solar deployment in DC (DOEE Solar for All community and '
        'single-family projects), cross-referenced against facility need to identify where new clean '
        "energy investment would have the most impact.</p>",
        unsafe_allow_html=True,
    )

    total_capacity_mw = solar["capacity_kw"].sum() / 1000
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Existing solar capacity", f"{total_capacity_mw:.1f} MW")
    c2.metric("Solar projects citywide", len(solar))
    c3.metric("Households served", f"{int(solar['households_served'].sum()):,}")
    c4.metric("Flagged DER opportunities", int(data["der_opportunity"].sum()))

    st.subheader("Existing solar capacity by ward")
    ward_summary = (
        solar[solar["ward"] != "Other/Unspecified"]
        .groupby("ward")["capacity_kw"]
        .sum()
        .div(1000)
        .reset_index()
        .rename(columns={"capacity_kw": "capacity_mw"})
        .sort_values("capacity_mw", ascending=True)
    )
    bar_fig = px.bar(
        ward_summary,
        x="capacity_mw",
        y="ward",
        orientation="h",
        labels={"capacity_mw": "Installed solar capacity (MW)", "ward": ""},
    )
    bar_fig.update_traces(marker_color=SEQUENTIAL_BLUE)
    bar_fig.update_layout(height=350, margin={"r": 20, "t": 10, "l": 10, "b": 40})
    st.plotly_chart(bar_fig, width="stretch")

    st.subheader("DER siting opportunities")
    st.markdown(
        f'<p class="section-note">Facilities in the High or Critical priority tier with '
        f"no existing solar project within {SOLAR_PROXIMITY_RADIUS_MILES} miles — "
        "the strongest candidates for a new microgrid or solar-plus-storage installation.</p>",
        unsafe_allow_html=True,
    )
    der_candidates = data[data["der_opportunity"]].sort_values("resilience_score", ascending=False)
    if len(der_candidates) == 0:
        st.info("No facilities currently meet the DER opportunity criteria.")
    else:
        cols = {
            "name": "Facility",
            "facility_type": "Type",
            "ward": "Ward",
            "priority_tier": "Priority tier",
            "resilience_score": "Priority score",
            "distance_to_solar_miles": "Miles to nearest solar project",
        }
        der_table = der_candidates[list(cols.keys())].rename(columns=cols).reset_index(drop=True)
        st.dataframe(style_tier_column(der_table, "Priority tier"), width="stretch")

# ==================== TAB 3: Ranked List ====================
with tab_list:
    st.subheader("All facilities, highest priority first")
    display_cols = {
        "name": "Facility",
        "facility_type": "Type",
        "ward": "Ward",
        "priority_tier": "Priority tier",
        "resilience_score": "Priority score",
        "distance_to_substation_miles": "Miles to nearest substation",
        "flood_risk_label": "Flood risk",
        "nearby_solar_capacity_kw": "Nearby solar capacity (kW)",
    }
    table = filtered[list(display_cols.keys())].rename(columns=display_cols)
    table = table.sort_values("Priority score", ascending=False).reset_index(drop=True)
    st.dataframe(style_tier_column(table, "Priority tier"), width="stretch")
    st.download_button(
        "Download as CSV",
        table.to_csv(index=False).encode("utf-8"),
        file_name="dc_facility_resilience_scores.csv",
        mime="text/csv",
    )

# ==================== TAB 4: Methodology & Data ====================
with tab_method:
    st.subheader("Resilience Priority Score")
    st.markdown(
        """
        **Resilience Priority Score = 40% Criticality + 30% Grid Exposure + 30% Hazard Exposure**, grouped into
        four tiers (Low / Moderate / High / Critical) for readability.

        - **Criticality** — fixed by facility type: Hospital (100), Fire/EMS Station (70), Homeless Shelter (50)
        - **Grid Exposure** — distance to the nearest electric substation, scaled 0-100 (farther = higher score)
        - **Hazard Exposure** — 100 if the facility sits in a FEMA Special Flood Hazard Area,
          50 if in a moderate-risk (0.2% annual chance) zone, 0 otherwise

        All weights and thresholds are configurable in `config.py`.
        """
    )

    st.subheader("Clean Energy Landscape")
    st.markdown(
        f"""
        - **Nearby solar capacity** — total installed capacity (kW) from DOEE's Solar for All program
          within {SOLAR_PROXIMITY_RADIUS_MILES} miles of each facility
        - **DER Opportunity flag** — True when a facility is High or Critical priority *and* has zero
          existing solar capacity nearby — a simple, transparent proxy for "underserved and urgent,"
          not a substitute for a real site assessment
        """
    )

    st.subheader("Data sources")
    st.markdown(
        """
        All data is public and pulled live from Open Data DC and DOEE:
        - Hospitals, Fire and EMS Station Locations, Homeless Shelter Locations
        - Electric Substations
        - Floodplains from 2023 (FEMA)
        - Solar for All — Community Renewable Energy Facility & single-family solar projects (DOEE)
        """
    )

    st.subheader("Limitations")
    st.markdown(
        """
        - The electric substation layer is small (19 records) and was last updated in 2002 — it's a
          rough proxy for grid proximity, not real feeder or circuit data from the utility.
        - Distance-based scoring doesn't account for actual feeder routing, redundancy, or documented
          backup power a facility may already have.
        - This is a starting point for prioritizing site assessments, not a replacement for one.
        """
    )
