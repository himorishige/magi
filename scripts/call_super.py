#!/usr/bin/env python3
"""Direct Ollama API call with fallback chain. Utility for MAGI skills."""

import argparse
import json
import os
import sys
import urllib.request

FALLBACK_CHAIN = [
    "nemotron-3-super",
    "qwen3.5:35b-a3b",
]


def call_ollama(host: str, model: str, system: str, prompt: str,
                timeout: int = 120, temperature: float = 0.7, max_tokens: int = 1000,
                json_mode: bool = False) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "think": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read())
    return result.get("message", {}).get("content", "")


def main():
    parser = argparse.ArgumentParser(description="Call Ollama with fallback chain")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--system", default="You are a helpful AI assistant.")
    parser.add_argument("--model", default=None, help="Primary model (tries fallbacks if fails)")
    parser.add_argument("--host", default=None)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=1000)
    parser.add_argument("--json", action="store_true", help="Request JSON output")
    args = parser.parse_args()

    host = args.host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    models = [args.model] + FALLBACK_CHAIN if args.model else FALLBACK_CHAIN
    models = [m for m in models if m]  # remove None

    for model in models:
        try:
            result = call_ollama(host, model, args.system, args.prompt,
                                 args.timeout, args.temperature, args.max_tokens, args.json)
            print(result)
            return
        except Exception as e:
            sys.stderr.write(f"Model {model} failed: {e}\n")

    sys.stderr.write("All models in fallback chain failed\n")
    sys.exit(1)


if __name__ == "__main__":
    main()
