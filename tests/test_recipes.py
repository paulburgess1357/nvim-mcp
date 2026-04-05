"""Tests for recipes loading, filtering, and quick reference."""

from nvim_mcp.recipes import QUICK_REFERENCE, get_recipes, load_recipes

EXPECTED_CATEGORIES = {
    "files",
    "navigation",
    "buffers",
    "windows & tabs",
    "marks",
    "registers",
    "folds",
    "lsp & diagnostics",
}


class TestLoadRecipes:
    def test_returns_all_categories(self):
        recipes = load_recipes()
        assert set(recipes.keys()) == EXPECTED_CATEGORIES

    def test_keys_are_lowercased(self):
        recipes = load_recipes()
        for key in recipes:
            assert key == key.lower(), f"Key {key!r} is not lowercased"

    def test_bodies_are_nonempty(self):
        recipes = load_recipes()
        for name, body in recipes.items():
            assert body.strip(), f"Category {name!r} has an empty body"


class TestGetRecipes:
    def test_no_category_returns_quick_reference(self):
        result = get_recipes(None)
        assert "Quick reference" in result

    def test_no_category_lists_all_categories(self):
        result = get_recipes(None)
        for name in EXPECTED_CATEGORIES:
            assert f"- {name}" in result

    def test_known_category_lowercase(self):
        result = get_recipes("files")
        assert "## files" in result
        assert "Open file" in result

    def test_known_category_preserves_case_in_header(self):
        result = get_recipes("Files")
        assert "## Files" in result

    def test_known_category_case_insensitive(self):
        lower = get_recipes("files")
        upper = get_recipes("Files")
        assert "Open file" in lower
        assert "Open file" in upper

    def test_unknown_category_returns_error(self):
        result = get_recipes("nonexistent")
        assert "Unknown category" in result
        assert "'nonexistent'" in result

    def test_unknown_category_lists_valid_categories(self):
        result = get_recipes("nonexistent")
        for name in EXPECTED_CATEGORIES:
            assert name in result


class TestQuickReference:
    EXPECTED_OPERATIONS = [
        "Open file",
        "Save file",
        "Go to line",
        "Reload from disk",
        "Close buffer",
        "Vertical split",
        "Navigate windows",
        "LSP go-to-definition",
        "LSP references",
    ]

    def test_contains_all_operations(self):
        for op in self.EXPECTED_OPERATIONS:
            assert op in QUICK_REFERENCE, f"Missing operation: {op!r}"

    def test_operation_count(self):
        numbered = [
            line
            for line in QUICK_REFERENCE.splitlines()
            if line.strip() and line.strip()[0].isdigit()
        ]
        assert len(numbered) == 9
