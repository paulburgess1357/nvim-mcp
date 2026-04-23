#!/usr/bin/env bash
# Generate nvim-mcp rule files for different AI coding tools.
# Usage: ./config/generate-configs.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE="$SCRIPT_DIR/AGENTS-EXAMPLE.md"

if [[ ! -f "$SOURCE" ]]; then
    echo "Error: $SOURCE not found" >&2
    exit 1
fi

generate_cursor() {
    local out="${1:-$SCRIPT_DIR/nvim-mcp.mdc}"
    {
        cat <<'FRONTMATTER'
---
description: Neovim via nvim-mcp
alwaysApply: true
---

FRONTMATTER
        cat "$SOURCE"
    } > "$out"
    echo "Generated: $out"
    echo "  Place at: ~/.cursor/rules/nvim-mcp.mdc (global)"
    echo "       or:  <project>/.cursor/rules/nvim-mcp.mdc (per-project)"
}

generate_claude() {
    local out="${1:-$SCRIPT_DIR/CLAUDE.md}"
    cp "$SOURCE" "$out"
    echo "Generated: $out"
    echo "  Place at: ~/.claude/CLAUDE.md (global)"
    echo "       or:  <project>/CLAUDE.md (per-project)"
    echo "  Tip: append to an existing file with:  cat $out >> ~/.claude/CLAUDE.md"
}

generate_opencode() {
    local out="${1:-$SCRIPT_DIR/AGENTS.md}"
    cp "$SOURCE" "$out"
    echo "Generated: $out"
    echo "  Place at: ~/.config/opencode/AGENTS.md (global)"
    echo "       or:  <project>/AGENTS.md (per-project)"
    echo "  Tip: append to an existing file with:  cat $out >> ~/.config/opencode/AGENTS.md"
}

generate_codex() {
    local out="${1:-$SCRIPT_DIR/AGENTS.md}"
    cp "$SOURCE" "$out"
    echo "Generated: $out"
    echo "  Place at: ~/.codex/AGENTS.md (global)"
    echo "       or:  <project>/AGENTS.md (per-project)"
    echo "  Tip: append to an existing file with:  cat $out >> ~/.codex/AGENTS.md"
}

show_menu() {
    echo "nvim-mcp config generator"
    echo "========================="
    echo ""
    echo "Files are generated in config/ for you to copy where needed."
    echo "Your existing config files will not be modified."
    echo ""
    echo "Which config would you like to generate?"
    echo ""
    echo "  1) Cursor      (~/.cursor/rules/nvim-mcp.mdc)"
    echo "  2) Claude      (~/.claude/CLAUDE.md)"
    echo "  3) Codex       (~/.codex/AGENTS.md)"
    echo "  4) OpenCode    (~/.config/opencode/AGENTS.md)"
    echo "  5) All"
    echo "  q) Quit"
    echo ""
}

main() {
    show_menu
    read -rp "Choice [1-5/q]: " choice

    echo ""
    case "$choice" in
        1) generate_cursor ;;
        2) generate_claude ;;
        3) generate_codex ;;
        4) generate_opencode ;;
        5)
            generate_cursor
            echo ""
            generate_claude
            echo ""
            generate_codex
            echo ""
            generate_opencode
            ;;
        q|Q) echo "Bye."; exit 0 ;;
        *)
            echo "Invalid choice: $choice" >&2
            exit 1
            ;;
    esac
}

main "$@"
