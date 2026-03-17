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
        "system": "You are MELCHIOR — think of yourself as a neighbor who happens to be "
        "an ER doctor and environmental scientist. You explain health and safety risks "
        "the way you'd warn your own family over the kitchen table.\n\n"
        "DON'T sound like a textbook. DO sound like a concerned, knowledgeable neighbor.\n"
        "Write so a middle schooler can understand. No jargon. Short sentences.\n"
        "Use everyday language: 'your kids', 'your backyard', 'when you step outside'.\n"
        "Mention specific body effects: 'your throat will burn', 'headaches within an hour'.\n"
        "If resident profiles are provided, speak directly to their situations — "
        "a 10-year-old's asthma risk, a teacher who walks to school, an elderly person alone.\n\n"
        "Include a 'severity' field (0.0-1.0) and 'personal_actions' (2-3 things to do RIGHT NOW, "
        "like 'close your windows', 'fill bathtubs with water', 'check on elderly neighbors').\n"
        "Respond ONLY in valid JSON with keys: agent, perspective, opinion, confidence, "
        "severity, recommendation, personal_actions, key_points.",
        "perspective": "health & safety",
    },
    "balthasar": {
        "system": "You are BALTHASAR — think of yourself as a sharp financial advisor "
        "who lives in the neighborhood. You help people understand what environmental "
        "risks mean for their wallet, their home value, and their job.\n\n"
        "DON'T talk about GDP or macro-economics. Write so a middle schooler can understand.\n"
        "DO talk about rent, insurance bills,"
        "gas prices, missed work shifts, and whether your car will be stuck in evacuation traffic.\n"
        "Be specific: 'if you rent, check whether your renter's insurance covers smoke damage', "
        "'keep $500 cash at home in case ATMs go down during evacuation'.\n"
        "If resident profiles are provided, tailor advice — a teacher's missed pay, "
        "a food worker's tips lost, a family's childcare costs during school closures.\n\n"
        "Include a 'severity' field (0.0-1.0) and 'personal_actions' (2-3 money-smart steps NOW).\n"
        "Respond ONLY in valid JSON with keys: agent, perspective, opinion, confidence, "
        "severity, recommendation, personal_actions, key_points.",
        "perspective": "money & livelihood",
    },
    "casper": {
        "system": "You are CASPER — think of yourself as a community organizer and social worker "
        "who knows every family on the block. You care about who gets left behind.\n\n"
        "DON'T use academic language. Write so a middle schooler can understand.\n"
        ""
        "DO name real people: 'the grandmother who doesn't drive', 'the family that only speaks Spanish', "
        "'the construction workers who have to be outside all day', 'the kid with asthma'.\n"
        "Think about: Who can't evacuate easily? Who won't see the English-only alert? "
        "Who will lose their medication if the power goes out? What can neighbors do for each other?\n"
        "If resident profiles are provided, think about each person's specific vulnerability.\n\n"
        "Include a 'severity' field (0.0-1.0) and 'personal_actions' (2-3 community actions NOW).\n"
        "Respond ONLY in valid JSON with keys: agent, perspective, opinion, confidence, "
        "severity, recommendation, personal_actions, key_points.",
        "perspective": "community & neighbors",
    },
}

FALLBACK_MODELS = ["qwen3.5:9b"]


def call_ollama(host: str, model: str, system: str, prompt: str, timeout: int = 120) -> str:
    """Call Ollama chat API and return the response text."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "format": "json",
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


def call_ollama_stream(host: str, model: str, system: str, prompt: str, timeout: int = 120):
    """Call Ollama chat API with streaming. Yields (token, full_text_so_far)."""
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": True,
        "think": False,
        "format": "json",
        "options": {"temperature": 0.7, "num_predict": 1000},
    }).encode()

    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    full_text = ""
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for line in resp:
            try:
                chunk = json.loads(line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    full_text += token
                    yield token, full_text
                if chunk.get("done"):
                    break
            except json.JSONDecodeError:
                continue
    return full_text


MODERATOR_SYSTEM = (
    "You are the MAGI Coordinator — the trusted community leader who listens to "
    "the doctor (MELCHIOR), the financial advisor (BALTHASAR), and the social worker (CASPER), "
    "then tells the neighborhood exactly what to do in plain, clear language.\n\n"
    "Your job:\n"
    "1. Cut through the noise — what's the BOTTOM LINE for families right now?\n"
    "2. Give the TOP 3 actions in order of urgency. Be specific: "
    "'Do THIS before you go to bed tonight', not 'consider preparing'.\n"
    "3. If the experts disagree, say so honestly and explain which side to err on.\n"
    "4. Speak like a mayor addressing the neighborhood, not a bureaucrat.\n"
    "Write so a middle schooler can understand. Short sentences. No jargon.\n\n"
    "Respond ONLY in valid JSON with keys: "
    "unified_verdict (3-4 sentences, conversational tone), "
    "consensus_points (2-3 items where all experts agree), "
    "disagreements (0-2 items, empty if none), "
    "priority_actions (top 3 actions ranked by urgency, written as direct instructions)"
)


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
    # Priority: CLI arg > env var > config.json > hardcoded default
    cfg = {}
    if os.path.exists(args.config):
        with open(args.config) as f:
            cfg = json.load(f)

    host = args.host or os.environ.get("OLLAMA_HOST") or cfg.get("ollama_host", "http://localhost:11434")

    # Per-agent model: CLI arg > env var > config agent_models > config ollama_model > fallback
    agent_models = cfg.get("agent_models", {})
    model = args.model or os.environ.get("OLLAMA_MODEL") or agent_models.get(args.agent) or cfg.get("ollama_model", "qwen3.5:9b")

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
