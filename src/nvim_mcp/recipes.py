"""Load and serve Neovim operation recipes for the nvim_recipes MCP tool."""

from __future__ import annotations

import re
from functools import lru_cache
from importlib import resources


QUICK_REFERENCE = """Quick reference (top operations):

1. **Open file:** `nvim_send(input="e /path/to/file", mode="command")`
2. **Save file:** `nvim_send(input="w", mode="command")`
3. **Go to line:** `nvim_send(input="42", mode="command")`
4. **Reload from disk:** `nvim_send(input="checktime", mode="command")`
5. **Close buffer:** `nvim_send(input="bd", mode="command")`
6. **Vertical split:** `nvim_send(input="vs /path/to/file", mode="command")`
7. **Navigate windows:** `nvim_send(input="wincmd w", mode="command")`
8. **LSP go-to-definition:** `nvim_send(input="lua vim.lsp.buf.definition()", mode="command")`
9. **LSP references:** `nvim_send(input="lua vim.lsp.buf.references()", mode="command")`
"""


def _read_recipes_md() -> str:
    return resources.files("nvim_mcp").joinpath("recipes.md").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _parsed_recipes() -> dict[str, str]:
    text = _read_recipes_md()
    pattern = re.compile(r"^## (.+)$", re.MULTILINE)
    parts = pattern.split(text)
    result: dict[str, str] = {}
    # parts[0] is preamble before first ##; then (title, body)+
    i = 1
    while i + 1 < len(parts):
        name = parts[i].strip().lower()
        body = parts[i + 1].strip()
        result[name] = body
        i += 2
    return result


def load_recipes() -> dict[str, str]:
    """Parse recipes.md into {category_name: body_text} dict.

    Split on ^## headers. Each header becomes a category key (lowercased, stripped).
    Category body is everything until the next ^## or EOF.
    """
    return dict(_parsed_recipes())


def get_recipes(category: str | None = None) -> str:
    """
    No category: return QUICK_REFERENCE + list of category names.
    With category: return full recipes for that section.
    Unknown category: return error message with valid categories listed.
    """
    recipes = load_recipes()
    names = sorted(recipes)

    if category is None:
        lines = [QUICK_REFERENCE.rstrip(), "", "Categories:", *[f"- {n}" for n in names]]
        return "\n".join(lines) + "\n"

    key = category.strip().lower()
    if key in recipes:
        return f"## {category.strip()}\n\n{recipes[key]}\n"

    valid = ", ".join(names)
    return f"Unknown category {category!r}. Valid categories: {valid}\n"
