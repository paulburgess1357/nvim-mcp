"""NeovimManager: multi-instance socket discovery, connection, and communication."""

from __future__ import annotations

import asyncio
import os
import stat
import subprocess
import time
from dataclasses import dataclass

import pynvim


@dataclass
class NvimInstance:
    socket_path: str
    pid: int
    cwd: str
    current_file: str


_GET_STATE_LUA = """\
local wins = {}
for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local b = vim.api.nvim_win_get_buf(w)
    wins[#wins + 1] = {
        file = vim.api.nvim_buf_get_name(b),
        modified = vim.bo[b].modified,
        active = (w == vim.api.nvim_get_current_win()),
    }
end
local modified = {}
local buf_count = 0
for _, b in ipairs(vim.api.nvim_list_bufs()) do
    if vim.bo[b].buflisted and vim.api.nvim_buf_is_loaded(b) then
        buf_count = buf_count + 1
        if vim.bo[b].modified then
            modified[#modified + 1] = vim.api.nvim_buf_get_name(b)
        end
    end
end
return {
    file = vim.fn.expand('%:p'),
    line = vim.fn.line('.'),
    col = vim.fn.col('.'),
    mode = vim.fn.mode(),
    modified = vim.bo.modified,
    filetype = vim.bo.filetype,
    total_lines = vim.fn.line('$'),
    cwd = vim.fn.getcwd(),
    relativenumber = vim.wo.relativenumber,
    windows = wins,
    modified_buffers = modified,
    buffer_count = buf_count,
}
"""

_EXEC_COMMAND_LUA = """\
local input = ...
vim.v.errmsg = ''
local ok, result = pcall(vim.api.nvim_exec2, input, {output = true})
local output = ok and (result.output or '') or ''
local errmsg = vim.v.errmsg
if not ok then errmsg = tostring(result) end
return {output = output, errmsg = errmsg}
"""


