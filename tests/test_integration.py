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

from nvim_mcp.neovim import NvimClient, NvimError

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


class TestNvimClientEdgeCases:

    def test_connect_bad_path_raises(self):
        with pytest.raises(OSError):
            NvimClient.connect("/tmp/nonexistent_nvim_socket_xyz_test")

    def test_close_is_idempotent(self, nvim_socket):
        client = NvimClient.connect(nvim_socket)
        client.close()
        client.close()
