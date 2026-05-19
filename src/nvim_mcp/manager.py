"""NeovimManager: multi-instance discovery, connection, and tool orchestration."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from nvim_mcp.client import NvimClient
from nvim_mcp.discovery import find_all_sockets, find_socket_for_terminal, probe_socket
from nvim_mcp.lua import (
    EDIT_BUF,
    EXEC_COMMAND,
    GET_DIAGNOSTICS,
    GET_STATE,
    GET_STATE_BRIEF,
    HIGHLIGHT,
    READ_BUF,
    VIRTUAL_TEXT,
)
from nvim_mcp.types import (
    ACTIVE_CONTEXT_LINES,
    BRIEF_CONTEXT_LINES,
    CONNECT_TIMEOUT,
    INACTIVE_CONTEXT_LINES,
    NvimError,
    NvimInstance,
)


def _is_connection_error(e: Exception) -> bool:
    if isinstance(e, OSError):
        return True
    if isinstance(e, NvimError):
        msg = str(e).lower()
        return any(
            kw in msg
            for kw in ("eof", "broken pipe", "connection", "transport", "closed")
        )
    return False


def _format_instance_dict(instances: list[NvimInstance]) -> dict:
    return {
        "error": "Multiple Neovim instances found. Use index, socket_path, or terminal_pid to select one.",
        "instances": [
            {
                "index": i,
                "socket_path": inst.socket_path,
                "cwd": inst.cwd,
                "file": inst.current_file or "(none)",
            }
            for i, inst in enumerate(instances, 1)
        ],
    }


class NeovimManager:
    def __init__(self) -> None:
        self._nvim: NvimClient | None = None
        self._socket_path: str | None = None
        self._lock = asyncio.Lock()
        self._discovery_cache: tuple[float, list[NvimInstance]] | None = None
        self._discovery_cache_ttl = 30.0

    async def shutdown(self) -> None:
        """Close the current connection and clear state."""
        async with self._lock:
            if self._nvim is not None:
                try:
                    self._nvim.close()
                except Exception:
                    pass
                self._nvim = None

    # -- Discovery -----------------------------------------------------------

    async def discover(self) -> list[NvimInstance]:
        if self._discovery_cache is not None:
            ts, cached = self._discovery_cache
            if time.monotonic() - ts < self._discovery_cache_ttl:
                return list(cached)

        candidates = find_all_sockets()

        async def _probe(sock: str) -> NvimInstance | None:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(probe_socket, sock),
                    timeout=CONNECT_TIMEOUT,
                )
            except Exception:
                return None

        results = await asyncio.gather(*(_probe(s) for s in candidates))
        instances = [r for r in results if r is not None]
        self._discovery_cache = (time.monotonic(), instances)
        return instances

    # -- Connection ----------------------------------------------------------

    async def connect(
        self,
        socket_path: str | None = None,
        terminal_pid: int | None = None,
        index: int | None = None,
    ) -> dict:
        instances = await self.discover()

        if socket_path is not None:
            target = socket_path
        elif terminal_pid is not None:
            target = find_socket_for_terminal(terminal_pid, instances)
            if target is None:
                return {
                    "error": f"No Neovim instance found for terminal PID {terminal_pid}."
                }
        elif index is not None:
            if index < 1 or index > len(instances):
                return {
                    "error": f"Index {index} out of range. Found {len(instances)} instance(s)."
                }
            target = instances[index - 1].socket_path
        elif len(instances) == 1:
            target = instances[0].socket_path
        elif len(instances) == 0:
            return {"error": "No Neovim instances found. Is Neovim running?"}
        else:
            return _format_instance_dict(instances)

        async with self._lock:
            try:
                self._nvim = await self._connect_to(target)
                self._socket_path = target
            except (asyncio.TimeoutError, OSError) as e:
                return {"error": f"Could not connect to {target}: {e}"}

            try:
                state = await asyncio.to_thread(self._get_state_sync)
                cwd = state.get("cwd", "?")
                wins = state.get("windows", [])
                current_file = wins[0].get("file", "") if wins else ""
                current_file = current_file or "(none)"
            except Exception:
                cwd = "?"
                current_file = "?"

        return {"connected": target, "cwd": cwd, "file": current_file}

    # -- Tool methods --------------------------------------------------------

    async def send_command(self, command: str | list[str]) -> dict | list[dict]:
        if isinstance(command, str):
            return await self._with_retry(
                self._run_command_sync, command, raise_on_error=True
            )
        return await self._with_retry(
            self._run_commands_sync, command, raise_on_error=True
        )

    async def send_keys(self, keys: str) -> dict:
        return await self._with_retry(
            self._run_keys_sync, keys, raise_on_error=True
        )

    async def get_state(self) -> dict:
        return await self._with_retry(
            self._get_state_sync, raise_on_error=True
        )

    async def get_state_brief(self) -> dict:
        return await self._with_retry(
            self._get_state_brief_sync, raise_on_error=True
        )

    async def get_diagnostics(self, file: str | None = None) -> list:
        return await self._with_retry(
            self._get_diagnostics_sync, file, raise_on_error=True
        )

    async def edit_buffer(
        self,
        file: str,
        new_string: str,
        old_string: str | None = None,
    ) -> dict:
        return await self._with_retry(
            self._edit_buf_sync, file, old_string, new_string,
            raise_on_error=True,
        )

    async def read_buffer(
        self,
        file: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> dict:
        return await self._with_retry(
            self._read_buf_sync, file, start_line, end_line,
            raise_on_error=True,
        )

    async def highlight_buffer(
        self,
        file: str,
        start_line: int,
        end_line: int,
        color: str = "Comment",
    ) -> dict:
        return await self._with_retry(
            self._highlight_buf_sync, file, start_line, end_line, color,
            raise_on_error=True,
        )

    async def clear_highlights(self, file: str) -> dict:
        return await self._with_retry(
            self._clear_highlights_sync, file, raise_on_error=True,
        )

    async def add_virtual_text(
        self,
        file: str,
        line: int,
        text: list[str],
        position: str = "eol",
        color: str = "Comment",
    ) -> dict:
        return await self._with_retry(
            self._add_vt_sync, file, line, text, position, color,
            raise_on_error=True,
        )

    async def clear_virtual_texts(self, file: str) -> dict:
        return await self._with_retry(
            self._clear_vt_sync, file, raise_on_error=True,
        )

    # -- Sync helpers --------------------------------------------------------

    def _run_command_sync(self, command: str) -> dict:
        assert self._nvim is not None
        result = self._nvim.exec_lua(EXEC_COMMAND, command)
        output = result.get("output", "") or ""
        errmsg = result.get("errmsg", "") or ""
        resp: dict[str, str] = {}
        if output:
            resp["output"] = output
        if errmsg:
            resp["error"] = errmsg
        return resp if resp else {"output": "(no output)"}

    def _run_commands_sync(self, commands: list[str]) -> list[dict]:
        return [self._run_command_sync(cmd) for cmd in commands]

    def _run_keys_sync(self, keys: str) -> dict:
        assert self._nvim is not None
        self._nvim.input("<Esc>" + keys)
        return {"sent": keys}

    def _get_state_sync(self) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(
            GET_STATE, ACTIVE_CONTEXT_LINES, INACTIVE_CONTEXT_LINES
        )

    def _get_state_brief_sync(self) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(GET_STATE_BRIEF, BRIEF_CONTEXT_LINES)

    def _get_diagnostics_sync(self, file: str | None) -> list:
        assert self._nvim is not None
        result = self._nvim.exec_lua(GET_DIAGNOSTICS, file)
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])
        return result

    def _edit_buf_sync(
        self,
        file: str,
        old_string: str | None,
        new_string: str,
    ) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(EDIT_BUF, file, old_string, new_string)

    def _read_buf_sync(
        self,
        file: str,
        start_line: int | None,
        end_line: int | None,
    ) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(READ_BUF, file, start_line, end_line)

    def _highlight_buf_sync(
        self,
        file: str,
        start_line: int,
        end_line: int,
        color: str,
    ) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(
            HIGHLIGHT, file, start_line, end_line, color, False
        )

    def _clear_highlights_sync(self, file: str) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(HIGHLIGHT, file, None, None, None, True)

    def _add_vt_sync(
        self,
        file: str,
        line: int,
        text: list[str],
        position: str,
        color: str,
    ) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(
            VIRTUAL_TEXT, file, line, text, position, color, False
        )

    def _clear_vt_sync(self, file: str) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(
            VIRTUAL_TEXT, file, None, None, None, None, True
        )

    # -- Connection helpers --------------------------------------------------

    async def _with_retry(self, fn, *args, raise_on_error: bool = False):
        """Acquire lock, auto-connect if needed, run *fn* with retry on disconnect."""
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    if raise_on_error:
                        raise RuntimeError(err.get("error", str(err)))
                    return err
            return await self._retry_on_disconnect(fn, *args)

    async def _connect_to(self, path: str) -> NvimClient:
        return await asyncio.wait_for(
            asyncio.to_thread(NvimClient.connect, path),
            timeout=CONNECT_TIMEOUT,
        )

    async def _auto_connect_unlocked(self) -> dict | None:
        """Auto-connect when a single instance exists.

        Returns an error dict on failure, None on success.
        """
        instances = await self.discover()
        if len(instances) == 0:
            self._discovery_cache = None
            return {"error": "No Neovim instances found. Is Neovim running?"}
        if len(instances) > 1:
            return _format_instance_dict(instances)

        target = instances[0].socket_path
        try:
            self._nvim = await self._connect_to(target)
            self._socket_path = target
        except (asyncio.TimeoutError, OSError) as e:
            return {"error": f"Could not auto-connect to {target}: {e}"}
        return None

    async def _reconnect_unlocked(self) -> None:
        """Re-attach to the last-known socket."""
        if self._nvim is not None:
            try:
                self._nvim.close()
            except Exception:
                pass
            self._nvim = None

        if self._socket_path is None:
            raise RuntimeError("Cannot reconnect: no previous socket path.")

        try:
            self._nvim = await self._connect_to(self._socket_path)
        except (asyncio.TimeoutError, OSError) as e:
            raise RuntimeError(f"Reconnect to {self._socket_path} failed: {e}") from e

    async def _retry_on_disconnect(self, fn, *args):
        """Run *fn* in a thread; on connection error, reconnect and retry once."""
        try:
            return await asyncio.to_thread(fn, *args)
        except (OSError, NvimError) as e:
            if not _is_connection_error(e):
                raise
            await self._reconnect_unlocked()
            return await asyncio.to_thread(fn, *args)
