#!/usr/bin/env python3
"""Fetch data for MAGI system. Supports APIs, local files, and cache fallback."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import urllib.request
    import urllib.error
except ImportError:
    pass


def fetch_open_meteo(lat: float = 37.3382, lon: float = -121.8863) -> dict:
    """Fetch air quality data from Open-Meteo (free, no key)."""
    url = (
        f"https://air-quality-api.open-meteo.com/v1/air-quality"
        f"?latitude={lat}&longitude={lon}"
        f"&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,ozone,european_aqi"
    )
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    current = data.get("current", {})
    aqi = current.get("european_aqi", 0)
    severity = "low"
    if aqi > 200:
        severity = "critical"
    elif aqi > 100:
        severity = "high"
    elif aqi > 50:
        severity = "medium"

    return {
        "domain": "eco",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "open-meteo",
        "location": f"{lat},{lon}",
        "metrics": [
            {"name": "aqi", "value": aqi, "unit": "European AQI", "severity": severity},
            {"name": "pm2_5", "value": current.get("pm2_5", 0), "unit": "μg/m³", "severity": "info"},
            {"name": "pm10", "value": current.get("pm10", 0), "unit": "μg/m³", "severity": "info"},
            {"name": "co", "value": current.get("carbon_monoxide", 0), "unit": "μg/m³", "severity": "info"},
            {"name": "no2", "value": current.get("nitrogen_dioxide", 0), "unit": "μg/m³", "severity": "info"},
            {"name": "o3", "value": current.get("ozone", 0), "unit": "μg/m³", "severity": "info"},
        ],
        "summary": f"Air Quality Index: {aqi} ({severity}). PM2.5: {current.get('pm2_5', 'N/A')} μg/m³",
    }


def load_provided_data(provided_dir: str) -> dict:
    """Load data from provided files (CSV, JSON)."""
    p = Path(provided_dir)
    if not p.exists():
        return {"domain": "unknown", "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "none", "metrics": [], "summary": "No provided data found"}

    for f in sorted(p.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix == ".json":
            with open(f) as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "metrics" in data:
                return data
            return {
                "domain": "provided",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": f.name,
                "metrics": [{"name": "raw_data", "value": data, "unit": "raw", "severity": "info"}],
                "summary": f"Loaded from {f.name}",
            }
        elif f.suffix == ".csv":
            import csv
            with open(f) as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
            return {
                "domain": "provided",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": f.name,
                "metrics": [{"name": "records", "value": len(rows), "unit": "rows", "severity": "info"}],
                "summary": f"Loaded {len(rows)} records from {f.name}",
                "raw_rows": rows[:50],
            }

    return {"domain": "unknown", "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "none", "metrics": [], "summary": "No supported files found"}


def load_cache(cache_dir: str) -> dict:
    """Load most recent cached data."""
    p = Path(cache_dir)
    if not p.exists():
        return None
    files = sorted(p.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    if files:
        with open(files[0]) as f:
            return json.load(f)
    return None


def save_cache(data: dict, cache_dir: str):
    """Save data to cache."""
    p = Path(cache_dir)
    p.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    with open(p / f"{ts}.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Also save as latest.json for easy access
    with open(p / "latest.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Fetch data for MAGI")
    parser.add_argument("--config", default="/app/config.json")
    parser.add_argument("--domain", default=None, help="Override domain (eco/human/culture/auto)")
    parser.add_argument("--cache-only", action="store_true", help="Only use cached data")
    parser.add_argument("--file", default=None, help="Load from specific file")
    args = parser.parse_args()

    # Load config
    cfg = {}
    if os.path.exists(args.config):
        with open(args.config) as f:
            cfg = json.load(f)

    domain = args.domain or cfg.get("domain", "eco")
    ds = cfg.get("data_sources", {}).get(domain, {})
    cache_dir = ds.get("cache_dir", f"data/cache/{domain}")
    provided_dir = cfg.get("provided_data_dir", "data/provided")

    # Priority: explicit file > API > provided data > cache
    data = None

    if args.file:
        if os.path.exists(args.file):
            data = load_provided_data(os.path.dirname(args.file))
        else:
            print(json.dumps({"error": f"File not found: {args.file}"}), file=sys.stderr)
            sys.exit(1)
    elif args.cache_only:
        data = load_cache(cache_dir)
        if not data:
            print(json.dumps({"error": "No cached data available"}), file=sys.stderr)
            sys.exit(1)
    else:
        # Try API first
        primary = ds.get("primary", "provided")
        if primary == "open-meteo" and domain == "eco":
            try:
                data = fetch_open_meteo()
            except Exception as e:
                sys.stderr.write(f"API fetch failed: {e}\n")

        # Fallback to provided data
        if not data:
            provided = load_provided_data(provided_dir)
            if provided.get("metrics"):
                data = provided

        # Fallback to cache
        if not data:
            data = load_cache(cache_dir)

        if not data:
            data = {
                "domain": domain,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "none",
                "metrics": [],
                "summary": "No data available from any source",
            }

    # Save to cache
    if data and data.get("source") != "none":
        save_cache(data, cache_dir)

    # Output to stdout
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
