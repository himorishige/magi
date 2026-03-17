#!/usr/bin/env python3
"""Orchestrate a 3-agent MAGI debate and output Canvas HTML."""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def call_agent(agent_id: str, prompt: str, config: str) -> dict:
    """Call a MAGI agent and return parsed response."""
    cmd = [
        sys.executable, str(SCRIPT_DIR / "call_agent.py"),
        "--agent", agent_id,
        "--prompt", prompt,
        "--config", config,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        sys.stderr.write(f"Agent {agent_id} failed: {e}\n")

    return {
        "agent": agent_id,
        "perspective": "unknown",
        "opinion": f"Agent {agent_id} failed to respond",
        "confidence": 0.0,
        "recommendation": "Manual review required",
        "key_points": ["Agent timeout or error"],
    }


def determine_pattern(opinions: list, domain: str) -> dict:
    """Determine PATTERN code from 3 agent opinions.

    Uses the 'severity' field from each agent (0.0-1.0) when available,
    falling back to 'confidence' for backward compatibility.

    Pattern codes (per IDENTITY.md):
      000 = no alert, 111 = low, 222 = moderate, 333 = elevated,
      444 = high, 555 = severe, 666 = critical
    """
    votes = {}
    personal_actions = []
    for op in opinions:
        # Prefer severity (data danger) over confidence (analysis certainty)
        sev = op.get("severity", op.get("confidence", 0.5))
        if sev >= 0.9:
            votes[op["agent"]] = "critical"
        elif sev >= 0.75:
            votes[op["agent"]] = "high"
        elif sev >= 0.6:
            votes[op["agent"]] = "moderate"
        elif sev >= 0.4:
            votes[op["agent"]] = "low"
        else:
            votes[op["agent"]] = "none"

        # Collect personal actions from all agents
        actions = op.get("personal_actions", [])
        if isinstance(actions, list):
            for a in actions:
                if a and a not in personal_actions:
                    personal_actions.append(a)

    severity_scores = {"critical": 3, "high": 2, "moderate": 1, "low": 0, "none": 0}
    total = sum(severity_scores[v] for v in votes.values())
    prefix = domain.upper()[:3] if domain else "MAG"

    # Map aggregate score (0-9) to 7 pattern levels
    if total >= 8:
        pattern, level = f"{prefix}-666", "critical"
    elif total >= 7:
        pattern, level = f"{prefix}-555", "severe"
    elif total >= 5:
        pattern, level = f"{prefix}-444", "high"
    elif total >= 4:
        pattern, level = f"{prefix}-333", "elevated"
    elif total >= 2:
        pattern, level = f"{prefix}-222", "moderate"
    elif total >= 1:
        pattern, level = f"{prefix}-111", "low"
    else:
        pattern, level = f"{prefix}-000", "clear"

    # Risk score: 0-100 based on average agent severity
    severities = [op.get("severity", op.get("confidence", 0.5)) for op in opinions]
    risk_score = round(sum(severities) / len(severities) * 100) if severities else 0

    result = {"pattern": pattern, "level": level, "votes": votes, "risk_score": risk_score}
    if personal_actions:
        result["personal_actions"] = personal_actions[:9]
    return result


def generate_canvas_html(data: dict, opinions: list, verdict: dict) -> str:
    """Generate the MAGI debate Canvas HTML with NERV aesthetic."""
    domain = data.get("domain", "unknown")
    timestamp = data.get("timestamp", datetime.now(timezone.utc).isoformat())
    summary = data.get("summary", "No data summary")
    pattern = verdict.get("pattern", "MAGI-000")
    level = verdict.get("level", "low")
    votes = verdict.get("votes", {})

    # Extract opinions
    mel = next((o for o in opinions if o["agent"] == "melchior"), {})
    bal = next((o for o in opinions if o["agent"] == "balthasar"), {})
    cas = next((o for o in opinions if o["agent"] == "casper"), {})

    blink_css = "animation: blink 1s infinite;" if level in ("critical", "severe") else ""
    level_color = {
        "critical": "#ff0040", "severe": "#ff2200", "high": "#ff8800",
        "elevated": "#ffaa00", "moderate": "#ffcc00", "low": "#00ff88", "clear": "#888",
    }.get(level, "#888")

    metrics_html = ""
    for m in data.get("metrics", [])[:6]:
        sev_color = {"critical": "#ff0040", "high": "#ff8800", "medium": "#ffcc00", "low": "#00ff88", "info": "#888"}.get(m.get("severity", "info"), "#888")
        metrics_html += f'<div class="metric"><span class="metric-name">{m["name"]}</span><span class="metric-val" style="color:{sev_color}">{m.get("value", "N/A")} {m.get("unit", "")}</span></div>'

    def agent_panel(agent: dict, color: str, name: str) -> str:
        kp = "".join(f"<li>{p}</li>" for p in agent.get("key_points", []))
        conf = agent.get("confidence", 0)
        vote = votes.get(agent.get("agent", ""), "N/A")
        return f"""
        <div class="agent-panel" style="border-color:{color}">
            <div class="agent-header" style="color:{color}">{name}</div>
            <div class="agent-label" style="color:{color}">{agent.get('perspective', '').upper()}</div>
            <div class="confidence">CONFIDENCE: {conf:.0%}</div>
            <div class="opinion">{agent.get('opinion', 'No response')[:300]}</div>
            <ul class="key-points">{kp}</ul>
            <div class="recommendation"><strong>REC:</strong> {agent.get('recommendation', 'N/A')}</div>
            <div class="vote" style="color:{color}">VOTE: {vote.upper()}</div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>MAGI Debate</title>
<style>
@keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:0.3}} }}
@keyframes scanline {{ 0%{{transform:translateY(-100%)}} 100%{{transform:translateY(100%)}} }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:#0a0a0a; color:#ccc; font-family:'Courier New',monospace; overflow:hidden; height:100vh; }}
body::after {{ content:''; position:fixed; top:0; left:0; width:100%; height:100%; background:repeating-linear-gradient(0deg,transparent,transparent 2px,rgba(0,255,100,0.03) 2px,rgba(0,255,100,0.03) 4px); pointer-events:none; z-index:1000; }}
.header {{ text-align:center; padding:12px; border-bottom:2px solid #333; }}
.pattern {{ font-size:2.5em; font-weight:bold; color:{level_color}; {blink_css} letter-spacing:8px; }}
.subtitle {{ font-size:0.8em; color:#666; margin-top:4px; }}
.domain-badge {{ display:inline-block; padding:2px 10px; background:{level_color}22; border:1px solid {level_color}; color:{level_color}; font-size:0.7em; margin-top:6px; }}
.main {{ display:flex; height:calc(100vh - 140px); }}
.sidebar {{ width:200px; padding:10px; border-right:1px solid #222; overflow-y:auto; }}
.sidebar h3 {{ color:#666; font-size:0.7em; margin-bottom:8px; text-transform:uppercase; letter-spacing:2px; }}
.metric {{ display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #1a1a1a; font-size:0.75em; }}
.metric-name {{ color:#666; }}
.metric-val {{ font-weight:bold; }}
.data-summary {{ color:#555; font-size:0.65em; margin-top:10px; padding:6px; background:#111; border:1px solid #222; }}
.agents {{ flex:1; display:flex; gap:1px; background:#1a1a1a; }}
.agent-panel {{ flex:1; padding:12px; background:#0a0a0a; border-top:3px solid; overflow-y:auto; }}
.agent-header {{ font-size:1.2em; font-weight:bold; letter-spacing:3px; margin-bottom:2px; }}
.agent-label {{ font-size:0.65em; letter-spacing:2px; margin-bottom:8px; opacity:0.7; }}
.confidence {{ font-size:0.7em; color:#888; margin-bottom:6px; }}
.opinion {{ font-size:0.75em; line-height:1.4; margin-bottom:8px; color:#aaa; }}
.key-points {{ font-size:0.7em; padding-left:14px; margin-bottom:8px; color:#999; }}
.key-points li {{ margin-bottom:3px; }}
.recommendation {{ font-size:0.7em; padding:6px; background:#111; border-left:2px solid #444; margin-bottom:6px; }}
.vote {{ font-size:0.9em; font-weight:bold; text-align:center; padding:4px; letter-spacing:2px; }}
.verdict-bar {{ display:flex; justify-content:center; align-items:center; gap:20px; padding:10px; border-top:2px solid #333; background:#0a0a0a; }}
.verdict-label {{ color:#666; font-size:0.7em; }}
.verdict-detail {{ font-size:0.9em; font-weight:bold; color:{level_color}; }}
.timestamp {{ color:#333; font-size:0.6em; }}
</style></head><body>
<div class="header">
    <div class="pattern">{pattern}</div>
    <div class="subtitle">MAGI MULTI-AGENT GOVERNANCE INTELLIGENCE</div>
    <div class="domain-badge">{domain.upper()} IMPACT</div>
</div>
<div class="main">
    <div class="sidebar">
        <h3>Data Metrics</h3>
        {metrics_html}
        <div class="data-summary">{summary[:200]}</div>
    </div>
    <div class="agents">
        {agent_panel(mel, '#00ff88', 'MELCHIOR')}
        {agent_panel(bal, '#ff8800', 'BALTHASAR')}
        {agent_panel(cas, '#8800ff', 'CASPER')}
    </div>
</div>
<div class="verdict-bar">
    <span class="verdict-label">VERDICT</span>
    <span class="verdict-detail">{pattern} — {level.upper()}</span>
    <span class="timestamp">{timestamp[:19]}</span>
</div>
</body></html>"""
    return html


def main():
    parser = argparse.ArgumentParser(description="Run MAGI 3-agent debate")
    parser.add_argument("--config", default="/app/config.json")
    parser.add_argument("--data", default=None, help="Path to data JSON (or reads latest cache)")
    args = parser.parse_args()

    # Load config
    cfg = {}
    if os.path.exists(args.config):
        with open(args.config) as f:
            cfg = json.load(f)

    domain = cfg.get("domain", "eco")

    # Load data
    data = None
    if args.data and os.path.exists(args.data):
        with open(args.data) as f:
            data = json.load(f)
    else:
        cache_dir = cfg.get("data_sources", {}).get(domain, {}).get("cache_dir", f"data/cache/{domain}")
        latest = Path(cache_dir) / "latest.json"
        if latest.exists():
            with open(latest) as f:
                data = json.load(f)

    if not data:
        data = {"domain": domain, "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "none", "metrics": [], "summary": "No data available"}

    # Build prompt from data
    prompt = f"""Analyze the following {domain} data and provide your assessment.

Domain: {domain}
Timestamp: {data.get('timestamp', 'N/A')}
Source: {data.get('source', 'N/A')}

Metrics:
{json.dumps(data.get('metrics', []), indent=2)}

Summary: {data.get('summary', 'N/A')}

Provide your analysis as JSON with: agent, perspective, opinion (max 200 words), confidence (0-1), recommendation, key_points (3 items)."""

    # Call all 3 agents
    opinions = []
    for agent_id in ["melchior", "balthasar", "casper"]:
        sys.stderr.write(f"Calling {agent_id}...\n")
        op = call_agent(agent_id, prompt, args.config)
        opinions.append(op)
        sys.stderr.write(f"  {agent_id} confidence: {op.get('confidence', 0)}\n")

    # Determine verdict
    verdict = determine_pattern(opinions, domain)
    sys.stderr.write(f"Verdict: {verdict['pattern']} ({verdict['level']})\n")

    # Generate Canvas HTML
    html = generate_canvas_html(data, opinions, verdict)

    # Save debate record
    memory_dir = Path("memory/debates")
    memory_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    with open(memory_dir / f"debate_{ts}.json", "w") as f:
        json.dump({"data": data, "opinions": opinions, "verdict": verdict, "timestamp": ts}, f, ensure_ascii=False, indent=2)

    # Output Canvas JSON
    print(json.dumps({"type": "canvas", "html": html}, ensure_ascii=False))


if __name__ == "__main__":
    main()
