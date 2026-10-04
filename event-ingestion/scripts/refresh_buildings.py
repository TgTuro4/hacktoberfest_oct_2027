"""Refresh the bundled UMD building list (names, codes, coordinates) from the community umd.io API."""

import json
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parents[1] / "src" / "umd_events" / "data" / "umd_buildings.json"

buildings = requests.get("https://api.umd.io/v1/map/buildings", timeout=30,
                         headers={"User-Agent": "UMDEventAggregator/1.0"}).json()
rows = [{"name": b["name"], "code": b.get("code") or None, "lat": round(b["lat"], 6), "lon": round(b["long"], 6)}
        for b in buildings if b.get("lat") and b.get("long")]
OUT.write_text(json.dumps(rows, indent=0, ensure_ascii=False), encoding="utf-8")
print(f"wrote {len(rows)} buildings to {OUT}")
