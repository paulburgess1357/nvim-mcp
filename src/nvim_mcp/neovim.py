"""NeovimManager: multi-instance socket discovery, connection, and communication."""

from __future__ import annotations

import asyncio
import os
import socket
import stat
import subprocess
import time
from dataclasses import dataclass
from typing import Any

import msgpack

_CONNECT_TIMEOUT = 5.0


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


_ACTIVE_CONTEXT_LINES = _env_int("NVIM_MCP_ACTIVE_CONTEXT_LINES", 20)
_INACTIVE_CONTEXT_LINES = _env_int("NVIM_MCP_INACTIVE_CONTEXT_LINES", 20)


class NvimError(Exception):
    """Error from Neovim or the msgpack-RPC connection."""


def _format_rpc_error(error: Any) -> str:
    """Extract a human-readable message from a msgpack-RPC error value.

    Neovim sends errors as ``[error_type, error_message]``.
    """
    if isinstance(error, (list, tuple)) and len(error) >= 2:
        return str(error[1])
    return str(error)


class NvimClient:
    """Synchronous msgpack-RPC client for Neovim's Unix socket API.

    Speaks the msgpack-RPC wire protocol (request/response only) directly over
    Neovim's Unix socket.  No plugin-host machinery, no event loop — just the
    three RPC methods this project needs.
    """

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock
        self._unpacker = msgpack.Unpacker(raw=False, strict_map_key=False)
        self._next_msgid = 0

    @classmethod
    def connect(cls, path: str, timeout: float = _CONNECT_TIMEOUT) -> NvimClient:
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


@dataclass
class NvimInstance:
    socket_path: str
    pid: int
    cwd: str
    current_file: str


_GET_STATE_LUA = """\
local active_n = select(1, ...) or 20
local inactive_n = select(2, ...) or active_n
local cur_win = vim.api.nvim_get_current_win()
local cur_mode = vim.fn.mode()

local function get_context(b, from, to, n)
    local total = vim.api.nvim_buf_line_count(b)
    local s = math.max(1, from - n)
    local e = math.min(total, to + n)
    local lines = vim.api.nvim_buf_get_lines(b, s - 1, e, false)
    for i, l in ipairs(lines) do
        lines[i] = (s + i - 1) .. ": " .. l
    end
    return { lines = lines }
end

local wins = {}
for _, w in ipairs(vim.api.nvim_tabpage_list_wins(0)) do
    local b = vim.api.nvim_win_get_buf(w)
    local is_active = (w == cur_win)
    local cursor = vim.api.nvim_win_get_cursor(w)
    local wline, wcol = cursor[1], cursor[2] + 1
    local winfo = {
        file = vim.api.nvim_buf_get_name(b),
        filetype = vim.bo[b].filetype,
        total_lines = vim.api.nvim_buf_line_count(b),
        modified = vim.bo[b].modified,
        buftype = vim.bo[b].buftype,
        active = is_active,
        line = wline,
        col = wcol,
        indent = {
            expandtab = vim.bo[b].expandtab,
            shiftwidth = vim.bo[b].shiftwidth,
            tabstop = vim.bo[b].tabstop,
        },
    }
    local ctx_n = is_active and active_n or inactive_n
    if is_active and (cur_mode == 'v' or cur_mode == 'V' or cur_mode == '\\22') then
        local vpos = vim.fn.getpos('v')
        local cpos = vim.fn.getpos('.')
        local sl, sc = vpos[2], vpos[3]
        local el, ec = cpos[2], cpos[3]
        if sl > el or (sl == el and sc > ec) then
            sl, sc, el, ec = el, ec, sl, sc
        end
        winfo.selection = {
            start_line = sl, start_col = sc,
            end_line = el, end_col = ec,
        }
        if ctx_n > 0 then
            winfo.context = get_context(b, sl, el, ctx_n)
        end
    elseif ctx_n > 0 then
        winfo.context = get_context(b, wline, wline, ctx_n)
    end
    local folds = {}
    vim.api.nvim_win_call(w, function()
        local total = vim.api.nvim_buf_line_count(b)
        local ln = 1
        while ln <= total do
            local fc = vim.fn.foldclosed(ln)
            if fc == ln then
                local fe = vim.fn.foldclosedend(ln)
                folds[#folds + 1] = {fc, fe}
                ln = fe + 1
            else
                ln = ln + 1
            end
        end
    end)
    if #folds > 0 then
        winfo.folds = folds
    end
    local sev_names = {"error", "warning", "info", "hint"}
    local diags = vim.diagnostic.get(b)
    local dcounts = {error = 0, warning = 0, info = 0, hint = 0}
    for _, d in ipairs(diags) do
        local s = sev_names[d.severity] or "hint"
        dcounts[s] = dcounts[s] + 1
    end
    if dcounts.error + dcounts.warning + dcounts.info + dcounts.hint > 0 then
        winfo.diagnostics_summary = dcounts
    end
    local mcp_ns = vim.api.nvim_create_namespace('mcp_highlight')
    local marks = vim.api.nvim_buf_get_extmarks(b, mcp_ns, 0, -1, {details = true})
    if #marks > 0 then
        local highlights = {}
        for _, m in ipairs(marks) do
            local line = m[2] + 1
            local group = m[4].line_hl_group or ""
            local bg = ""
            if group ~= "" then
                local hl = vim.api.nvim_get_hl(0, {name = group})
                if hl.bg then bg = string.format("#%06x", hl.bg) end
            end
            local prev = highlights[#highlights]
            if prev and prev.color == bg and prev.end_line == line - 1 then
                prev.end_line = line
            else
                highlights[#highlights + 1] = {start_line = line, end_line = line, color = bg}
            end
        end
        winfo.mcp_highlights = highlights
    end
    local buf_marks = {}
    for c = string.byte('a'), string.byte('z') do
        local mark = vim.api.nvim_buf_get_mark(b, string.char(c))
        if mark[1] > 0 then
            buf_marks[#buf_marks + 1] = {mark = string.char(c), line = mark[1], col = mark[2] + 1}
        end
    end
    if #buf_marks > 0 then
        winfo.marks = buf_marks
    end
    if is_active then
        table.insert(wins, 1, winfo)
    else
        wins[#wins + 1] = winfo
    end
end
local modified = {}
local buffers = {}
for _, b in ipairs(vim.api.nvim_list_bufs()) do
    if vim.bo[b].buflisted and vim.api.nvim_buf_is_loaded(b) then
        local name = vim.api.nvim_buf_get_name(b)
        if name ~= "" then
            buffers[#buffers + 1] = name
        end
        if vim.bo[b].modified then
            modified[#modified + 1] = name
        end
    end
end
return {
    mode = cur_mode,
    cwd = vim.fn.getcwd(),
    modified_buffers = modified,
    buffers = buffers,
    current_tab = vim.fn.tabpagenr(),
    tab_count = vim.fn.tabpagenr('$'),
    windows = wins,
}
"""

