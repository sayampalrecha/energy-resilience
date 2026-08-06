"""Settings for the DC Critical Facility Energy Resilience project.

Everything a reviewer would want to question — data sources and scoring
weights — lives here instead of being buried in the pipeline code.
"""

# Open Data DC / DOEE download endpoints (public, no API key required).
DATA_SOURCES = {
    "hospitals": "https://opendata.dc.gov/api/download/v1/items/6c18bb76d8644bc1bf53cac2d2199564/geojson?layers=4",
    "fire_ems_stations": "https://opendata.dc.gov/api/download/v1/items/05d048a0aa4845c6a0912f3a9f216992/geojson?layers=6",
    "homeless_shelters": "https://opendata.dc.gov/api/download/v1/items/87c5e68942304363a4578b30853f385d/geojson?layers=25",
    "electric_substations": "https://opendata.dc.gov/api/download/v1/items/b1db18de82434dcda9f96ea49d079e6a/geojson?layers=25",
    "floodplains": "https://opendata.dc.gov/api/download/v1/items/2e43cc87ea004602af8481175ffe9a37/geojson?layers=1",
    # DOEE Solar for All — Community Renewable Energy Facility & single-family
    # solar projects already built in DC (capacity, households served, ward).
    "solar_projects": "https://services.arcgis.com/neT9SoYxizqTHZPH/arcgis/rest/services/Locations_of_CREF_Projects/FeatureServer/0/query?where=1=1&outFields=*&f=geojson",
}

RAW_DIR = "data/raw"
OUTPUT_PATH = "data/facilities_scored.geojson"
SOLAR_OUTPUT_PATH = "data/solar_projects.geojson"

# How close an existing solar project has to be to a facility to "count"
# as nearby clean energy infrastructure, in miles.
SOLAR_PROXIMITY_RADIUS_MILES = 0.5

# A facility is flagged as a DER (distributed energy resource) siting
# opportunity if it needs backup power (High/Critical tier) and has zero
# existing solar capacity within the radius above.
DER_OPPORTUNITY_MIN_TIER = "High"

# Fixed criticality score by facility type (0-100).
# Reasoning: a hospital losing power endangers patients on life support;
# a fire/EMS station losing power delays emergency response; a shelter
# losing power is serious but has more evacuation flexibility.
CRITICALITY_WEIGHTS = {
    "Hospital": 100,
    "Fire/EMS Station": 70,
    "Homeless Shelter": 50,
}

# How much each factor contributes to the final Resilience Priority Score.
# Must sum to 1.0.
SCORE_WEIGHTS = {
    "criticality": 0.4,
    "grid_exposure": 0.3,
    "hazard_exposure": 0.3,
}

# Projected coordinate system used for distance calculations (feet).
# EPSG:2248 = NAD83 / Maryland State Plane, which covers DC.
DISTANCE_CRS = "EPSG:2248"

# Resilience Priority Score (0-100) grouped into tiers for the map and
# tables, so the dashboard reads as "these facilities need attention" rather
# than a raw number. (min, max, label) — max is inclusive.
PRIORITY_TIERS = [
    (0, 39, "Low"),
    (40, 59, "Moderate"),
    (60, 79, "High"),
    (80, 100, "Critical"),
]

# Status colors (fixed — not decorative), used consistently across the map,
# charts, and tier badges.
STATUS_COLORS = {
    "Low": "#0ca30c",
    "Moderate": "#fab219",
    "High": "#ec835a",
    "Critical": "#d03b3b",
}

# Single-hue sequential blue, used for magnitude charts (e.g. solar capacity
# by ward) that aren't tied to a priority tier.
SEQUENTIAL_BLUE = "#2a78d6"
