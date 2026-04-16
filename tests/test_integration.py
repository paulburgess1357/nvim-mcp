"""Integration tests for NvimClient against a real headless Neovim instance.

Skipped automatically when nvim is not installed.
"""

import os
import shutil
import socket
import subprocess
import tempfile
import time

import pytest

from nvim_mcp.client import NvimClient
from nvim_mcp.lua import EDIT_BUF, EXEC_COMMAND, GET_DIAGNOSTICS, GET_STATE, HIGHLIGHT, READ_BUF
from nvim_mcp.types import NvimError

pytestmark = pytest.mark.skipif(
    not shutil.which("nvim"), reason="nvim not installed"
)


@pytest.fixture()
def nvim_socket():
    """Start a headless Neovim and yield its socket path."""
    tmpdir = tempfile.mkdtemp(prefix="nvim_test_")
    sock_path = os.path.join(tmpdir, "nvim.sock")

    proc = subprocess.Popen(
        ["nvim", "--headless", "--clean", "--listen", sock_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if os.path.exists(sock_path):
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(1.0)
                s.connect(sock_path)
                s.close()
                break
            except OSError:
                pass
        time.sleep(0.05)
    else:
        proc.kill()
        proc.wait()
        pytest.fail("Neovim did not start within 5 seconds")

    yield sock_path

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    shutil.rmtree(tmpdir, ignore_errors=True)


class TestNvimClientRPC:
    """Verify the msgpack-RPC wire protocol against a real Neovim."""

    def test_eval_arithmetic(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            assert client.eval("1 + 1") == 2
        finally:
            client.close()

    def test_eval_string(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            assert client.eval("'hello'") == "hello"
        finally:
            client.close()

    def test_eval_getpid(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            pid = client.eval("getpid()")
            assert isinstance(pid, int)
            assert pid > 0
        finally:
            client.close()

    def test_eval_getcwd(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            cwd = client.eval("getcwd()")
            assert isinstance(cwd, str)
            assert len(cwd) > 0
        finally:
            client.close()

    def test_eval_error_raises(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            with pytest.raises(NvimError):
                client.eval("invalid!!!")
        finally:
            client.close()

    def test_exec_lua_return_scalar(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            assert client.exec_lua("return 42") == 42
        finally:
            client.close()

    def test_exec_lua_with_args(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            assert client.exec_lua("local x = ... return x * 2", 21) == 42
        finally:
            client.close()

    def test_exec_lua_return_table(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            result = client.exec_lua("return {a = 1, b = 'two'}")
            assert result == {"a": 1, "b": "two"}
        finally:
            client.close()

    def test_exec_lua_state_snapshot(self, nvim_socket):
        """Exercise the same Lua pattern used by _GET_STATE_LUA."""
        client = NvimClient.connect(nvim_socket)
        try:
            state = client.exec_lua(
                "return {"
                "  file = vim.fn.expand('%:p'),"
                "  line = vim.fn.line('.'),"
                "  col = vim.fn.col('.'),"
                "  mode = vim.fn.mode(),"
                "  cwd = vim.fn.getcwd(),"
                "}"
            )
            assert isinstance(state, dict)
            assert isinstance(state["line"], int)
            assert isinstance(state["col"], int)
            assert isinstance(state["cwd"], str)
        finally:
            client.close()

    def test_input_keys(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        try:
            written = client.input("ihello<Esc>")
            assert isinstance(written, int)
            assert written > 0
        finally:
            client.close()

    def test_sequential_requests(self, nvim_socket):
        """Verify the unpacker handles many sequential request/response cycles."""
        client = NvimClient.connect(nvim_socket)
        try:
            for i in range(20):
                assert client.eval(f"{i} + 1") == i + 1
        finally:
            client.close()


class TestBufEdit:
    """Test nvim_buf_edit Lua against a real Neovim with various content."""

    _buf_counter = 0

    @pytest.fixture()
    def client(self, nvim_socket):
        c = NvimClient.connect(nvim_socket)
        yield c
        c.close()

    def _unique_path(self):
        TestBufEdit._buf_counter += 1
        return f"/tmp/nvim_test_buf_{os.getpid()}_{TestBufEdit._buf_counter}.txt"

    def _setup_buffer(self, client, path, content):
        """Create a buffer with known content, no disk interaction."""
        client.exec_lua(
            "local f, c = ...\n"
            "vim.cmd('noswapfile edit ' .. vim.fn.fnameescape(f))\n"
            "local b = vim.fn.bufnr(f)\n"
            "vim.api.nvim_buf_set_lines(b, 0, -1, false, vim.split(c, '\\n', {plain=true}))",
            path, content,
        )

    def _read_buffer(self, client, path):
        """Read full buffer content as a string."""
        result = client.exec_lua(READ_BUF, path, None, None)
        lines = result["lines"]
        return "\n".join(line.split(": ", 1)[1] for line in lines)

    def test_basic_replace(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "hello world")
        result = client.exec_lua(EDIT_BUF, p, "hello", "goodbye")
        assert "error" not in result
        assert self._read_buffer(client, p) == "goodbye world"

    def test_double_quotes(self, client):
        p = self._unique_path()
        content = '#include "stdio.h"\n#include "stdlib.h"'
        self._setup_buffer(client, p, content)
        result = client.exec_lua(
            EDIT_BUF, p,
            '#include "stdio.h"',
            '#include "stdio.h"\n#include "math.h"',
        )
        assert "error" not in result
        assert '#include "math.h"' in self._read_buffer(client, p)

    def test_single_quotes(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "msg = 'hello'")
        result = client.exec_lua(EDIT_BUF, p, "'hello'", "'goodbye'")
        assert "error" not in result
        assert self._read_buffer(client, p) == "msg = 'goodbye'"

    def test_backslashes(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "path = C:\\Users\\test")
        result = client.exec_lua(
            EDIT_BUF, p, "C:\\Users\\test", "C:\\Users\\new",
        )
        assert "error" not in result
        assert "C:\\Users\\new" in self._read_buffer(client, p)

    def test_tab_characters(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "no\ttabs\there")
        result = client.exec_lua(EDIT_BUF, p, "\ttabs\t", "\tspaces\t")
        assert "error" not in result
        assert "no\tspaces\there" == self._read_buffer(client, p)

    def test_unicode(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "hello 世界 🌍")
        result = client.exec_lua(EDIT_BUF, p, "世界 🌍", "world 🌎")
        assert "error" not in result
        assert self._read_buffer(client, p) == "hello world 🌎"

    def test_multiline_replace(self, client):
        p = self._unique_path()
        content = "line 1\nline 2\nline 3\nline 4"
        self._setup_buffer(client, p, content)
        result = client.exec_lua(
            EDIT_BUF, p,
            "line 2\nline 3", "replaced 2\nreplaced 3\nextra line",
        )
        assert "error" not in result
        assert result["lines_removed"] == 2
        assert result["lines_added"] == 3
        buf = self._read_buffer(client, p)
        assert "replaced 2\nreplaced 3\nextra line" in buf
        assert "line 1" in buf
        assert "line 4" in buf

    def test_delete_text(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "keep this remove this keep too")
        result = client.exec_lua(EDIT_BUF, p, " remove this", "")
        assert "error" not in result
        assert self._read_buffer(client, p) == "keep this keep too"

    def test_lua_pattern_chars(self, client):
        p = self._unique_path()
        content = "match: 100% (done) [ok]"
        self._setup_buffer(client, p, content)
        result = client.exec_lua(
            EDIT_BUF, p,
            "100% (done) [ok]", "50% (pending) [wait]",
        )
        assert "error" not in result
        assert "50% (pending) [wait]" in self._read_buffer(client, p)

    def test_curly_braces(self, client):
        p = self._unique_path()
        content = "void foo() {\n    return;\n}"
        self._setup_buffer(client, p, content)
        result = client.exec_lua(
            EDIT_BUF, p,
            "{\n    return;\n}", "{\n    int x = 0;\n    return;\n}",
        )
        assert "error" not in result
        assert "int x = 0;" in self._read_buffer(client, p)

    def test_write_mode_full_content(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "old content")
        result = client.exec_lua(EDIT_BUF, p, None, "brand new\ncontent")
        assert "error" not in result
        assert result["total_lines"] == 2
        assert self._read_buffer(client, p) == "brand new\ncontent"

    def test_write_mode_empty_old_string(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "old content")
        result = client.exec_lua(EDIT_BUF, p, "", "replaced all")
        assert "error" not in result
        assert self._read_buffer(client, p) == "replaced all"

    def test_create_new_buffer(self, client):
        p = self._unique_path()
        result = client.exec_lua(EDIT_BUF, p, None, "fresh content")
        assert "error" not in result
        assert result["total_lines"] == 1
        assert self._read_buffer(client, p) == "fresh content"

    def test_not_found_error(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "some content")
        result = client.exec_lua(EDIT_BUF, p, "nonexistent text", "replacement")
        assert "error" in result
        assert "not found" in result["error"]

    def test_multiple_matches_error(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "aaa bbb aaa")
        result = client.exec_lua(EDIT_BUF, p, "aaa", "ccc")
        assert "error" in result
        assert "multiple" in result["error"]

    def test_append_to_end(self, client):
        p = self._unique_path()
        content = "line 1\nline 2\nline 3"
        self._setup_buffer(client, p, content)
        result = client.exec_lua(
            EDIT_BUF, p, "line 3", "line 3\nline 4\nline 5",
        )
        assert "error" not in result
        buf = self._read_buffer(client, p)
        assert buf.endswith("line 4\nline 5")

    def test_insert_at_beginning(self, client):
        p = self._unique_path()
        content = "first line\nsecond line"
        self._setup_buffer(client, p, content)
        result = client.exec_lua(
            EDIT_BUF, p, "first line", "zeroth line\nfirst line",
        )
        assert "error" not in result
        buf = self._read_buffer(client, p)
        assert buf.startswith("zeroth line\nfirst line")

    def test_logger_style_content(self, client):
        p = self._unique_path()
        content = (
            '#include "utils/Logger.hpp"\n'
            "\n"
            'void foo() {\n'
            '    Logger::getInstance().info("Shape added to renderer");\n'
            "}"
        )
        self._setup_buffer(client, p, content)
        result = client.exec_lua(
            EDIT_BUF, p,
            '    Logger::getInstance().info("Shape added to renderer");',
            '    Logger::getInstance().info("Shape added to renderer");\n'
            '    Logger::getInstance().debug("Count: " + std::to_string(count));',
        )
        assert "error" not in result
        buf = self._read_buffer(client, p)
        assert 'Logger::getInstance().debug("Count: "' in buf
        assert '#include "utils/Logger.hpp"' in buf


class TestHighlight:
    """Test nvim_highlight Lua against a real Neovim."""

    _buf_counter = 0

    @pytest.fixture()
    def client(self, nvim_socket):
        c = NvimClient.connect(nvim_socket)
        yield c
        c.close()

    def _unique_path(self):
        TestHighlight._buf_counter += 1
        return f"/tmp/nvim_test_hl_{os.getpid()}_{TestHighlight._buf_counter}.txt"

    def _setup_buffer(self, client, path, content):
        client.exec_lua(
            "local f, c = ...\n"
            "vim.cmd('noswapfile edit ' .. vim.fn.fnameescape(f))\n"
            "local b = vim.fn.bufnr(f)\n"
            "vim.api.nvim_buf_set_lines(b, 0, -1, false, vim.split(c, '\\n', {plain=true}))",
            path, content,
        )

    def test_highlight_range(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "line1\nline2\nline3")
        result = client.exec_lua(HIGHLIGHT, p, 1, 2, "Yellow", None)
        assert "error" not in result
        assert result["highlighted"] == 2

    def test_highlight_single_line(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "a\nb\nc")
        result = client.exec_lua(HIGHLIGHT, p, 2, 2, "DarkGreen", None)
        assert "error" not in result
        assert result["highlighted"] == 1

    def test_highlight_hex_color(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "a\nb\nc\nd\ne")
        result = client.exec_lua(HIGHLIGHT, p, 3, 4, "#ff6666", None)
        assert "error" not in result
        assert result["highlighted"] == 2

    def test_clear_highlights(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "a\nb\nc")
        client.exec_lua(HIGHLIGHT, p, 1, 3, "Yellow", None)
        result = client.exec_lua(HIGHLIGHT, p, None, None, None, True)
        assert result.get("cleared") is True

    def test_invalid_buffer_returns_error(self, client):
        result = client.exec_lua(
            HIGHLIGHT,
            "/tmp/nvim_test_no_such_buffer_ever.txt",
            1, 1, "Red", None,
        )
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_missing_lines_returns_error(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "content")
        result = client.exec_lua(HIGHLIGHT, p, None, None, None, None)
        assert "error" in result
        result2 = client.exec_lua(HIGHLIGHT, p, 1, None, None, None)
        assert "error" in result2

    def test_highlight_does_not_modify_content(self, client):
        p = self._unique_path()
        self._setup_buffer(client, p, "hello\nworld")
        client.exec_lua(HIGHLIGHT, p, 1, 2, "#334455", None)
        buf = client.exec_lua(READ_BUF, p, None, None)
        lines = [l.split(": ", 1)[1] for l in buf["lines"]]
        assert lines == ["hello", "world"]


class TestGetState:
    """Verify the composed GET_STATE Lua script runs against a real Neovim."""

    @pytest.fixture()
    def client(self, nvim_socket):
        c = NvimClient.connect(nvim_socket)
        yield c
        c.close()

    def test_returns_expected_structure(self, client):
        state = client.exec_lua(GET_STATE, 20, 5)
        assert isinstance(state, dict)
        assert isinstance(state["mode"], str)
        assert isinstance(state["cwd"], str)
        assert isinstance(state["windows"], list)
        assert isinstance(state["buffers"], list)
        assert isinstance(state["current_tab"], int)
        assert isinstance(state["tab_count"], int)
        assert "modified_buffers" in state

    def test_active_window_has_expected_fields(self, client):
        state = client.exec_lua(GET_STATE, 20, 5)
        wins = state["windows"]
        assert len(wins) >= 1
        active = wins[0]
        assert active["role"] == "active"
        assert isinstance(active["line"], int)
        assert isinstance(active["col"], int)
        assert isinstance(active["total_lines"], int)
        assert isinstance(active["filetype"], str)
        assert isinstance(active["modified"], bool)
        assert "indent" in active
        assert "context" in active

    def test_mode_is_normal_in_headless(self, client):
        state = client.exec_lua(GET_STATE, 20, 5)
        assert state["mode"] == "normal"

    def test_zero_context_lines_omits_context(self, client):
        state = client.exec_lua(GET_STATE, 0, 0)
        active = state["windows"][0]
        assert "context" not in active


class TestGetDiagnostics:
    """Verify the composed GET_DIAGNOSTICS Lua script runs against a real Neovim."""

    @pytest.fixture()
    def client(self, nvim_socket):
        c = NvimClient.connect(nvim_socket)
        yield c
        c.close()

    def test_returns_list_with_no_diagnostics(self, client):
        result = client.exec_lua(GET_DIAGNOSTICS, None)
        assert isinstance(result, list)

    def test_unknown_file_returns_error(self, client):
        result = client.exec_lua(GET_DIAGNOSTICS, "/tmp/nvim_test_no_such_file_ever.py")
        assert isinstance(result, dict)
        assert "error" in result
        assert "not found" in result["error"].lower()


class TestExecCommand:
    """Verify the EXEC_COMMAND Lua script runs against a real Neovim."""

    @pytest.fixture()
    def client(self, nvim_socket):
        c = NvimClient.connect(nvim_socket)
        yield c
        c.close()

    def test_echo_returns_output(self, client):
        result = client.exec_lua(EXEC_COMMAND, "echo 'hello'")
        assert result["output"] == "hello"
        assert result["errmsg"] == ""

    def test_invalid_command_returns_error(self, client):
        result = client.exec_lua(EXEC_COMMAND, "nonexistent_command_xyz")
        assert result["errmsg"] != ""

    def test_silent_command_returns_empty_output(self, client):
        result = client.exec_lua(EXEC_COMMAND, "let g:_mcp_test = 1")
        assert result["errmsg"] == ""


class TestNvimClientEdgeCases:

    def test_connect_bad_path_raises(self):
        with pytest.raises(OSError):
            NvimClient.connect("/tmp/nonexistent_nvim_socket_xyz_test")

    def test_close_is_idempotent(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        client.close()
        client.close()