_GET_DIAGNOSTICS_LUA = """\
local file = ...
if file == vim.NIL then file = nil end
local sev_names = {"error", "warning", "info", "hint"}
local bufs = {}
if file then
    local b = vim.fn.bufnr(file)
    if b == -1 then return {error = "Buffer not found: " .. tostring(file)} end
    bufs[1] = b
else
    for _, b in ipairs(vim.api.nvim_list_bufs()) do
        if vim.bo[b].buflisted and vim.api.nvim_buf_is_loaded(b) then
            bufs[#bufs + 1] = b
        end
    end
end
local result = {}
for _, b in ipairs(bufs) do
    local diags = vim.diagnostic.get(b)
    if #diags > 0 then
        local name = vim.api.nvim_buf_get_name(b)
        for _, d in ipairs(diags) do
            result[#result + 1] = {
                file = name,
                line = d.lnum + 1,
                col = d.col + 1,
                severity = sev_names[d.severity] or "hint",
                message = d.message,
                source = d.source or "",
            }
        end
    end
end
return result
"""

_EDIT_BUF_LUA = r"""
local file, old_str, new_str = ...

-- Find or create buffer
local b = vim.fn.bufnr(file)
if b == -1 then
    b = vim.fn.bufadd(file)
    vim.fn.bufload(b)
end
if not vim.api.nvim_buf_is_loaded(b) then
    vim.fn.bufload(b)
end

-- Write mode: no old_str means set entire buffer content
if old_str == nil or old_str == vim.NIL or old_str == "" then
    local new_lines = vim.split(new_str, "\n", {plain = true})
    vim.api.nvim_buf_set_lines(b, 0, -1, false, new_lines)
    return {total_lines = #new_lines}
end

-- Replace mode: find old_str in buffer, replace with new_str
local lines = vim.api.nvim_buf_get_lines(b, 0, -1, false)
local text = table.concat(lines, "\n")

local s, e = string.find(text, old_str, 1, true)
if not s then
    return {error = "old_string not found in buffer"}
end
if string.find(text, old_str, e + 1, true) then
    return {error = "old_string matches multiple locations; add context to make it unique"}
end

-- Compute affected line range (0-indexed)
local before = text:sub(1, s - 1)
local start_line = select(2, before:gsub("\n", ""))
local end_line = start_line + select(2, old_str:gsub("\n", ""))

-- Preserve text on start_line before match and on end_line after match
local prefix = before:match("[^\n]*$") or ""
local suffix = (text:sub(e + 1)):match("^[^\n]*") or ""

local replacement = prefix .. new_str .. suffix
local new_lines = vim.split(replacement, "\n", {plain = true})
vim.api.nvim_buf_set_lines(b, start_line, end_line + 1, false, new_lines)

return {
    start_line = start_line + 1,
    lines_removed = end_line - start_line + 1,
    lines_added = #new_lines,
    total_lines = vim.api.nvim_buf_line_count(b),
}
"""

