#!/usr/bin/env bash
# Generate nvim-mcp rule files for different AI coding tools.
# Usage: ./config/generate-configs.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$SCRIPT_DIR/AGENTS-EXAMPLE.md"

if [[ ! -f "$SOURCE" ]]; then
    echo "Error: $SOURCE not found" >&2
    exit 1
fi

cursor_rule_content() {
    cat <<'FRONTMATTER'
---
description: Neovim via nvim-mcp
alwaysApply: true
---

FRONTMATTER
    cat "$SOURCE"
}

generate_cursor() {
    local config_out="$SCRIPT_DIR/nvim-mcp.mdc"
    local plugin_out="$REPO_ROOT/rules/nvim-mcp.mdc"

    for out in "$config_out" "$plugin_out"; do
        mkdir -p "$(dirname "$out")"
        cursor_rule_content > "$out"
        echo "Generated: $out"
    done
    echo "  Local copy: place at ~/.cursor/rules/nvim-mcp.mdc (global)"
    echo "                    or <project>/.cursor/rules/nvim-mcp.mdc (per-project)"
    echo "  Plugin copy (tracked in repo): rules/nvim-mcp.mdc — ships with the marketplace plugin"
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

usage() {
    cat <<EOF
Usage: $(basename "$0") [FLAG]

Run with no arguments for an interactive menu.

Flags (non-interactive, for use in scripts):
  --cursor      Generate the Cursor rule (config/nvim-mcp.mdc and rules/nvim-mcp.mdc)
  --claude      Generate config/CLAUDE.md
  --codex       Generate config/AGENTS.md (Codex)
  --opencode    Generate config/AGENTS.md (OpenCode)
  --all         Generate all of the above
  -h, --help    Show this help
EOF
}

main() {
    if [[ $# -gt 0 ]]; then
        case "$1" in
            --cursor)   generate_cursor ;;
            --claude)   generate_claude ;;
            --codex)    generate_codex ;;
            --opencode) generate_opencode ;;
            --all)
                generate_cursor
                echo ""
                generate_claude
                echo ""
                generate_codex
                echo ""
                generate_opencode
                ;;
            -h|--help) usage; exit 0 ;;
            *) echo "Unknown flag: $1" >&2; usage >&2; exit 1 ;;
        esac
        return
    fi

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
