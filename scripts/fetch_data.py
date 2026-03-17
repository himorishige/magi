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


# --- Wildfire Data Sources ---

# California fire-prone regions for scanning
WILDFIRE_LOCATIONS = {
    "los_angeles": {"lat": 34.05, "lon": -118.25, "label": "Los Angeles, CA"},
    "san_diego": {"lat": 32.72, "lon": -117.16, "label": "San Diego, CA"},
    "sacramento": {"lat": 38.58, "lon": -121.49, "label": "Sacramento, CA"},
    "san_francisco": {"lat": 37.77, "lon": -122.42, "label": "San Francisco, CA"},
}


def fetch_wildfire_weather(lat: float = 34.05, lon: float = -118.25) -> dict:
    """Fetch fire-weather metrics from Open-Meteo Weather API (free, no key)."""
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=relative_humidity_2m,wind_speed_10m,wind_direction_10m,"
        f"wind_gusts_10m,temperature_2m"
        f"&hourly=vapour_pressure_deficit,soil_moisture_0_to_7cm"
        f"&forecast_hours=1&wind_speed_unit=mph"
        f"&timezone=America%2FLos_Angeles"
    )
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())

    current = data.get("current", {})
    hourly = data.get("hourly", {})

    humidity = current.get("relative_humidity_2m", 50)
    wind_speed = current.get("wind_speed_10m", 0)
    wind_gusts = current.get("wind_gusts_10m", 0)
    wind_dir = current.get("wind_direction_10m", 0)
    temp = current.get("temperature_2m", 20)
    vpd_list = hourly.get("vapour_pressure_deficit") or [0]
    vpd = vpd_list[0] if vpd_list[0] is not None else 0
    soil_list = hourly.get("soil_moisture_0_to_7cm") or [0.3]
    soil_moisture = soil_list[0] if soil_list[0] is not None else 0.3

    return {
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_gusts": wind_gusts,
        "wind_direction": wind_dir,
        "temperature": temp,
        "vpd": vpd,
        "soil_moisture": soil_moisture,
    }