class NeovimManager:
    def __init__(self) -> None:
        self._nvim: pynvim.Nvim | None = None
        self._socket_path: str | None = None
        self._lock = asyncio.Lock()
        self._discovery_cache: tuple[float, list[NvimInstance]] | None = None
        self._discovery_cache_ttl = 30.0

    # -- Discovery -----------------------------------------------------------

    async def discover(self) -> list[NvimInstance]:
        if self._discovery_cache is not None:
            ts, cached = self._discovery_cache
            if time.monotonic() - ts < self._discovery_cache_ttl:
                return list(cached)

        candidates = self._all_sockets()

        async def _probe_with_timeout(sock: str) -> NvimInstance | None:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._probe_socket, sock),
                    timeout=5.0,
                )
            except (asyncio.TimeoutError, Exception):
                return None

        results = await asyncio.gather(
            *(_probe_with_timeout(s) for s in candidates)
        )
        instances = [r for r in results if r is not None]
        self._discovery_cache = (time.monotonic(), instances)
        return instances

    # -- Connection ----------------------------------------------------------

    async def connect(
        self,
        socket_path: str | None = None,
        terminal_pid: int | None = None,
        index: int | None = None,
    ) -> str:
        instances = await self.discover()

        if socket_path is not None:
            target = socket_path
        elif terminal_pid is not None:
            target = self._find_socket_for_terminal(terminal_pid, instances)
            if target is None:
                return (
                    f"Error: no Neovim instance found for terminal PID "
                    f"{terminal_pid}."
                )
        elif index is not None:
            if index < 1 or index > len(instances):
                return (
                    f"Error: index {index} out of range. "
                    f"Found {len(instances)} instance(s)."
                )
            target = instances[index - 1].socket_path
        elif len(instances) == 1:
            target = instances[0].socket_path
        elif len(instances) == 0:
            return "Error: no Neovim instances found. Is Neovim running?"
        else:
            return self._format_instance_list(instances)

        async with self._lock:
            try:
                nvim = await asyncio.wait_for(
                    asyncio.to_thread(pynvim.attach, "socket", path=target),
                    timeout=5.0,
                )
            except (asyncio.TimeoutError, OSError) as e:
                return f"Error: could not connect to {target}: {e}"

            self._nvim = nvim
            self._socket_path = target

            try:
                state = await asyncio.to_thread(self._get_state_sync)
                cwd = state.get("cwd", "?")
                current_file = state.get("file", "") or "(none)"
            except Exception:
                cwd = "?"
                current_file = "?"

        return f"Connected to nvim at {target} (cwd: {cwd}, file: {current_file})"

    # -- Send ----------------------------------------------------------------

    async def send(self, input: str, mode: str) -> str:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    return err
            try:
                return await asyncio.to_thread(self._send_sync, input, mode)
            except (OSError, pynvim.NvimError) as e:
                if not self._is_connection_error(e):
                    raise
                await self._reconnect_unlocked()
                return await asyncio.to_thread(self._send_sync, input, mode)

    def _send_sync(self, input: str, mode: str) -> str:
        assert self._nvim is not None

        if mode == "command":
            result = self._nvim.exec_lua(_EXEC_COMMAND_LUA, input)
            output = result.get("output", "") or ""
            errmsg = result.get("errmsg", "") or ""
            parts: list[str] = []
            if output:
                parts.append(output)
            if errmsg:
                parts.append(f"E: {errmsg}")
            return "\n".join(parts) if parts else "(no output)"

        if mode == "eval":
            try:
                result = self._nvim.eval(input)
                return str(result)
            except pynvim.NvimError as e:
                if self._is_connection_error(e):
                    raise
                return f"Error: {e}"

        if mode == "keys":
            self._nvim.input("<Esc>" + input)
            return f"Keys sent: {input}"

        return f"Error: unknown mode {mode!r}. Use 'command', 'eval', or 'keys'."

    # -- State ---------------------------------------------------------------

    async def get_state(self) -> dict:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    raise RuntimeError(err)
            return await asyncio.to_thread(self._get_state_sync)

    def _get_state_sync(self) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(_GET_STATE_LUA)

    # -- Auto-connect (called with lock held) --------------------------------

    async def _auto_connect_unlocked(self) -> str | None:
        """Auto-connect when a single instance exists.

        Returns an error message if connection fails, None on success.
        Must be called with ``self._lock`` held.
        """
        instances = await self.discover()
        if len(instances) == 0:
            return "Error: no Neovim instances found. Is Neovim running?"
        if len(instances) > 1:
            return (
                "Error: multiple Neovim instances found. Connect first:\n"
                + self._format_instance_list(instances)
            )

        target = instances[0].socket_path
        try:
            nvim = await asyncio.wait_for(
                asyncio.to_thread(pynvim.attach, "socket", path=target),
                timeout=5.0,
            )
        except (asyncio.TimeoutError, OSError) as e:
            return f"Error: could not auto-connect to {target}: {e}"

        self._nvim = nvim
        self._socket_path = target
        return None

    # -- Reconnect (called with lock held) -----------------------------------

    async def _reconnect_unlocked(self) -> None:
        """Re-attach to the last-known socket.

        Must be called with ``self._lock`` held.
        """
        if self._nvim is not None:
            try:
                self._nvim.close()
            except Exception:
                pass
        self._nvim = None

        if self._socket_path is None:
            raise RuntimeError("Cannot reconnect: no previous socket path.")

        try:
            self._nvim = await asyncio.wait_for(
                asyncio.to_thread(
                    pynvim.attach, "socket", path=self._socket_path
                ),
                timeout=5.0,
            )
        except (asyncio.TimeoutError, OSError) as e:
            raise RuntimeError(
                f"Reconnect to {self._socket_path} failed: {e}"
            ) from e

    # -- Socket discovery (synchronous) --------------------------------------

    @staticmethod
    def _all_sockets() -> list[str]:
        override = os.environ.get("NVIM_SOCKET_PATH")
        if override:
            try:
                real = os.path.realpath(override)
                st = os.stat(real)
                if stat.S_ISSOCK(st.st_mode):
                    return [real]
            except OSError:
                pass

        search_dirs: list[str] = []

        xdg = os.environ.get("XDG_RUNTIME_DIR")
        if xdg:
            search_dirs.append(xdg)

        try:
            run_user = f"/run/user/{os.getuid()}"
            search_dirs.append(run_user)
        except AttributeError:
            pass  # os.getuid() unavailable on Windows

        tmpdir = os.environ.get("TMPDIR")
        if tmpdir:
            search_dirs.append(tmpdir)
        search_dirs.append("/tmp")

        seen: set[str] = set()
        results: list[str] = []

        for base_dir in search_dirs:
            if not os.path.isdir(base_dir):
                continue
            for root, dirnames, filenames in os.walk(base_dir, followlinks=False):
                rel = os.path.relpath(root, base_dir)
                depth = 0 if rel == "." else rel.count(os.sep) + 1

                all_entries = filenames + list(dirnames)

                if depth >= 4:
                    dirnames.clear()

                for name in all_entries:
                    if not name.startswith("nvim"):
                        continue
                    full = os.path.join(root, name)
                    try:
                        st = os.stat(full)
                    except OSError:
                        continue
                    if not stat.S_ISSOCK(st.st_mode):
                        continue
                    real = os.path.realpath(full)
                    if real not in seen:
                        seen.add(real)
                        results.append(full)

        return results

    @staticmethod
    def _probe_socket(sock: str) -> NvimInstance | None:
        try:
            nvim = pynvim.attach("socket", path=sock)
        except Exception:
            return None
        try:
            pid: int = nvim.eval("getpid()")
            cwd: str = nvim.eval("getcwd()")
            current_file: str = nvim.eval("expand('%:p')")
            return NvimInstance(
                socket_path=sock,
                pid=pid,
                cwd=cwd,
                current_file=current_file,
            )
        except Exception:
            return None
        finally:
            try:
                nvim.close()
            except Exception:
                pass

    @staticmethod
    def _find_socket_for_terminal(
        terminal_pid: int, instances: list[NvimInstance]
    ) -> str | None:
        descendants: set[int] = set()
        to_visit = [terminal_pid]
        while to_visit:
            pid = to_visit.pop()
            if pid in descendants:
                continue
            descendants.add(pid)
            try:
                result = subprocess.run(
                    ["pgrep", "-P", str(pid)],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().splitlines():
                        child = int(line.strip())
                        if child not in descendants:
                            to_visit.append(child)
            except (subprocess.TimeoutExpired, ValueError, OSError):
                pass

        for inst in instances:
            if inst.pid in descendants:
                return inst.socket_path
        return None

    @staticmethod
    def _is_connection_error(e: Exception) -> bool:
        if isinstance(e, (
            BrokenPipeError,
            ConnectionRefusedError,
            ConnectionResetError,
            ConnectionAbortedError,
        )):
            return True
        if isinstance(e, OSError) and not isinstance(e, pynvim.NvimError):
            return True
        if isinstance(e, pynvim.NvimError):
            msg = str(e).lower()
            return any(
                kw in msg
                for kw in ("eof", "broken pipe", "connection", "transport", "closed")
            )
        return False

    @staticmethod
    def _format_instance_list(instances: list[NvimInstance]) -> str:
        lines = ["Multiple Neovim instances found:"]
        for i, inst in enumerate(instances, 1):
            file_display = inst.current_file or "(none)"
            lines.append(
                f"  {i}. {inst.socket_path} "
                f"(cwd: {inst.cwd}, file: {file_display})"
            )
        lines.append(
            "\nUse index=N, socket_path=..., or terminal_pid=... to select one."
        )
        return "\n".join(lines)
