---
name: magi-scan
description: Quick single-point data scan without full debate
---

# MAGI Scan

When the user asks for a quick check or scan, run a lightweight analysis.

## Steps

1. Fetch the latest data:
   ```
   exec /app/scripts/fetch_data.py --config /app/config.json
   ```

2. Provide a brief summary in chat (3-5 sentences) covering:
   - Current data status
   - Any anomalies detected
   - Whether a full debate is recommended

## Important

- This is a quick check, NOT a full debate
- If anomalies are critical (would be PATTERN 444+), recommend triggering `magi-debate`
