#!/usr/bin/env python3
"""MAGI API — FastAPI backend with SSE streaming for the dashboard."""

import asyncio
import json
import os
import random
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


@app.get("/api/videos/{filename}")
async def serve_video(filename: str):
    """Serve Cosmos-generated videos."""
    video_dir = SCRIPT_DIR.parent / "data" / "videos"
    video_path = video_dir / filename
    if video_path.exists() and video_path.suffix in (".mp4", ".webm"):
        return FileResponse(video_path, media_type="video/mp4")
    return {"error": "Video not found"}


@app.get("/api/videos")
async def list_videos():
    """List available Cosmos-generated videos."""
    video_dir = SCRIPT_DIR.parent / "data" / "videos"
    if not video_dir.exists():
        return {"videos": []}
    videos = [f.name for f in video_dir.iterdir() if f.suffix in (".mp4", ".webm")]
    return {"videos": videos}


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
            hotspots = data.get("hotspots", [])
            hotspots_count = data.get("hotspots_count", len(hotspots))
            if hotspots_count > 0:
                # Filter: only include high-FRP hotspots (likely real fires)
                fire_hotspots = [h for h in hotspots if h.get("frp", 0) >= 5]
                industrial_count = hotspots_count - len(fire_hotspots)
                extra_context += (
                    f"\nSatellite Thermal Anomalies: {hotspots_count} total "
                    f"({len(fire_hotspots)} high-FRP likely fires, "
                    f"{industrial_count} low-FRP likely industrial heat sources — "
                    f"do NOT count industrial heat as wildfire risk)\n"
                )
                # Only send likely-fire hotspots to LLM
                top = sorted(fire_hotspots, key=lambda h: h.get("frp", 0), reverse=True)[:10]
                if top:
                    extra_context += "Significant hotspots (FRP >= 5 MW, likely fires):\n"
                    for h in top:
                        extra_context += (
                            f"  - lat:{h['latitude']}, lon:{h['longitude']}, "
                            f"FRP:{h.get('frp','N/A')}MW, "
                            f"confidence:{h.get('confidence','N/A')}, "
                            f"date:{h.get('acq_date','N/A')}\n"
                        )

        # Load persona data for personalized analysis
        persona_context = ""
        personas_path = SCRIPT_DIR.parent / "data" / "personas_la.json"
        if personas_path.exists():
            with open(personas_path) as pf:
                all_personas = json.load(pf)
            if all_personas:
                sample = random.sample(all_personas, min(4, len(all_personas)))
                persona_context = "\n\nREAL RESIDENT PROFILES (from NVIDIA Nemotron-Personas-USA dataset):\n"
                persona_context += "Consider how this situation affects each of these real people:\n"
                for i, p in enumerate(sample, 1):
                    persona_context += (
                        f"\nResident {i}: {p.get('city','')}, age {p.get('age','')}, "
                        f"{p.get('sex','')}, {p.get('occupation','').replace('_',' ')}, "
                        f"education: {p.get('education','').replace('_',' ')}. "
                        f"{p.get('cultural_background','')[:150]}\n"
                    )
                persona_context += (
                    "\nReference these specific residents in your analysis. "
                    "Explain how the environmental conditions affect THEM specifically "
                    "based on their age, occupation, and circumstances.\n"
                )

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
            f"{extra_context}"
            f"{persona_context}\n"
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
                # Use streaming to send tokens in real-time
                import queue
                import threading

                token_queue = queue.Queue()

                def stream_worker():
                    try:
                        for token, _ in call_agent.call_ollama_stream(
                            host, model, persona["system"], prompt
                        ):
                            token_queue.put(("token", token))
                        token_queue.put(("done", None))
                    except Exception as e:
                        token_queue.put(("error", str(e)))

                thread = threading.Thread(target=stream_worker, daemon=True)
                thread.start()

                full_text = ""
                while True:
                    try:
                        msg_type, msg_data = await asyncio.to_thread(
                            token_queue.get, True, 120
                        )
                    except Exception:
                        break

                    if msg_type == "token":
                        full_text += msg_data
                        yield {
                            "event": "agent_chunk",
                            "data": json.dumps(
                                {"agent": agent_id, "token": msg_data},
                                ensure_ascii=False,
                            ),
                        }
                    elif msg_type == "done":
                        break
                    elif msg_type == "error":
                        full_text = f"Agent failed: {msg_data}"
                        break

                thread.join(timeout=5)
                result = call_agent.parse_agent_response(full_text, agent_id)
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

        # Moderator synthesis — unified verdict from 3 perspectives
        yield {
            "event": "moderator_start",
            "data": json.dumps({"model": resolve_model(cfg, "moderator")}),
        }

        mod_prompt = (
            "Here are the three MAGI agent analyses:\n\n"
            + "\n\n".join(
                f"**{r.get('agent', '').upper()}** ({r.get('perspective', '')}):\n"
                f"Opinion: {r.get('opinion', 'N/A')}\n"
                f"Severity: {r.get('severity', 'N/A')}\n"
                f"Key actions: {r.get('personal_actions', [])}"
                for r in opinions
            )
            + f"\n\nOverall pattern: {verdict.get('pattern', 'N/A')} ({verdict.get('level', 'N/A')})\n"
            + "Synthesize these into a unified assessment for residents."
        )

        try:
            mod_full = ""
            for token, _ in call_agent.call_ollama_stream(
                host, resolve_model(cfg, "moderator"),
                call_agent.MODERATOR_SYSTEM, mod_prompt
            ):
                mod_full += token
                yield {
                    "event": "moderator_chunk",
                    "data": json.dumps({"token": token}, ensure_ascii=False),
                }

            mod_result = call_agent.parse_agent_response(mod_full, "moderator")
            yield {
                "event": "moderator_result",
                "data": json.dumps(mod_result, ensure_ascii=False),
            }
        except Exception as e:
            yield {
                "event": "moderator_result",
                "data": json.dumps({"error": str(e)}, ensure_ascii=False),
            }

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
