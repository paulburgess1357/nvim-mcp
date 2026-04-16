"""Shared types, errors, and configuration constants."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class NvimError(Exception):
    """Error from Neovim or the msgpack-RPC connection."""


@dataclass
class NvimInstance:
    socket_path: str
    pid: int
    cwd: str
    current_file: str


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        return max(0, int(val))
    except ValueError:
        return default


def _format_rpc_error(error: Any) -> str:
    """Extract a human-readable message from a msgpack-RPC error value.

    Neovim sends errors as ``[error_type, error_message]``.
    """
    if isinstance(error, (list, tuple)) and len(error) >= 2:
        return str(error[1])
    return str(error)


CONNECT_TIMEOUT: float = 5.0

ACTIVE_CONTEXT_LINES: int = _env_int("NVIM_MCP_ACTIVE_CONTEXT_LINES", 20)
INACTIVE_CONTEXT_LINES: int = _env_int("NVIM_MCP_INACTIVE_CONTEXT_LINES", 20)
