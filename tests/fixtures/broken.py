"""A file with intentional errors for diagnostics testing."""


def greet(name: str) -> str:
    return "Hello, " + name


def bad_types(x: int) -> str:
    result: str = x + 1
    return result


def unused_import_user():
    import json
    return 42
