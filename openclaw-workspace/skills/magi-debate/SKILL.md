---
name: magi-debate
description: Trigger a full MAGI 3-agent debate on current data anomalies
---

# MAGI Debate

When the user asks to analyze data, debate an issue, or check the current status, execute a full MAGI debate.

## Steps

1. Fetch the latest data:
   ```
   exec /app/scripts/fetch_data.py --config /app/config.json
   ```

2. Run the 3-agent debate and generate Canvas output:
   ```
   exec /app/scripts/debate_canvas.py --config /app/config.json --data /app/data/cache/latest.json
   ```

3. Send a brief chat message with the PATTERN code result only.
   Example: "PATTERN ECO-444 — Moderate alert. See Canvas for full debate."

## Important

- Do NOT generate your own analysis. Let the scripts handle everything.
- Do NOT show raw JSON in chat. Canvas is the only output channel.
- If fetch_data.py fails, try with `--cache-only` flag.
