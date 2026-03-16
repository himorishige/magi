#!/usr/bin/env python3
"""Call a single MAGI agent via Ollama HTTP API with persona injection."""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

AGENT_PERSONAS = {
    "melchior": {
        "system": "You are MELCHIOR, the scientific analysis component of the MAGI system. "
        "Analyze the provided data from a purely scientific, evidence-based perspective. "
        "Cite specific numbers. Never use emotional language. Never discuss costs. "
        "Respond ONLY in valid JSON with keys: agent, perspective, opinion, confidence, recommendation, key_points.",
        "perspective": "science",
    },
    "balthasar": {
        "system": "You are BALTHASAR, the economic analysis component of the MAGI system. "
        "Analyze the provided data from an economic and pragmatic perspective. "
        "Estimate costs, GDP impact, and feasibility. Be realistic and grounded. "
        "Respond ONLY in valid JSON with keys: agent, perspective, opinion, confidence, recommendation, key_points.",
        "perspective": "economics",
    },
    "casper": {
        "system": "You are CASPER, the ethical analysis component of the MAGI system. "
        "Analyze the provided data from an ethical and future-oriented perspective. "
        "Consider long-term consequences, vulnerable populations, and intergenerational justice. "
        "Respond ONLY in valid JSON with keys: agent, perspective, opinion, confidence, recommendation, key_points.",
        "perspective": "ethics",
    },
}

FALLBACK_MODELS = ["qwen3.5:35b-a3b"]


def call_ollama(host: str, model: str, system: str, prompt: str, timeout: int = 120) -> str:
    """Call Ollama chat API and return the response text."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 1000},
    }).encode()

    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data.get("message", {}).get("content", "")


def parse_agent_response(raw: str, agent_id: str) -> dict:
    """Parse agent response, extracting JSON even if wrapped in markdown."""
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        result = json.loads(text)
        result["agent"] = agent_id
        return result
    except json.JSONDecodeError:
        return {
            "agent": agent_id,
            "perspective": AGENT_PERSONAS.get(agent_id, {}).get("perspective", "unknown"),
            "opinion": raw[:500],
            "confidence": 0.5,
            "recommendation": "Unable to parse structured response",
            "key_points": ["Response parsing failed — raw text preserved in opinion field"],
        }


def main():
    parser = argparse.ArgumentParser(description="Call a MAGI agent via Ollama")
    parser.add_argument("--agent", required=True, choices=["melchior", "balthasar", "casper"])
    parser.add_argument("--prompt", required=True, help="Prompt text or path to JSON file")
    parser.add_argument("--model", default=None, help="Override model (default: from config)")
    parser.add_argument("--host", default=None, help="Ollama host URL")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--config", default="/app/config.json")
    args = parser.parse_args()

    # Load config for defaults
    host = args.host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    model = args.model or os.environ.get("OLLAMA_MODEL", "qwen3.5:35b-a3b")

    if os.path.exists(args.config):
        with open(args.config) as f:
            cfg = json.load(f)
        host = args.host or cfg.get("ollama_host", host)
        model = args.model or cfg.get("ollama_model", model)

    persona = AGENT_PERSONAS[args.agent]

    # Prompt can be a file path or direct text
    prompt_text = args.prompt
    if os.path.exists(args.prompt):
        with open(args.prompt) as f:
            prompt_text = f.read()

    # Try primary model, then fallbacks
    models_to_try = [model] + [m for m in FALLBACK_MODELS if m != model]
    last_error = None

    for m in models_to_try:
        try:
            raw = call_ollama(host, m, persona["system"], prompt_text, args.timeout)
            result = parse_agent_response(raw, args.agent)
            print(json.dumps(result, ensure_ascii=False))
            return
        except Exception as e:
            last_error = e
            continue

    # All models failed
    print(json.dumps({
        "agent": args.agent,
        "perspective": persona["perspective"],
        "opinion": f"All models failed. Last error: {last_error}",
        "confidence": 0.0,
        "recommendation": "Manual review required",
        "key_points": ["Agent inference failed"],
    }), file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
