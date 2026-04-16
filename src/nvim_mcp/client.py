"""Synchronous msgpack-RPC client for Neovim's socket API (Unix and TCP)."""

from __future__ import annotations

import re
import socket
from typing import Any

import msgpack

from nvim_mcp.types import CONNECT_TIMEOUT, NvimError, _format_rpc_error

_MAX_NON_RESPONSE_MESSAGES = 1000

_TCP_RE = re.compile(r"^(?!/)(.+):(\d+)$")


def _parse_tcp_address(address: str) -> tuple[str, int] | None:
    """Return ``(host, port)`` if *address* looks like a TCP endpoint, else ``None``."""
    m = _TCP_RE.match(address)
    if m is None:
        return None
    return m.group(1), int(m.group(2))


class NvimClient:
    """Speaks the msgpack-RPC wire protocol (request/response only) directly
    over Neovim's socket.  No plugin-host machinery, no event loop —
    just the three RPC methods this project needs.
    """

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
        self._next_msgid = 0

    def __enter__(self) -> NvimClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @classmethod
    def connect(cls, address: str, timeout: float = CONNECT_TIMEOUT) -> NvimClient:
        """Open a connection to Neovim at *address* (Unix socket path or ``host:port``)."""
        tcp = _parse_tcp_address(address)
        if tcp is not None:
            host, port = tcp
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                sock.connect((host, port))
            except Exception:
                sock.close()
                raise
        else:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                sock.connect(address)
            except Exception:
                sock.close()
                raise
        return cls(sock)

    def request(self, method: str, *args: Any) -> Any:
        """Send an RPC request and block until the matching response arrives."""
        self._next_msgid += 1
        msgid = self._next_msgid
        self._sock.sendall(msgpack.packb([0, msgid, method, list(args)]))
        return self._read_response(msgid)

    def _read_response(self, expected_msgid: int) -> Any:
        skipped = 0
        while True:
            data = self._sock.recv(65536)
            if not data:
                raise NvimError("Connection closed by Neovim")
            self._unpacker.feed(data)
            for msg in self._unpacker:
                if not isinstance(msg, (list, tuple)) or len(msg) < 4:
                    skipped += 1
                    if skipped >= _MAX_NON_RESPONSE_MESSAGES:
                        raise NvimError("Too many non-response messages")
                    continue
                msg_type, rmsgid, error, result = msg[0], msg[1], msg[2], msg[3]
                if msg_type != 1 or rmsgid != expected_msgid:
                    skipped += 1
                    if skipped >= _MAX_NON_RESPONSE_MESSAGES:
                        raise NvimError("Too many non-response messages")
                    continue
                if error is not None:
                    raise NvimError(_format_rpc_error(error))
                return result

    def exec_lua(self, code: str, *args: Any) -> Any:
        return self.request("nvim_exec_lua", code, list(args))

    def eval(self, expr: str) -> Any:
        return self.request("nvim_eval", expr)

    def input(self, keys: str) -> int:
        return self.request("nvim_input", keys)

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass
