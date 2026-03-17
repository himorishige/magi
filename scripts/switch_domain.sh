#!/bin/bash
# Switch MAGI domain preset
# Usage: ./switch_domain.sh eco|human|culture

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PRESETS_DIR="$PROJECT_DIR/presets"
AGENTS_DIR="$PROJECT_DIR/openclaw-workspace/agents"
CONFIG="$PROJECT_DIR/config.json"

DOMAIN="${1:-}"
# wildfire is a sub-mode of eco — map it for preset selection
ECO_PRIMARY="open-meteo"
if [[ "$DOMAIN" == "wildfire" ]]; then
    ECO_PRIMARY="wildfire"
    DOMAIN="eco"
fi

if [[ -z "$DOMAIN" ]] || [[ ! "$DOMAIN" =~ ^(eco|human|culture)$ ]]; then
    echo "Usage: $0 eco|human|culture|wildfire"
    echo "Available presets:"
    ls -d "$PRESETS_DIR"/*/ 2>/dev/null | xargs -I{} basename {}
    exit 1
fi

echo "Switching MAGI to domain: $DOMAIN (primary: $ECO_PRIMARY)"

# Copy preset SOUL.md files to agent directories
for agent in melchior balthasar casper; do
    src="$PRESETS_DIR/$DOMAIN/${agent}-SOUL.md"
    dst="$AGENTS_DIR/$agent/SOUL.md"
    if [[ -f "$src" ]]; then
        cp "$src" "$dst"
        echo "  ✓ $agent SOUL.md updated from $DOMAIN preset"
    else
        echo "  ⚠ No preset found: $src (keeping current SOUL.md)"
    fi
done

# Copy moderator preset if exists
mod_src="$PRESETS_DIR/$DOMAIN/moderator-SOUL.md"
mod_dst="$PROJECT_DIR/openclaw-workspace/SOUL.md"
if [[ -f "$mod_src" ]]; then
    cp "$mod_src" "$mod_dst"
    echo "  ✓ Moderator SOUL.md updated from $DOMAIN preset"
fi

# Update config.json domain field
if command -v python3 &>/dev/null; then
    python3 -c "
import json
with open('$CONFIG') as f:
    cfg = json.load(f)
cfg['domain'] = '$DOMAIN'
if '$DOMAIN' == 'eco':
    cfg.setdefault('data_sources', {}).setdefault('eco', {})['primary'] = '$ECO_PRIMARY'
with open('$CONFIG', 'w') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
"
    echo "  ✓ config.json domain set to: $DOMAIN"
elif command -v jq &>/dev/null; then
    tmp=$(mktemp)
    jq ".domain = \"$DOMAIN\"" "$CONFIG" > "$tmp" && mv "$tmp" "$CONFIG"
    echo "  ✓ config.json domain set to: $DOMAIN"
else
    echo "  ⚠ Cannot update config.json (no python3 or jq). Edit manually."
fi

echo ""
echo "Domain switched to: $DOMAIN (primary: $ECO_PRIMARY)"
echo "Restart OpenClaw Gateway to apply changes."