_READ_BUF_LUA = """\
local file, start_line, end_line = ...
local b = vim.fn.bufnr(file)
if b == -1 then return {error = "Buffer not found: " .. tostring(file)} end
local total = vim.api.nvim_buf_line_count(b)
local s = (type(start_line) == "number") and start_line or 1
local e = (type(end_line) == "number") and end_line or total
if s < 1 then s = 1 end
if e > total then e = total end
local lines = vim.api.nvim_buf_get_lines(b, s - 1, e, false)
for i, l in ipairs(lines) do
    lines[i] = (s + i - 1) .. ": " .. l
end
return {lines = lines, total_lines = total}
"""

_HIGHLIGHT_LUA = r"""
local file, start_line, end_line, color, clear = ...
if type(start_line) == "userdata" then start_line = nil end
if type(end_line) == "userdata" then end_line = nil end
if type(color) == "userdata" then color = nil end
if type(clear) == "userdata" then clear = nil end

local b = vim.fn.bufnr(file)
if b == -1 then
    return {error = "Buffer not found: " .. tostring(file)}
end

local ns = vim.api.nvim_create_namespace('mcp_highlight')

if clear then
    vim.api.nvim_buf_clear_namespace(b, ns, 0, -1)
    return {cleared = true}
end

if not start_line or not end_line then
    return {error = "start_line and end_line are required (pass clear=true to remove highlights)"}
end

local total = vim.api.nvim_buf_line_count(b)
local sl = start_line
local el = end_line
color = color or "Yellow"
if sl < 1 then sl = 1 end
if el > total then el = total end

local group = "McpHl_" .. color:gsub("[^%w]", "_")
vim.api.nvim_set_hl(0, group, {bg = color})

for line = sl, el do
    vim.api.nvim_buf_set_extmark(b, ns, line - 1, 0, {
        line_hl_group = group,
    })
end
return {highlighted = el - sl + 1}
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
        self._nvim: NvimClient | None = None
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

        async def _probe(sock: str) -> NvimInstance | None:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._probe_socket, sock),
                    timeout=_CONNECT_TIMEOUT,
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
                self._nvim = await self._connect_to(target)
                self._socket_path = target
            except (asyncio.TimeoutError, OSError) as e:
                return f"Error: could not connect to {target}: {e}"

            try:
                state = await asyncio.to_thread(self._get_state_sync)
                cwd = state.get("cwd", "?")
                wins = state.get("windows", [])
                current_file = wins[0].get("file", "") if wins else ""
                current_file = current_file or "(none)"
            except Exception:
                cwd = "?"
                current_file = "?"

        return f"Connected to nvim at {target} (cwd: {cwd}, file: {current_file})"

    # -- Send ----------------------------------------------------------------

    async def send_command(self, command: str | list[str]) -> str | list[str]:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    return err
            if isinstance(command, str):
                return await self._retry_on_disconnect(
                    self._run_command_sync, command
                )
            return await self._retry_on_disconnect(
                self._run_commands_sync, command
            )

    async def send_keys(self, keys: str) -> str:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    return err
            return await self._retry_on_disconnect(self._run_keys_sync, keys)

    def _run_command_sync(self, command: str) -> str:
        assert self._nvim is not None
        result = self._nvim.exec_lua(_EXEC_COMMAND_LUA, command)
        output = result.get("output", "") or ""
        errmsg = result.get("errmsg", "") or ""
        parts: list[str] = []
        if output:
            parts.append(output)
        if errmsg:
            parts.append(f"E: {errmsg}")
        return "\n".join(parts) if parts else "(no output)"

    def _run_commands_sync(self, commands: list[str]) -> list[str]:
        return [self._run_command_sync(cmd) for cmd in commands]

    def _run_keys_sync(self, keys: str) -> str:
        assert self._nvim is not None
        self._nvim.input("<Esc>" + keys)
        return ""

    # -- State ---------------------------------------------------------------

    async def get_state(self) -> dict:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    raise RuntimeError(err)
            return await self._retry_on_disconnect(self._get_state_sync)

    def _get_state_sync(self) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(
            _GET_STATE_LUA, _ACTIVE_CONTEXT_LINES, _INACTIVE_CONTEXT_LINES
        )

    # -- Diagnostics ---------------------------------------------------------

    async def get_diagnostics(self, file: str | None = None) -> list:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    raise RuntimeError(err)
            return await self._retry_on_disconnect(
                self._get_diagnostics_sync, file
            )

    def _get_diagnostics_sync(self, file: str | None) -> list:
        assert self._nvim is not None
        return self._nvim.exec_lua(_GET_DIAGNOSTICS_LUA, file)

    # -- Buffer edit ---------------------------------------------------------

    async def edit_buffer(
        self,
        file: str,
        new_string: str,
        old_string: str | None = None,
    ) -> dict:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    raise RuntimeError(err)
            return await self._retry_on_disconnect(
                self._edit_buf_sync, file, old_string, new_string
            )

    def _edit_buf_sync(
        self,
        file: str,
        old_string: str | None,
        new_string: str,
    ) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(_EDIT_BUF_LUA, file, old_string, new_string)

    # -- Buffer read ---------------------------------------------------------

    async def read_buffer(
        self,
        file: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> dict:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    raise RuntimeError(err)
            return await self._retry_on_disconnect(
                self._read_buf_sync, file, start_line, end_line
            )

    def _read_buf_sync(
        self,
        file: str,
        start_line: int | None,
        end_line: int | None,
    ) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(_READ_BUF_LUA, file, start_line, end_line)

    # -- Buffer highlight ----------------------------------------------------

    async def highlight_buffer(
        self,
        file: str,
        start_line: int,
        end_line: int,
        color: str = "Yellow",
    ) -> dict:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    raise RuntimeError(err)
            return await self._retry_on_disconnect(
                self._highlight_buf_sync, file, start_line, end_line, color,
            )

    def _highlight_buf_sync(
        self,
        file: str,
        start_line: int,
        end_line: int,
        color: str,
    ) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(
            _HIGHLIGHT_LUA, file, start_line, end_line, color, False
        )

    async def clear_highlights(self, file: str) -> dict:
        async with self._lock:
            if self._nvim is None:
                err = await self._auto_connect_unlocked()
                if err is not None:
                    raise RuntimeError(err)
            return await self._retry_on_disconnect(
                self._clear_highlights_sync, file,
            )

    def _clear_highlights_sync(self, file: str) -> dict:
        assert self._nvim is not None
        return self._nvim.exec_lua(
            _HIGHLIGHT_LUA, file, None, None, None, True
        )

    # -- Connection helpers (called with lock held) --------------------------

    async def _connect_to(self, path: str) -> NvimClient:
        return await asyncio.wait_for(
            asyncio.to_thread(NvimClient.connect, path),
            timeout=_CONNECT_TIMEOUT,
        )

    async def _auto_connect_unlocked(self) -> str | None:
        """Auto-connect when a single instance exists.

        Returns an error message on failure, None on success.
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
            self._nvim = await self._connect_to(target)
            self._socket_path = target
        except (asyncio.TimeoutError, OSError) as e:
            return f"Error: could not auto-connect to {target}: {e}"
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
            raise RuntimeError(
                f"Reconnect to {self._socket_path} failed: {e}"
            ) from e

    async def _retry_on_disconnect(self, fn, *args):
        """Run *fn* in a thread; on connection error, reconnect and retry once."""
        try:
            return await asyncio.to_thread(fn, *args)
        except (OSError, NvimError) as e:
            if not self._is_connection_error(e):
                raise
            await self._reconnect_unlocked()
            return await asyncio.to_thread(fn, *args)

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
            nvim = NvimClient.connect(sock)
        except Exception:
            return None
        try:
            info = nvim.exec_lua(
                "return {pid=vim.fn.getpid(), cwd=vim.fn.getcwd(),"
                " file=vim.fn.expand('%:p')}",
            )
            return NvimInstance(
                socket_path=sock,
                pid=info["pid"],
                cwd=info["cwd"],
                current_file=info["file"],
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
        if isinstance(e, OSError):
            return True
        if isinstance(e, NvimError):
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
