# MAGI — Multi-Agent Governance Intelligence

Three AI agents autonomously debate data anomalies from different perspectives and produce governance recommendations.

Inspired by the MAGI supercomputer from Neon Genesis Evangelion.

## Agents

| Agent | Perspective | Color |
|-------|------------|-------|
| **MELCHIOR** | Science & Data | Green |
| **BALTHASAR** | Economics & Pragmatics | Orange |
| **CASPER** | Ethics & Future | Purple |

## Features

- **Data Domain Agnostic**: Switch between Eco/Human/Culture Impact with one command
- **Autonomous Monitoring**: Heartbeat-driven continuous data surveillance
- **Canvas Visualization**: NERV-aesthetic 3-panel debate dashboard
- **PATTERN Verdicts**: Multi-agent consensus scoring (000-666)
- **Offline-First**: Works with cached data when APIs are unavailable

## Quick Start

```bash
./setup.sh                           # Pull models, init directories
./scripts/switch_domain.sh eco       # Set domain (eco/human/culture)
cd openclaw-workspace && openclaw start
# Open http://localhost:18789
```

## Stack

- **OpenClaw** 2026.3.8 (agent framework)
- **Ollama** + Qwen3.5:35b-a3b (local LLM, 23GB)
- **NVIDIA GB10** / DGX Spark (128GB unified memory)

## License

MIT
