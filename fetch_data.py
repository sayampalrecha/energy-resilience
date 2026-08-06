"""Downloads the raw datasets from Open Data DC into data/raw/.

Run this once (or whenever you want fresh data):
    python fetch_data.py
"""
import os

import requests

from config import DATA_SOURCES, RAW_DIR


def fetch_all():
    os.makedirs(RAW_DIR, exist_ok=True)
    for name, url in DATA_SOURCES.items():
        dest = os.path.join(RAW_DIR, f"{name}.geojson")
        print(f"Downloading {name} -> {dest}")
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        with open(dest, "wb") as f:
            f.write(response.content)
    print("Done. All raw files saved to", RAW_DIR)


if __name__ == "__main__":
    fetch_all()
