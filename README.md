# DC Critical Facility Energy Resilience Dashboard

Ranks Washington, DC's hospitals, fire/EMS stations, and homeless shelters
by how urgently they'd benefit from backup power (microgrid, battery
storage, generator) if the electric grid goes down — based on distance
to the nearest substation and exposure to FEMA flood hazard zones — and
cross-references that against existing solar deployment to flag facilities
that are both high-need and currently underserved by clean energy.

## Data sources (Open Data DC / DOEE, no API key needed)

- Hospitals
- Fire and EMS Station Locations
- Homeless Shelter Locations
- Electric Substations
- Floodplains from 2023 (FEMA)
- Solar for All — Community Renewable Energy Facility & single-family solar projects (DOEE)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the pipeline

```bash
python fetch_data.py   # downloads raw data into data/raw/
python process.py      # computes scores -> data/facilities_scored.geojson, data/solar_projects.geojson
streamlit run app.py   # launches the dashboard
```

## Dashboard

- **Resilience Map** — facilities colored by priority tier (Low/Moderate/High/Critical), auto-zooms to whatever's filtered
- **Clean Energy Landscape** — citywide solar capacity by ward, and a DER (distributed energy resource) siting opportunity table
- **Ranked List** — full sortable table with CSV export
- **Methodology & Data** — scoring formulas, data sources, and known limitations

## Methodology

Each facility gets a **Resilience Priority Score** (0-100, higher = more urgent), grouped into Low/Moderate/High/Critical tiers:

```
score = 0.4 * criticality + 0.3 * grid_exposure + 0.3 * hazard_exposure
```

- **Criticality** — fixed by facility type (Hospital 100, Fire/EMS 70, Shelter 50)
- **Grid exposure** — distance to nearest electric substation, normalized 0-100
- **Hazard exposure** — 100 if in a FEMA Special Flood Hazard Area, 50 if moderate risk, 0 otherwise

**DER Opportunity flag** — True when a facility is High/Critical priority *and* has zero
existing solar capacity within 0.5 miles (configurable) — a transparent proxy for
"underserved and urgent," not a substitute for a real site assessment.

Weights and thresholds live in `config.py` and are meant to be tuned/debated,
not treated as ground truth — the point is a transparent, explainable
starting point for prioritizing site assessments.

## Known limitations

- The electric substation layer is small (19 records) and was last updated in 2002 — a
  rough proxy for grid proximity, not real feeder/circuit data from the utility.
- Distance-based scoring doesn't account for actual feeder routing, redundancy, or
  documented backup power a facility may already have.
