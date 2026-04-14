"""A simple calculator module for testing nvim-mcp tools."""


def add(a: int, b: int) -> int:
    return a + b


def subtract(a: int, b: int) -> int:
    return a - b


def multiply(a: int, b: int) -> int:
    return a * b


def divide(a: int, b: int) -> float:
    return a / b


def modulo(a: int, b: int) -> int:
    return a % b


def power(a: int, b: int) -> int:
    return a ** b


OPERATIONS = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
    "modulo": modulo,
    "power": power,
}


def run(op: str, a: int, b: int):
    if op not in OPERATIONS:
        raise ValueError(f"Unknown operation: {op}")
    return OPERATIONS[op](a, b)
