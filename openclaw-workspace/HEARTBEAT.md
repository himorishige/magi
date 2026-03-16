# HEARTBEAT — Autonomous Monitoring

Every heartbeat cycle, perform the following:

1. Run `exec /app/scripts/fetch_data.py --domain auto --cache-only` to check for new data
2. If new anomalies are detected, trigger `magi-debate` skill
3. Log results to memory/
4. If PATTERN level >= 444, alert via Canvas immediately
