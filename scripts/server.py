#!/usr/bin/env python3
"""MAGI API — FastAPI backend with SSE streaming for the dashboard."""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse

# Import existing MAGI modules from same directory
import call_agent
import debate_canvas
import fetch_data

app = FastAPI(title="MAGI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCRIPT_DIR = Path(__file__).parent
CONFIG_PATH = os.environ.get("MAGI_CONFIG", str(SCRIPT_DIR.parent / "config.json"))

# Latest state (in-memory)
latest_state = {"data": None, "opinions": [], "verdict": None}


def load_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def resolve_host(cfg: dict) -> str:
    return os.environ.get("OLLAMA_HOST") or cfg.get("ollama_host", "http://localhost:11434")


def resolve_model(cfg: dict, agent_id: str) -> str:
    agent_models = cfg.get("agent_models", {})
    return (
        os.environ.get("OLLAMA_MODEL")
        or agent_models.get(agent_id)
        or cfg.get("ollama_model", "qwen3.5:9b")
    )


@app.get("/")
async def dashboard():
    return FileResponse(SCRIPT_DIR / "dashboard.html", media_type="text/html")


@app.get("/api/scan")
async def scan():
    cfg = load_config()
    domain = cfg.get("domain", "eco")
    ds = cfg.get("data_sources", {}).get(domain, {})
    cache_dir = ds.get("cache_dir", f"data/cache/{domain}")
    provided_dir = cfg.get("provided_data_dir", "data/provided")

    # Resolve paths relative to project root
    project_root = SCRIPT_DIR.parent
    abs_cache = str(project_root / cache_dir)
    abs_provided = str(project_root / provided_dir)

    data = None

    # Try API first (eco domain only)
    primary = ds.get("primary", "provided")
    if primary == "wildfire" and domain == "eco":
        try:
            wf_location = ds.get("wildfire_location", "los_angeles")
            data = await asyncio.to_thread(fetch_data.fetch_wildfire, wf_location)
        except Exception:
            pass
    elif primary == "open-meteo" and domain == "eco":
        try:
            data = await asyncio.to_thread(fetch_data.fetch_open_meteo)
        except Exception:
            pass

    # Fallback to provided data
    if not data:
        provided = await asyncio.to_thread(fetch_data.load_provided_data, abs_provided)
        if provided.get("metrics"):
            data = provided

    # Fallback to cache
    if not data:
        data = await asyncio.to_thread(fetch_data.load_cache, abs_cache)

    if not data:
        data = {
            "domain": domain,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "none",
            "metrics": [],
            "summary": "No data available from any source",
        }

    # Save to cache
    if data.get("source") != "none":
        await asyncio.to_thread(fetch_data.save_cache, data, abs_cache)

    latest_state["data"] = data
    return data


@app.post("/api/debate")
async def debate():
    async def event_generator():
        cfg = load_config()
        domain = cfg.get("domain", "eco")
        host = resolve_host(cfg)

        # Scan first if no data
        data = latest_state.get("data")
        if not data:
            data = await scan()

        yield {"event": "scan_result", "data": json.dumps(data, ensure_ascii=False)}

        # Build prompt — include wildfire-specific data when available
        extra_context = ""
        if data.get("sub_domain") == "wildfire":
            alerts = data.get("alerts", [])
            incidents = data.get("incidents", [])
            if alerts:
                extra_context += f"\nActive Fire-Weather Alerts:\n{json.dumps(alerts, indent=2)}\n"
            if incidents:
                extra_context += f"\nActive Wildfire Incidents:\n{json.dumps(incidents, indent=2)}\n"
            hotspots = data.get("hotspots_count", 0)
            if hotspots > 0:
                extra_context += f"\nSatellite Fire Hotspots Detected: {hotspots}\n"

        prompt = (
            f"Analyze the following {domain} data and provide your assessment.\n"
            f"Your goal is to help INDIVIDUALS understand how this environmental data "
            f"affects THEM PERSONALLY — their health, safety, property, and community.\n\n"
            f"Domain: {domain}\n"
            f"Location: {data.get('location', 'N/A')}\n"
            f"Timestamp: {data.get('timestamp', 'N/A')}\n"
            f"Source: {data.get('source', 'N/A')}\n\n"
            f"Metrics:\n{json.dumps(data.get('metrics', []), indent=2)}\n\n"
            f"Summary: {data.get('summary', 'N/A')}\n"
            f"{extra_context}\n"
            f"Respond as JSON with: agent, perspective, "
            f"opinion (max 200 words, written for a non-expert resident), "
            f"confidence (0-1), severity (0-1, how dangerous is this data), "
            f"recommendation, personal_actions (2-3 concrete steps for individuals), "
            f"key_points (3 items)."
        )

        opinions = []
        for agent_id in ["melchior", "balthasar", "casper"]:
            model = resolve_model(cfg, agent_id)
            persona = call_agent.AGENT_PERSONAS[agent_id]

            yield {
                "event": "agent_start",
                "data": json.dumps({"agent": agent_id, "model": model}),
            }

            t0 = time.monotonic()
            try:
                raw = await asyncio.to_thread(
                    call_agent.call_ollama, host, model, persona["system"], prompt
                )
                result = call_agent.parse_agent_response(raw, agent_id)
            except Exception as e:
                result = {
                    "agent": agent_id,
                    "perspective": persona["perspective"],
                    "opinion": f"Agent failed: {e}",
                    "confidence": 0.0,
                    "recommendation": "Manual review required",
                    "key_points": ["Agent inference failed"],
                }
            elapsed = round(time.monotonic() - t0, 1)

            opinions.append(result)
            yield {
                "event": "agent_result",
                "data": json.dumps(
                    {"agent": agent_id, "result": result, "elapsed": elapsed},
                    ensure_ascii=False,
                ),
            }

        # Determine verdict
        verdict = debate_canvas.determine_pattern(opinions, domain)
        yield {"event": "verdict", "data": json.dumps(verdict, ensure_ascii=False)}

        # Save debate record
        project_root = SCRIPT_DIR.parent
        memory_dir = project_root / "memory" / "debates"
        memory_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        debate_id = f"debate_{ts}"
        with open(memory_dir / f"{debate_id}.json", "w") as f:
            json.dump(
                {"data": data, "opinions": opinions, "verdict": verdict, "timestamp": ts},
                f,
                ensure_ascii=False,
                indent=2,
            )

        # Update state
        latest_state.update({"data": data, "opinions": opinions, "verdict": verdict})

        yield {
            "event": "debate_end",
            "data": json.dumps({"timestamp": ts, "debate_id": debate_id}),
        }

    return EventSourceResponse(event_generator())


@app.get("/api/status")
async def status():
    return latest_state
