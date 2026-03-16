---
name: magi-monitor
description: Continuous monitoring mode linked to HEARTBEAT
---

# MAGI Monitor

When the user asks to start monitoring or continuous watch, activate periodic checks.

## Steps

1. Acknowledge monitoring mode activation
2. On each HEARTBEAT cycle, run:
   ```
   exec /app/scripts/fetch_data.py --config /app/config.json
   ```
3. If anomaly severity >= "high", automatically trigger `magi-debate` skill
4. If no anomalies, log status to memory and wait for next cycle

## Important

- Monitoring runs autonomously via HEARTBEAT
- Only trigger full debates for significant anomalies
- Always log results even when no action is needed
