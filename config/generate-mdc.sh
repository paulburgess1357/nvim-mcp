#!/usr/bin/env bash
# Generate nvim-mcp.mdc (Cursor rule file) from AGENTS.md.
# Usage: ./config/generate-mdc.sh [output-path]
#   Defaults to config/nvim-mcp.mdc next to AGENTS.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTS_MD="$SCRIPT_DIR/AGENTS.md"
OUTPUT="${1:-"$SCRIPT_DIR/nvim-mcp.mdc"}"

if [[ ! -f "$AGENTS_MD" ]]; then
    echo "Error: $AGENTS_MD not found" >&2
    exit 1
fi

cat > "$OUTPUT" <<'FRONTMATTER'
---
description: Neovim via nvim-mcp
alwaysApply: true
---

FRONTMATTER

cat "$AGENTS_MD" >> "$OUTPUT"

echo "Generated $OUTPUT"