def fetch_noaa_alerts(state: str = "CA") -> list:
    """Fetch active fire-weather alerts from NOAA NWS API (free, no key)."""
    url = f"https://api.weather.gov/alerts/active?area={state}"
    req = urllib.request.Request(url, headers={"User-Agent": "MAGI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return []

    fire_events = {"Red Flag Warning", "Fire Weather Watch", "Extreme Fire Danger"}
    alerts = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        event = props.get("event", "")
        if event in fire_events:
            alerts.append({
                "event": event,
                "headline": props.get("headline", ""),
                "area": props.get("areaDesc", ""),
                "severity": props.get("severity", "Unknown"),
                "onset": props.get("onset", ""),
                "expires": props.get("expires", ""),
            })
    return alerts


def fetch_calfire_incidents() -> list:
    """Fetch active wildfire incidents from CAL FIRE GeoJSON API (free, no key)."""
    url = "https://www.fire.ca.gov/umbraco/api/IncidentApi/GeoJsonList?inactive=false"
    req = urllib.request.Request(url, headers={"User-Agent": "MAGI/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return []

    incidents = []
    for feature in data.get("features", []):
        props = feature.get("properties", {})
        if props.get("IsActive"):
            incidents.append({
                "name": props.get("Name", "Unknown"),
                "acres": props.get("AcresBurned", 0),
                "contained": props.get("PercentContained", 0),
                "latitude": props.get("Latitude", 0),
                "longitude": props.get("Longitude", 0),
                "started": props.get("Started", ""),
                "county": props.get("County", ""),
            })
    return incidents


def fetch_nasa_firms(lat: float = 34.05, lon: float = -118.25, radius_deg: float = 5.0) -> list:
    """Fetch satellite fire hotspots from NASA FIRMS (requires NASA_FIRMS_KEY env var)."""
    api_key = os.environ.get("NASA_FIRMS_KEY", "")
    if not api_key:
        return []

    west = lon - radius_deg
    east = lon + radius_deg
    south = lat - radius_deg
    north = lat + radius_deg
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/VIIRS_NOAA20_NRT/{west},{south},{east},{north}/1"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            import csv
            import io
            text = resp.read().decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            hotspots = []
            for row in reader:
                try:
                    hotspots.append({
                        "latitude": float(row.get("latitude", 0)),
                        "longitude": float(row.get("longitude", 0)),
                        "brightness": float(row.get("bright_ti4", 0)),
                        "confidence": row.get("confidence", ""),
                        "frp": float(row.get("frp", 0)),
                        "acq_date": row.get("acq_date", ""),
                    })
                except (ValueError, TypeError):
                    continue
            return hotspots
    except Exception:
        return []


def assess_fire_risk(weather: dict, alerts: list, incidents: list, hotspots: list) -> str:
    """Compute composite fire-risk severity from all data sources."""
    score = 0

    # Weather factors
    humidity = weather.get("humidity", 50)
    wind_speed = weather.get("wind_speed", 0)
    vpd = weather.get("vpd", 0)
    if humidity < 15:
        score += 3
    elif humidity < 25:
        score += 2
    elif humidity < 35:
        score += 1

    if wind_speed > 40:
        score += 3
    elif wind_speed > 25:
        score += 2
    elif wind_speed > 15:
        score += 1

    if vpd > 3.0:
        score += 2
    elif vpd > 2.0:
        score += 1

    # Active alerts
    for alert in alerts:
        if alert.get("event") == "Red Flag Warning":
            score += 3
        elif alert.get("event") == "Fire Weather Watch":
            score += 2

    # Active incidents
    for inc in incidents:
        acres = inc.get("acres", 0)
        if acres > 10000:
            score += 3
        elif acres > 1000:
            score += 2
        elif acres > 0:
            score += 1

    # Satellite hotspots
    if len(hotspots) > 50:
        score += 3
    elif len(hotspots) > 10:
        score += 2
    elif len(hotspots) > 0:
        score += 1

    if score >= 10:
        return "critical"
    elif score >= 7:
        return "high"
    elif score >= 4:
        return "medium"
    elif score >= 2:
        return "low"
    return "minimal"


def fetch_wildfire(location: str = "los_angeles") -> dict:
    """Composite wildfire data fetch — combines weather, alerts, incidents, and hotspots."""
    loc = WILDFIRE_LOCATIONS.get(location, WILDFIRE_LOCATIONS["los_angeles"])
    lat, lon, label = loc["lat"], loc["lon"], loc["label"]
    now = datetime.now(timezone.utc)

    # Fetch all sources (weather is required, others are best-effort)
    weather = fetch_wildfire_weather(lat, lon)
    alerts = fetch_noaa_alerts("CA")
    incidents = fetch_calfire_incidents()
    hotspots = fetch_nasa_firms(lat, lon)

    severity = assess_fire_risk(weather, alerts, incidents, hotspots)

    # Build metrics
    humidity = weather["humidity"]
    wind_speed = weather["wind_speed"]
    wind_gusts = weather["wind_gusts"]
    vpd = weather["vpd"]
    soil = weather["soil_moisture"]
    temp = weather["temperature"]
    wind_dir = weather["wind_direction"]

    h_sev = "critical" if humidity < 15 else "high" if humidity < 25 else "medium" if humidity < 35 else "low"
    w_sev = "critical" if wind_speed > 40 else "high" if wind_speed > 25 else "medium" if wind_speed > 15 else "low"

    metrics = [
        {"name": "fire_risk", "value": severity, "unit": "composite", "severity": severity},
        {"name": "humidity", "value": humidity, "unit": "%", "severity": h_sev},
        {"name": "wind_speed", "value": wind_speed, "unit": "mph", "severity": w_sev},
        {"name": "wind_gusts", "value": wind_gusts, "unit": "mph", "severity": "info"},
        {"name": "wind_direction", "value": wind_dir, "unit": "°", "severity": "info"},
        {"name": "temperature", "value": temp, "unit": "°C", "severity": "info"},
        {"name": "vpd", "value": round(vpd, 2), "unit": "kPa", "severity": "high" if vpd > 2.0 else "info"},
        {"name": "soil_moisture", "value": round(soil, 3), "unit": "m³/m³", "severity": "high" if soil < 0.1 else "info"},
    ]

    # Alert summary
    alert_names = [a["event"] for a in alerts[:3]]
    alert_str = ", ".join(alert_names) if alert_names else "None"

    # Incident summary
    active_fires = len(incidents)
    total_acres = sum(i.get("acres", 0) for i in incidents)

    # Hotspot summary
    hotspot_count = len(hotspots)

    summary_parts = [
        f"Fire Risk: {severity.upper()}",
        f"Humidity: {humidity}%",
        f"Wind: {wind_speed} mph (gusts {wind_gusts} mph)",
        f"VPD: {vpd:.1f} kPa",
        f"Alerts: {alert_str}",
        f"Active fires: {active_fires} ({total_acres:,} acres)",
    ]
    if hotspot_count > 0:
        summary_parts.append(f"Satellite hotspots: {hotspot_count}")

    return {
        "domain": "eco",
        "sub_domain": "wildfire",
        "timestamp": now.isoformat(),
        "source": "wildfire-composite",
        "location": f"{label} ({lat},{lon})",
        "metrics": metrics,
        "alerts": alerts[:5],
        "incidents": incidents[:10],
        "hotspots_count": hotspot_count,
        "hotspots": hotspots[:50],
        "center": {"lat": lat, "lon": lon},
        "summary": ". ".join(summary_parts),
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
        if primary == "wildfire" and domain == "eco":
            try:
                wf_location = ds.get("wildfire_location", "los_angeles")
                data = fetch_wildfire(wf_location)
            except Exception as e:
                sys.stderr.write(f"Wildfire fetch failed: {e}\n")
        elif primary == "open-meteo" and domain == "eco":
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
