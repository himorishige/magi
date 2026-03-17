---
marp: true
theme: uncover
paginate: true
backgroundColor: "#0a0a0a"
color: "#e0e0e0"
style: |
  section {
    font-family: 'Helvetica Neue', Arial, sans-serif;
  }
  h1 {
    color: #00ff88;
  }
  h2 {
    color: #88ccff;
  }
  strong {
    color: #ffaa00;
  }
  em {
    color: #aaaaaa;
  }
  table {
    font-size: 0.7em;
  }
  blockquote {
    border-left: 4px solid #00ff88;
    padding-left: 1em;
    color: #cccccc;
    font-style: italic;
  }
  code {
    color: #00ff88;
    background: #1a1a1a;
  }
---

# MAGI

## Multi-Agent Governance Intelligence

*Three Wise Models. One Informed Decision.*

GTC 2026 — Hack for Impact

---

## The Problem

Wildfire data exists — satellites, weather stations, government alerts.

But for a family in LA, **numbers don't trigger action**.

- "Humidity 16%, VPD 5.2 kPa" → *So what?*
- "69 satellite hotspots detected" → *Should I worry?*

> Data is abundant. **Personal awareness is scarce.**

---

## Our Answer: Make It Personal

MAGI turns environmental data into advice **you'd give your neighbor**.

Three AI agents analyze the same threat from **three angles**:

| Agent | Role | Question |
|-------|------|----------|
| **MELCHIOR** | Your neighbor the ER doctor | "What does this mean for your body?" |
| **BALTHASAR** | Your neighbor the financial advisor | "What does this cost your family?" |
| **CASPER** | Your neighbor the community organizer | "Who on your block needs help?" |

A **Coordinator** synthesizes their advice into one clear action plan.

---

## Why 4 Models, Not 1?

Three 9B models + one 24B coordinator fit in **~45 GB**.
A single desktop GPU can run this. **No cloud needed.**

| Role | Model | Family | Size |
|------|-------|--------|------|
| MELCHIOR | Qwen 3.5 9B | Alibaba | 6.6 GB |
| BALTHASAR | Nemotron 9B | **NVIDIA** | 6.2 GB |
| CASPER | Gemma 3 12B | Google | 8.1 GB |
| Coordinator | Nemotron-3-Nano 24B | **NVIDIA** | 24 GB |

*Different training data. Different blind spots. **Better decisions.***

---

## Real Resident Profiles

MAGI uses **NVIDIA Nemotron-Personas-USA** (1M synthetic profiles)
to ground its analysis in real people.

Each analysis references **4 randomly sampled local residents**:

- *"Maria, 30, elementary school teacher in LA — walks to school"*
- *"Thomas, 10, Long Beach — has childhood asthma"*
- *"James, 68, Pasadena — lives alone, no car"*

The agents don't speak in abstractions.
They speak about **people you'd recognize on your street**.

---

## Data Sources — All Free, All Real-Time

| Source | Data | API Key |
|--------|------|---------|
| Open-Meteo Weather | Humidity, wind, temperature, VPD | Free |
| NOAA NWS Alerts | Red Flag Warnings, Fire Weather Watch | Free |
| CAL FIRE Incidents | Active wildfire locations & acreage | Free |
| NASA FIRMS | Satellite fire hotspots (VIIRS) | Free |
| **NVIDIA Nemotron-Personas-USA** | 1M resident profiles | CC-BY-4.0 |

All data is fetched live at scan time. No pre-cached results.

---

## Architecture

```
  Live Data APIs              MAGI Engine (GB10)            Dashboard
┌────────────────┐    ┌─────────────────────────────┐    ┌─────────────┐
│ Open-Meteo     │───▶│ 1. SCAN: Fetch + Score      │───▶│ Leaflet Map │
│ NOAA NWS       │    │ 2. DEBATE: 3 Agents (SSE)   │    │ Risk Score  │
│ CAL FIRE       │    │ 3. VERDICT: Risk 0-100      │    │ Live Stream │
│ NASA FIRMS     │    │ 4. COORDINATE: Unified Plan │    │ Action Plan │
│ Personas-USA   │    │ 5. VISUALIZE: Cosmos Video  │    │ Cosmos Vid  │
└────────────────┘    └─────────────────────────────┘    └─────────────┘
```

- **Streaming**: Agents think in real-time via SSE — no waiting
- **Interactive map**: Leaflet + OpenStreetMap with live fire markers
- **World model**: Cosmos Predict2.5-2B wildfire simulation

---

## Live Demo

1. **SCAN** — Pull live weather + satellite data for Los Angeles
2. **STREAM** — Watch 3 agents analyze in real-time
3. **SCORE** — Risk score 0–100 from averaged agent severity
4. **COORDINATE** — Unified action plan from Nemotron-3-Nano
5. **VISUALIZE** — Cosmos-generated wildfire scenario

> "You can't stop a wildfire. But you can change what people do **before** it reaches them."

---

## Impact & Vision

**Today**: Wildfire risk in California
**Tomorrow**: Any environmental threat, anywhere

- Air pollution in Delhi → "Should your kid go to school today?"
- Flooding in Houston → "Is your renter's insurance enough?"
- Heatwave in Phoenix → "Which neighbor should you check on tonight?"

Architecture is **domain-agnostic** — switch with one command.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Hardware | NVIDIA GB10 (128 GB unified memory) |
| Inference | Ollama — 4 models, GPU-accelerated |
| Backend | FastAPI + SSE streaming |
| Frontend | Leaflet + OpenStreetMap |
| Personas | NVIDIA Nemotron-Personas-USA |
| Video | NVIDIA Cosmos Predict2.5-2B |
| World Model | NVIDIA Cosmos Predict2.5-2B |
| Data | 4 free public APIs (real-time) |

**All open-source. All local. No cloud inference.**

*MAGI: Because important decisions deserve more than one opinion.*
