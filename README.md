# MAGI — Multi-Agent Governance Intelligence

Three AI agents analyze environmental threats from different perspectives, then a coordinator synthesizes their advice into a unified action plan for residents.

Built for **GTC 2026 Hack for Impact** (Eco Impact track).

## What It Does

MAGI turns raw environmental data into personalized advice. Instead of "humidity 16%, VPD 5.2 kPa", MAGI says "close your windows tonight and check on your elderly neighbor who lives alone."

## Agents

| Agent | Role | Model |
|-------|------|-------|
| **MELCHIOR** | Health & Safety (the ER doctor neighbor) | Qwen 3.5 9B |
| **BALTHASAR** | Money & Livelihood (the financial advisor neighbor) | NVIDIA Nemotron 9B |
| **CASPER** | Community & Neighbors (the social worker neighbor) | Google Gemma 3 12B |
| **Coordinator** | Unified synthesis | NVIDIA Nemotron-3-Nano 24B |

All agents write in plain language a middle schooler can understand.

## Data Sources (All Free, Real-Time)

| Source | Data |
|--------|------|
| Open-Meteo | Humidity, wind, temperature, VPD |
| NOAA NWS | Red Flag Warnings, Fire Weather Watch |
| CAL FIRE | Active wildfire locations & acreage |
| NASA FIRMS | Satellite fire hotspots (VIIRS) |
| NVIDIA Nemotron-Personas-USA | 1M synthetic resident profiles |

## Features

- **Streaming debate**: Watch agents reason in real-time via SSE
- **Interactive map**: Leaflet + OpenStreetMap with live fire markers (FRP-based color filtering)
- **Persona-grounded**: Analysis references real resident profiles (age, occupation, cultural background)
- **Risk score**: 0-100 averaged from agent severity assessments
- **Coordinator synthesis**: Unified action priorities from all perspectives
- **Cosmos video**: NVIDIA Cosmos Predict2.5-2B wildfire simulation

## Quick Start

```bash
# 1. Install Ollama and pull models
ollama pull qwen3.5:9b
ollama pull gemma3:12b
# nemotron-9b-n6-nothink: custom model (see docs)
# nemotron-3-nano: ollama pull nemotron-3-nano

# 2. Install Python dependencies
cd scripts
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# 3. Set API keys (optional)
export NASA_FIRMS_KEY=your_key  # for satellite hotspots

# 4. Start dashboard
uvicorn server:app --host 0.0.0.0 --port 8000
# Open http://localhost:8000
```

## Architecture

```
Live Data APIs              MAGI Engine (GB10)            Dashboard
┌────────────────┐    ┌─────────────────────────────┐    ┌─────────────┐
│ Open-Meteo     │───>│ 1. SCAN: Fetch + Score      │───>│ Leaflet Map │
│ NOAA NWS       │    │ 2. DEBATE: 3 Agents (SSE)   │    │ Risk Score  │
│ CAL FIRE       │    │ 3. VERDICT: Risk 0-100      │    │ Live Stream │
│ NASA FIRMS     │    │ 4. COORDINATE: Unified Plan │    │ Action Plan │
│ Personas-USA   │    │ 5. VISUALIZE: Cosmos Video  │    │ Video       │
└────────────────┘    └─────────────────────────────┘    └─────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Hardware | NVIDIA GB10 (128 GB unified memory) |
| Inference | Ollama — 4 models, GPU-accelerated |
| Backend | FastAPI + SSE streaming |
| Frontend | Leaflet + OpenStreetMap |
| Personas | NVIDIA Nemotron-Personas-USA |
| World Model | NVIDIA Cosmos Predict2.5-2B |
| Data | 4 free public APIs (real-time) |

## License

MIT
