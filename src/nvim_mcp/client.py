"""Synchronous msgpack-RPC client for Neovim's Unix socket API."""

from __future__ import annotations

import socket
from typing import Any

import msgpack

from nvim_mcp.types import CONNECT_TIMEOUT, NvimError, _format_rpc_error


class NvimClient:
    """Speaks the msgpack-RPC wire protocol (request/response only) directly
    over Neovim's Unix socket.  No plugin-host machinery, no event loop —
    just the three RPC methods this project needs.
    """

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
        self._next_msgid = 0

    @classmethod
    def connect(cls, path: str, timeout: float = CONNECT_TIMEOUT) -> NvimClient:
        """Open a Unix-socket connection to Neovim at *path*."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(path)
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
        while True:
            data = self._sock.recv(65536)
            if not data:
                raise NvimError("Connection closed by Neovim")
            self._unpacker.feed(data)
            for msg in self._unpacker:
                if not isinstance(msg, (list, tuple)) or len(msg) < 4:
                    continue
                msg_type, rmsgid, error, result = msg[0], msg[1], msg[2], msg[3]
                if msg_type != 1 or rmsgid != expected_msgid:
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
