"""Comprehensive unit tests for nvim_mcp — no real Neovim required.

Covers: types (_env_int, _format_rpc_error, NvimError, NvimInstance),
client (NvimClient), discovery (socket scanning, probing, PID matching),
manager (NeovimManager: connection, commands, state, diagnostics,
buffer operations, highlights, reconnection, retry logic).
"""

from __future__ import annotations

import asyncio
import os
import socket
import stat
from unittest.mock import MagicMock, patch

import msgpack
import pytest

from nvim_mcp.client import NvimClient
from nvim_mcp.discovery import find_all_sockets, find_socket_for_terminal, probe_socket
from nvim_mcp.manager import NeovimManager, _format_instance_dict, _is_connection_error
from nvim_mcp.types import NvimError, NvimInstance, _env_int, _format_rpc_error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_instance(idx: int = 0) -> NvimInstance:
    return NvimInstance(
        socket_path=f"/tmp/nvim.{idx}/0",
        pid=1000 + idx,
        cwd=f"/home/user/project{idx}",
        current_file=f"file{idx}.py",
    )


def _make_mock_nvim() -> MagicMock:
    mock = MagicMock(spec=NvimClient)
    mock.exec_lua.return_value = {"output": "", "errmsg": ""}
    return mock


def _connected_manager() -> tuple[NeovimManager, MagicMock]:
    mgr = NeovimManager()
    mock_nvim = _make_mock_nvim()
    mgr._nvim = mock_nvim
    mgr._socket_path = "/tmp/nvim.0/0"
    return mgr, mock_nvim


def _patch_discovery(instances: list[NvimInstance]):
    """Context manager that patches socket discovery to return *instances*."""
    return (
        patch(
            "nvim_mcp.manager.find_all_sockets",
            return_value=[i.socket_path for i in instances],
        ),
        patch(
            "nvim_mcp.manager.probe_socket",
            side_effect=instances,
        ),
    )


# ===================================================================
# _env_int
# ===================================================================

class TestEnvInt:
    def test_returns_default_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _env_int("NVIM_MCP_TEST_VAR", 42) == 42

    def test_returns_parsed_value(self):
        with patch.dict(os.environ, {"NVIM_MCP_TEST_VAR": "10"}):
            assert _env_int("NVIM_MCP_TEST_VAR", 42) == 10

    def test_returns_default_on_non_integer(self):
        with patch.dict(os.environ, {"NVIM_MCP_TEST_VAR": "abc"}):
            assert _env_int("NVIM_MCP_TEST_VAR", 42) == 42

    def test_returns_zero(self):
        with patch.dict(os.environ, {"NVIM_MCP_TEST_VAR": "0"}):
            assert _env_int("NVIM_MCP_TEST_VAR", 42) == 0

    def test_returns_negative(self):
        with patch.dict(os.environ, {"NVIM_MCP_TEST_VAR": "-5"}):
            assert _env_int("NVIM_MCP_TEST_VAR", 42) == -5

    def test_returns_default_on_empty_string(self):
        with patch.dict(os.environ, {"NVIM_MCP_TEST_VAR": ""}):
            assert _env_int("NVIM_MCP_TEST_VAR", 42) == 42

    def test_returns_default_on_whitespace(self):
        with patch.dict(os.environ, {"NVIM_MCP_TEST_VAR": " "}):
            assert _env_int("NVIM_MCP_TEST_VAR", 42) == 42

    def test_returns_default_on_float_string(self):
        with patch.dict(os.environ, {"NVIM_MCP_TEST_VAR": "3.14"}):
            assert _env_int("NVIM_MCP_TEST_VAR", 42) == 42


# ===================================================================
# _format_rpc_error
# ===================================================================

class TestFormatRpcError:
    def test_list_error_extracts_message(self):
        assert _format_rpc_error([1, "Something went wrong"]) == "Something went wrong"

    def test_tuple_error_extracts_message(self):
        assert _format_rpc_error((1, "Bad call")) == "Bad call"

    def test_plain_string(self):
        assert _format_rpc_error("raw error") == "raw error"

    def test_plain_int(self):
        assert _format_rpc_error(42) == "42"

    def test_short_list_falls_through(self):
        assert _format_rpc_error([1]) == "[1]"

    def test_empty_list_falls_through(self):
        assert _format_rpc_error([]) == "[]"

    def test_list_with_extra_elements(self):
        assert _format_rpc_error([1, "main error", "extra"]) == "main error"

    def test_none_value(self):
        assert _format_rpc_error(None) == "None"

    def test_nested_list(self):
        assert _format_rpc_error([0, [1, "nested"]]) == "[1, 'nested']"


# ===================================================================
# NvimError
# ===================================================================

class TestNvimError:
    def test_is_exception(self):
        assert issubclass(NvimError, Exception)

    def test_message(self):
        err = NvimError("test error")
        assert str(err) == "test error"


# ===================================================================
# NvimClient — unit tests with mocked socket
# ===================================================================

class TestNvimClientInit:
    def test_initial_state(self):
        sock = MagicMock(spec=socket.socket)
        client = NvimClient(sock)
        assert client._next_msgid == 0
        assert client._sock is sock


class TestNvimClientConnect:
    def test_connect_creates_unix_socket(self):
        mock_sock = MagicMock(spec=socket.socket)
        with patch("nvim_mcp.client.socket.socket", return_value=mock_sock):
            client = NvimClient.connect("/tmp/test.sock", timeout=3.0)

        mock_sock.settimeout.assert_called_once_with(3.0)
        mock_sock.connect.assert_called_once_with("/tmp/test.sock")
        assert client._sock is mock_sock

    def test_connect_uses_default_timeout(self):
        mock_sock = MagicMock(spec=socket.socket)
        with patch("nvim_mcp.client.socket.socket", return_value=mock_sock):
            NvimClient.connect("/tmp/test.sock")
        from nvim_mcp.types import CONNECT_TIMEOUT
        mock_sock.settimeout.assert_called_once_with(CONNECT_TIMEOUT)

    def test_connect_closes_socket_on_failure(self):
        mock_sock = MagicMock(spec=socket.socket)
        mock_sock.connect.side_effect = ConnectionRefusedError("refused")
        with patch("nvim_mcp.client.socket.socket", return_value=mock_sock):
            with pytest.raises(ConnectionRefusedError):
                NvimClient.connect("/tmp/test.sock")
        mock_sock.close.assert_called_once()


class TestNvimClientRequest:
    def _make_client_with_response(self, msgid: int, error, result):
        """Create a client whose socket returns a single packed RPC response."""
        response = msgpack.packb([1, msgid, error, result])
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = response
        return NvimClient(sock)

    def test_request_increments_msgid(self):
        client = self._make_client_with_response(1, None, "ok")
        result = client.request("nvim_eval", "1+1")
        assert result == "ok"
        assert client._next_msgid == 1

        client._sock.recv.return_value = msgpack.packb([1, 2, None, "ok2"])
        result2 = client.request("nvim_eval", "2+2")
        assert result2 == "ok2"
        assert client._next_msgid == 2

    def test_request_sends_packed_message(self):
        client = self._make_client_with_response(1, None, "result")
        client.request("nvim_eval", "test_expr")

        sent_data = client._sock.sendall.call_args[0][0]
        unpacked = msgpack.unpackb(sent_data)
        assert unpacked[0] == 0  # request type
        assert unpacked[1] == 1  # msgid
        assert unpacked[2] == "nvim_eval"
        assert unpacked[3] == ["test_expr"]

    def test_request_raises_on_rpc_error(self):
        client = self._make_client_with_response(1, [0, "E15: Invalid expression"], None)
        with pytest.raises(NvimError, match="E15"):
            client.request("nvim_eval", "bad!!!")

    def test_request_raises_on_connection_closed(self):
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = b""
        client = NvimClient(sock)
        with pytest.raises(NvimError, match="Connection closed"):
            client.request("nvim_eval", "1")

    def test_skips_non_response_messages(self):
        notification = msgpack.packb([2, "event", []])
        response = msgpack.packb([1, 1, None, "final"])
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [notification, response]
        client = NvimClient(sock)
        assert client.request("nvim_eval", "1") == "final"

    def test_skips_wrong_msgid(self):
        wrong_id = msgpack.packb([1, 999, None, "wrong"])
        right_id = msgpack.packb([1, 1, None, "right"])
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [wrong_id, right_id]
        client = NvimClient(sock)
        assert client.request("nvim_eval", "1") == "right"

    def test_skips_malformed_messages(self):
        malformed = msgpack.packb([1, 2])  # too short
        good = msgpack.packb([1, 1, None, "good"])
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [malformed, good]
        client = NvimClient(sock)
        assert client.request("nvim_eval", "1") == "good"

    def test_response_split_across_recv_calls(self):
        full = msgpack.packb([1, 1, None, "split_result"])
        mid = len(full) // 2
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [full[:mid], full[mid:]]
        client = NvimClient(sock)
        assert client.request("nvim_eval", "1") == "split_result"

    def test_multiple_messages_in_single_recv(self):
        notification = msgpack.packb([2, "redraw", []])
        response = msgpack.packb([1, 1, None, "batched"])
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = notification + response
        client = NvimClient(sock)
        assert client.request("nvim_eval", "1") == "batched"

    def test_request_with_no_args(self):
        response = msgpack.packb([1, 1, None, "ok"])
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = response
        client = NvimClient(sock)
        client.request("nvim_get_current_line")
        sent = msgpack.unpackb(sock.sendall.call_args[0][0])
        assert sent[3] == []

    def test_request_with_multiple_args(self):
        response = msgpack.packb([1, 1, None, "ok"])
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = response
        client = NvimClient(sock)
        client.request("nvim_buf_set_lines", 0, 0, -1, False, ["a", "b"])
        sent = msgpack.unpackb(sock.sendall.call_args[0][0])
        assert sent[3] == [0, 0, -1, False, ["a", "b"]]

    def test_skips_non_list_unpacked_values(self):
        scalar = msgpack.packb("just a string")
        response = msgpack.packb([1, 1, None, "ok"])
        sock = MagicMock(spec=socket.socket)
        sock.recv.side_effect = [scalar, response]
        client = NvimClient(sock)
        assert client.request("nvim_eval", "1") == "ok"


class TestNvimClientConvenienceMethods:
    def test_exec_lua_delegates(self):
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = msgpack.packb([1, 1, None, 42])
        client = NvimClient(sock)
        assert client.exec_lua("return 42") == 42
        sent = msgpack.unpackb(sock.sendall.call_args[0][0])
        assert sent[2] == "nvim_exec_lua"
        assert sent[3] == ["return 42", []]

    def test_exec_lua_with_args(self):
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = msgpack.packb([1, 1, None, 84])
        client = NvimClient(sock)
        assert client.exec_lua("return ... * 2", 42) == 84
        sent = msgpack.unpackb(sock.sendall.call_args[0][0])
        assert sent[3] == ["return ... * 2", [42]]

    def test_eval_delegates(self):
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = msgpack.packb([1, 1, None, 2])
        client = NvimClient(sock)
        assert client.eval("1+1") == 2
        sent = msgpack.unpackb(sock.sendall.call_args[0][0])
        assert sent[2] == "nvim_eval"

    def test_input_delegates(self):
        sock = MagicMock(spec=socket.socket)
        sock.recv.return_value = msgpack.packb([1, 1, None, 5])
        client = NvimClient(sock)
        assert client.input("ihello") == 5
        sent = msgpack.unpackb(sock.sendall.call_args[0][0])
        assert sent[2] == "nvim_input"


class TestNvimClientClose:
    def test_close_calls_socket_close(self):
        sock = MagicMock(spec=socket.socket)
        client = NvimClient(sock)
        client.close()
        sock.close.assert_called_once()

    def test_close_swallows_os_error(self):
        sock = MagicMock(spec=socket.socket)
        sock.close.side_effect = OSError("already closed")
        client = NvimClient(sock)
        client.close()  # should not raise


# ===================================================================
# NvimInstance
# ===================================================================

class TestNvimInstance:
    def test_dataclass_fields(self):
        inst = NvimInstance(
            socket_path="/tmp/nvim.0/0",
            pid=1234,
            cwd="/home/user",
            current_file="main.py",
        )
        assert inst.socket_path == "/tmp/nvim.0/0"
        assert inst.pid == 1234
        assert inst.cwd == "/home/user"
        assert inst.current_file == "main.py"


# ===================================================================
# NeovimManager — Discovery
# ===================================================================

class TestDiscover:
    def test_discover_returns_instances(self):
        mgr = NeovimManager()
        instances = [_make_instance(0), _make_instance(1)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            result = asyncio.run(mgr.discover())
        assert len(result) == 2
        assert result[0].pid == 1000
        assert result[1].pid == 1001

    def test_discover_filters_failed_probes(self):
        mgr = NeovimManager()
        with (
            patch("nvim_mcp.manager.find_all_sockets", return_value=["/sock1", "/sock2"]),
            patch("nvim_mcp.manager.probe_socket", side_effect=[_make_instance(0), None]),
        ):
            result = asyncio.run(mgr.discover())
        assert len(result) == 1

    def test_discover_caches_results(self):
        mgr = NeovimManager()
        instances = [_make_instance(0)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            result1 = asyncio.run(mgr.discover())
            result2 = asyncio.run(mgr.discover())
        assert result1 == result2

    def test_discover_cache_expires(self):
        mgr = NeovimManager()
        mgr._discovery_cache_ttl = 0.0
        instances_v1 = [_make_instance(0)]
        instances_v2 = [_make_instance(0), _make_instance(1)]

        p1a, p1b = _patch_discovery(instances_v1)
        with p1a, p1b:
            r1 = asyncio.run(mgr.discover())
        assert len(r1) == 1

        mgr._discovery_cache_ttl = 0.0
        p2a, p2b = _patch_discovery(instances_v2)
        with p2a, p2b:
            r2 = asyncio.run(mgr.discover())
        assert len(r2) == 2

    def test_discover_returns_empty_list(self):
        mgr = NeovimManager()
        with (
            patch("nvim_mcp.manager.find_all_sockets", return_value=[]),
        ):
            result = asyncio.run(mgr.discover())
        assert result == []

    def test_discover_cache_returns_independent_copy(self):
        mgr = NeovimManager()
        instances = [_make_instance(0)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            asyncio.run(mgr.discover())
        result2 = asyncio.run(mgr.discover())
        result2.append(_make_instance(1))
        result3 = asyncio.run(mgr.discover())
        assert len(result3) == 1

    def test_discover_probe_timeout_returns_none(self):
        mgr = NeovimManager()
        with (
            patch("nvim_mcp.manager.find_all_sockets", return_value=["/sock1"]),
            patch(
                "nvim_mcp.manager.probe_socket",
                side_effect=asyncio.TimeoutError("probe timed out"),
            ),
        ):
            result = asyncio.run(mgr.discover())
        assert result == []

    def test_discover_probe_generic_exception(self):
        mgr = NeovimManager()
        with (
            patch("nvim_mcp.manager.find_all_sockets", return_value=["/sock1"]),
            patch(
                "nvim_mcp.manager.probe_socket",
                side_effect=RuntimeError("unexpected"),
            ),
        ):
            result = asyncio.run(mgr.discover())
        assert result == []


# ===================================================================
# NeovimManager — Connect
# ===================================================================

class TestConnect:
    def test_connect_single_instance_auto_selects(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {
            "cwd": "/home/user/project0",
            "windows": [{"file": "file0.py"}],
        }
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect())
        assert result["connected"] == inst.socket_path
        assert result["cwd"] == "/home/user/project0"
        assert result["file"] == "file0.py"

    def test_connect_no_instances_returns_error(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            result = asyncio.run(mgr.connect())
        assert "error" in result
        assert "No Neovim instances" in result["error"]

    def test_connect_multiple_instances_no_args_returns_list(self):
        mgr = NeovimManager()
        instances = [_make_instance(0), _make_instance(1)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            result = asyncio.run(mgr.connect())
        assert "error" in result
        assert "Multiple Neovim instances" in result["error"]
        assert "instances" in result
        assert len(result["instances"]) == 2

    def test_connect_by_socket_path(self):
        mgr = NeovimManager()
        instances = [_make_instance(0)]
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {
            "cwd": "/cwd",
            "windows": [{"file": "f.py"}],
        }
        p1, p2 = _patch_discovery(instances)
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect(socket_path="/custom/path"))
        assert result["connected"] == "/custom/path"

    def test_connect_by_terminal_pid(self):
        mgr = NeovimManager()
        inst = _make_instance(0)
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"cwd": "/c", "windows": [{"file": "x"}]}
        p1, p2 = _patch_discovery([inst])
        with (
            p1, p2,
            patch.object(NvimClient, "connect", return_value=mock_nvim),
            patch("nvim_mcp.manager.find_socket_for_terminal", return_value=inst.socket_path),
        ):
            result = asyncio.run(mgr.connect(terminal_pid=5000))
        assert result["connected"] == inst.socket_path

    def test_connect_by_terminal_pid_not_found(self):
        mgr = NeovimManager()
        inst = _make_instance(0)
        p1, p2 = _patch_discovery([inst])
        with (
            p1, p2,
            patch("nvim_mcp.manager.find_socket_for_terminal", return_value=None),
        ):
            result = asyncio.run(mgr.connect(terminal_pid=9999))
        assert "error" in result
        assert "9999" in result["error"]

    def test_connect_by_index(self):
        mgr = NeovimManager()
        instances = [_make_instance(0), _make_instance(1)]
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"cwd": "/c", "windows": [{"file": "f"}]}
        p1, p2 = _patch_discovery(instances)
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect(index=2))
        assert result["connected"] == instances[1].socket_path

    def test_connect_by_index_out_of_range(self):
        mgr = NeovimManager()
        instances = [_make_instance(0)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            result = asyncio.run(mgr.connect(index=5))
        assert "error" in result
        assert "out of range" in result["error"]

    def test_connect_by_index_zero_out_of_range(self):
        mgr = NeovimManager()
        instances = [_make_instance(0)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            result = asyncio.run(mgr.connect(index=0))
        assert "error" in result

    def test_connect_handles_connection_error(self):
        mgr = NeovimManager()
        inst = _make_instance()
        p1, p2 = _patch_discovery([inst])
        with (
            p1, p2,
            patch.object(NvimClient, "connect", side_effect=OSError("refused")),
        ):
            result = asyncio.run(mgr.connect())
        assert "error" in result
        assert "Could not connect" in result["error"]

    def test_connect_handles_timeout_error(self):
        mgr = NeovimManager()
        inst = _make_instance()
        p1, p2 = _patch_discovery([inst])
        with (
            p1, p2,
            patch.object(NvimClient, "connect", side_effect=asyncio.TimeoutError()),
        ):
            result = asyncio.run(mgr.connect())
        assert "error" in result

    def test_connect_state_fetch_failure_defaults(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.side_effect = Exception("lua error")
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect())
        assert result["cwd"] == "?"
        assert result["file"] == "?"

    def test_connect_empty_windows_defaults_file(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"cwd": "/c", "windows": []}
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect())
        assert result["file"] == "(none)"

    def test_connect_state_missing_cwd_key(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"windows": [{"file": "x.py"}]}
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect())
        assert result["cwd"] == "?"

    def test_connect_state_missing_windows_key(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"cwd": "/c"}
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect())
        assert result["file"] == "(none)"

    def test_connect_window_with_empty_file_string(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"cwd": "/c", "windows": [{"file": ""}]}
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect())
        assert result["file"] == "(none)"

    def test_connect_window_missing_file_key(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"cwd": "/c", "windows": [{"buftype": "term"}]}
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.connect())
        assert result["file"] == "(none)"


# ===================================================================
# NeovimManager — send_command
# ===================================================================

class TestSendCommand:
    def test_single_command_output(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "hello", "errmsg": ""}
        result = asyncio.run(mgr.send_command("echo 'hello'"))
        assert isinstance(result, dict)
        assert result["output"] == "hello"

    def test_single_command_no_output(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "", "errmsg": ""}
        result = asyncio.run(mgr.send_command("w"))
        assert result == {"output": "(no output)"}

    def test_single_command_error(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "", "errmsg": "E492: Not an editor command"}
        result = asyncio.run(mgr.send_command("badcmd"))
        assert "error" in result
        assert "E492" in result["error"]

    def test_single_command_output_and_error(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "partial", "errmsg": "E500: oops"}
        result = asyncio.run(mgr.send_command("cmd"))
        assert result["output"] == "partial"
        assert result["error"] == "E500: oops"

    def test_command_list(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.side_effect = [
            {"output": "r1", "errmsg": ""},
            {"output": "", "errmsg": ""},
            {"output": "r3", "errmsg": ""},
        ]
        result = asyncio.run(mgr.send_command(["cmd1", "cmd2", "cmd3"]))
        assert isinstance(result, list)
        assert len(result) == 3
        assert result[0]["output"] == "r1"
        assert result[1] == {"output": "(no output)"}
        assert result[2]["output"] == "r3"

    def test_auto_connects_when_no_client(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"output": "connected!", "errmsg": ""}
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.send_command("w"))
        assert result["output"] == "connected!"

    def test_auto_connect_fails_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            result = asyncio.run(mgr.send_command("w"))
        assert "error" in result
        assert "No Neovim instances" in result["error"]

    def test_auto_connect_fails_multiple_instances(self):
        mgr = NeovimManager()
        instances = [_make_instance(0), _make_instance(1)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            result = asyncio.run(mgr.send_command("w"))
        assert "instances" in result

    def test_command_list_returns_error_on_auto_connect_fail(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            result = asyncio.run(mgr.send_command(["cmd1", "cmd2"]))
        assert "error" in result

    def test_empty_command_list(self):
        mgr, mock_nvim = _connected_manager()
        result = asyncio.run(mgr.send_command([]))
        assert isinstance(result, list)
        assert len(result) == 0


# ===================================================================
# NeovimManager — send_keys
# ===================================================================

class TestSendKeys:
    def test_sends_keys_with_escape_prefix(self):
        mgr, mock_nvim = _connected_manager()
        result = asyncio.run(mgr.send_keys("gg"))
        assert result == {"sent": "gg"}
        mock_nvim.input.assert_called_once_with("<Esc>gg")

    def test_auto_connects_when_no_client(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.send_keys("dd"))
        assert result == {"sent": "dd"}
        mock_nvim.input.assert_called_once_with("<Esc>dd")

    def test_returns_error_when_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            result = asyncio.run(mgr.send_keys("gg"))
        assert "error" in result


# ===================================================================
# NeovimManager — get_state
# ===================================================================

class TestGetState:
    def test_returns_state_dict(self):
        mgr, mock_nvim = _connected_manager()
        state = {"mode": "normal", "cwd": "/home", "windows": [], "buffers": []}
        mock_nvim.exec_lua.return_value = state
        result = asyncio.run(mgr.get_state())
        assert result == state

    def test_auto_connects(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        state = {"mode": "normal", "cwd": "/c", "windows": []}
        mock_nvim.exec_lua.return_value = state
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr.get_state())
        assert result == state

    def test_raises_when_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            with pytest.raises(RuntimeError, match="No Neovim instances"):
                asyncio.run(mgr.get_state())

    def test_raises_when_multiple_instances(self):
        mgr = NeovimManager()
        instances = [_make_instance(0), _make_instance(1)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            with pytest.raises(RuntimeError):
                asyncio.run(mgr.get_state())


# ===================================================================
# NeovimManager — get_diagnostics
# ===================================================================

class TestGetDiagnostics:
    def test_returns_diagnostics_list(self):
        mgr, mock_nvim = _connected_manager()
        diags = [{"file": "a.py", "line": 1, "severity": "error", "message": "oops"}]
        mock_nvim.exec_lua.return_value = diags
        result = asyncio.run(mgr.get_diagnostics())
        assert result == diags

    def test_returns_diagnostics_for_file(self):
        mgr, mock_nvim = _connected_manager()
        diags = [{"file": "b.py", "line": 5, "severity": "warning", "message": "hmm"}]
        mock_nvim.exec_lua.return_value = diags
        result = asyncio.run(mgr.get_diagnostics(file="b.py"))
        assert result == diags

    def test_raises_on_error_dict(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"error": "Buffer not found: z.py"}
        with pytest.raises(RuntimeError, match="Buffer not found"):
            asyncio.run(mgr.get_diagnostics(file="z.py"))

    def test_raises_when_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            with pytest.raises(RuntimeError):
                asyncio.run(mgr.get_diagnostics())

    def test_returns_empty_list(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = []
        result = asyncio.run(mgr.get_diagnostics())
        assert result == []

    def test_diagnostics_result_is_dict_without_error_key(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"some_key": "value"}
        result = asyncio.run(mgr.get_diagnostics())
        assert result == {"some_key": "value"}


# ===================================================================
# NeovimManager — edit_buffer
# ===================================================================

class TestEditBuffer:
    def test_edit_returns_result(self):
        mgr, mock_nvim = _connected_manager()
        edit_result = {"start_line": 1, "lines_removed": 1, "lines_added": 2, "total_lines": 10}
        mock_nvim.exec_lua.return_value = edit_result
        result = asyncio.run(mgr.edit_buffer("a.py", "new text", "old text"))
        assert result == edit_result

    def test_edit_write_mode(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"total_lines": 5}
        result = asyncio.run(mgr.edit_buffer("a.py", "new content"))
        assert result == {"total_lines": 5}

    def test_raises_when_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            with pytest.raises(RuntimeError):
                asyncio.run(mgr.edit_buffer("a.py", "text"))


# ===================================================================
# NeovimManager — read_buffer
# ===================================================================

class TestReadBuffer:
    def test_read_returns_result(self):
        mgr, mock_nvim = _connected_manager()
        read_result = {"lines": ["1: hello", "2: world"], "total_lines": 2}
        mock_nvim.exec_lua.return_value = read_result
        result = asyncio.run(mgr.read_buffer("a.py"))
        assert result == read_result

    def test_read_with_line_range(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"lines": ["5: middle"], "total_lines": 10}
        result = asyncio.run(mgr.read_buffer("a.py", start_line=5, end_line=5))
        assert result["lines"] == ["5: middle"]

    def test_raises_when_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            with pytest.raises(RuntimeError):
                asyncio.run(mgr.read_buffer("a.py"))


# ===================================================================
# NeovimManager — highlight_buffer / clear_highlights
# ===================================================================

class TestHighlightBuffer:
    def test_highlight_returns_result(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"highlighted": 5}
        result = asyncio.run(mgr.highlight_buffer("a.py", 1, 5, "#ff0000"))
        assert result == {"highlighted": 5}

    def test_highlight_default_color(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"highlighted": 1}
        asyncio.run(mgr.highlight_buffer("a.py", 1, 1))
        call_args = mock_nvim.exec_lua.call_args[0]
        assert call_args[4] == "Yellow"

    def test_raises_when_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            with pytest.raises(RuntimeError):
                asyncio.run(mgr.highlight_buffer("a.py", 1, 1))


class TestClearHighlights:
    def test_clear_returns_result(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"cleared": True}
        result = asyncio.run(mgr.clear_highlights("a.py"))
        assert result == {"cleared": True}

    def test_clear_passes_correct_lua_args(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"cleared": True}
        asyncio.run(mgr.clear_highlights("test.py"))
        call_args = mock_nvim.exec_lua.call_args[0]
        assert call_args[1] == "test.py"
        assert call_args[2] is None  # start_line
        assert call_args[3] is None  # end_line
        assert call_args[4] is None  # color
        assert call_args[5] is True  # clear flag

    def test_raises_when_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            with pytest.raises(RuntimeError):
                asyncio.run(mgr.clear_highlights("a.py"))


# ===================================================================
# NeovimManager — _auto_connect_unlocked
# ===================================================================

class TestAutoConnectUnlocked:
    def test_returns_error_when_no_instances(self):
        mgr = NeovimManager()
        with patch("nvim_mcp.manager.find_all_sockets", return_value=[]):
            result = asyncio.run(mgr._auto_connect_unlocked())
        assert isinstance(result, dict)
        assert "error" in result

    def test_returns_instance_list_when_multiple(self):
        mgr = NeovimManager()
        instances = [_make_instance(0), _make_instance(1)]
        p1, p2 = _patch_discovery(instances)
        with p1, p2:
            result = asyncio.run(mgr._auto_connect_unlocked())
        assert isinstance(result, dict)
        assert "instances" in result

    def test_connects_single_instance(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = asyncio.run(mgr._auto_connect_unlocked())
        assert result is None
        assert mgr._nvim is mock_nvim
        assert mgr._socket_path == inst.socket_path

    def test_returns_error_on_connection_failure(self):
        mgr = NeovimManager()
        inst = _make_instance()
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", side_effect=OSError("refused")):
            result = asyncio.run(mgr._auto_connect_unlocked())
        assert isinstance(result, dict)
        assert "error" in result
        assert "auto-connect" in result["error"]

    def test_returns_error_on_timeout(self):
        mgr = NeovimManager()
        inst = _make_instance()
        p1, p2 = _patch_discovery([inst])
        with p1, p2, patch.object(NvimClient, "connect", side_effect=asyncio.TimeoutError()):
            result = asyncio.run(mgr._auto_connect_unlocked())
        assert isinstance(result, dict)
        assert "error" in result


# ===================================================================
# NeovimManager — _reconnect_unlocked
# ===================================================================

class TestReconnectUnlocked:
    def test_raises_when_no_previous_path(self):
        mgr = NeovimManager()
        with pytest.raises(RuntimeError, match="no previous socket path"):
            asyncio.run(mgr._reconnect_unlocked())

    def test_reconnects_to_previous_path(self):
        mgr, old_nvim = _connected_manager()
        new_nvim = _make_mock_nvim()
        with patch.object(NvimClient, "connect", return_value=new_nvim):
            asyncio.run(mgr._reconnect_unlocked())
        assert mgr._nvim is new_nvim
        old_nvim.close.assert_called_once()

    def test_raises_on_reconnect_failure(self):
        mgr, _ = _connected_manager()
        with patch.object(NvimClient, "connect", side_effect=OSError("dead")):
            with pytest.raises(RuntimeError, match="Reconnect.*failed"):
                asyncio.run(mgr._reconnect_unlocked())

    def test_closes_old_connection_even_if_close_errors(self):
        mgr, old_nvim = _connected_manager()
        old_nvim.close.side_effect = OSError("already closed")
        new_nvim = _make_mock_nvim()
        with patch.object(NvimClient, "connect", return_value=new_nvim):
            asyncio.run(mgr._reconnect_unlocked())
        assert mgr._nvim is new_nvim

    def test_reconnect_when_nvim_is_none(self):
        mgr = NeovimManager()
        mgr._socket_path = "/tmp/nvim.0/0"
        new_nvim = _make_mock_nvim()
        with patch.object(NvimClient, "connect", return_value=new_nvim):
            asyncio.run(mgr._reconnect_unlocked())
        assert mgr._nvim is new_nvim

    def test_reconnect_timeout_error(self):
        mgr, _ = _connected_manager()
        with patch.object(NvimClient, "connect", side_effect=asyncio.TimeoutError()):
            with pytest.raises(RuntimeError, match="Reconnect.*failed"):
                asyncio.run(mgr._reconnect_unlocked())


# ===================================================================
# NeovimManager — _retry_on_disconnect
# ===================================================================

class TestRetryOnDisconnect:
    def test_returns_on_first_success(self):
        mgr, mock_nvim = _connected_manager()

        def sync_fn():
            return "ok"

        result = asyncio.run(mgr._retry_on_disconnect(sync_fn))
        assert result == "ok"

    def test_retries_on_connection_error(self):
        mgr, mock_nvim = _connected_manager()
        call_count = 0

        def sync_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("broken pipe")
            return "recovered"

        new_nvim = _make_mock_nvim()
        with patch.object(NvimClient, "connect", return_value=new_nvim):
            result = asyncio.run(mgr._retry_on_disconnect(sync_fn))
        assert result == "recovered"
        assert call_count == 2

    def test_does_not_retry_non_connection_error(self):
        mgr, mock_nvim = _connected_manager()

        def sync_fn():
            raise ValueError("unrelated")

        with pytest.raises(ValueError, match="unrelated"):
            asyncio.run(mgr._retry_on_disconnect(sync_fn))

    def test_retries_on_nvim_eof_error(self):
        mgr, mock_nvim = _connected_manager()
        call_count = 0

        def sync_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NvimError("EOF")
            return "back"

        new_nvim = _make_mock_nvim()
        with patch.object(NvimClient, "connect", return_value=new_nvim):
            result = asyncio.run(mgr._retry_on_disconnect(sync_fn))
        assert result == "back"

    def test_does_not_retry_nvim_expression_error(self):
        mgr, mock_nvim = _connected_manager()

        def sync_fn():
            raise NvimError("E15: Invalid expression")

        with pytest.raises(NvimError, match="E15"):
            asyncio.run(mgr._retry_on_disconnect(sync_fn))

    def test_passes_args_to_fn(self):
        mgr, _ = _connected_manager()

        def sync_fn(a, b):
            return a + b

        result = asyncio.run(mgr._retry_on_disconnect(sync_fn, 3, 4))
        assert result == 7

    def test_reconnect_failure_propagates(self):
        mgr, _ = _connected_manager()

        def sync_fn():
            raise OSError("broken")

        with patch.object(NvimClient, "connect", side_effect=OSError("dead")):
            with pytest.raises(RuntimeError, match="Reconnect.*failed"):
                asyncio.run(mgr._retry_on_disconnect(sync_fn))

    def test_second_attempt_also_fails_propagates(self):
        mgr, _ = _connected_manager()

        def sync_fn():
            raise OSError("always broken")

        new_nvim = _make_mock_nvim()
        with patch.object(NvimClient, "connect", return_value=new_nvim):
            with pytest.raises(OSError, match="always broken"):
                asyncio.run(mgr._retry_on_disconnect(sync_fn))

    def test_retry_with_nvim_closed_error(self):
        mgr, _ = _connected_manager()
        call_count = 0

        def sync_fn():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise NvimError("Connection closed by Neovim")
            return "ok"

        new_nvim = _make_mock_nvim()
        with patch.object(NvimClient, "connect", return_value=new_nvim):
            result = asyncio.run(mgr._retry_on_disconnect(sync_fn))
        assert result == "ok"
        assert call_count == 2


# ===================================================================
# NeovimManager — reconnect via send_command (integration-style)
# ===================================================================

class TestReconnectViaSendCommand:
    def test_reconnects_on_broken_pipe(self):
        mgr = NeovimManager()
        old_nvim = _make_mock_nvim()
        new_nvim = _make_mock_nvim()

        mgr._nvim = old_nvim
        mgr._socket_path = "/tmp/nvim.0/0"

        old_nvim.exec_lua.side_effect = OSError("Broken pipe")
        new_nvim.exec_lua.return_value = {"output": "recovered", "errmsg": ""}

        with patch.object(NvimClient, "connect", return_value=new_nvim):
            result = asyncio.run(mgr.send_command("w"))

        assert result["output"] == "recovered"


# ===================================================================
# NeovimManager._is_connection_error
# ===================================================================

class TestIsConnectionError:
    @pytest.mark.parametrize(
        ("exc", "expected"),
        [
            (BrokenPipeError("broken"), True),
            (ConnectionRefusedError("refused"), True),
            (ConnectionResetError("reset"), True),
            (ConnectionAbortedError("aborted"), True),
            (OSError("socket gone"), True),
            (ValueError("unrelated"), False),
        ],
    )
    def test_classification(self, exc, expected):
        assert _is_connection_error(exc) is expected

    @pytest.mark.parametrize(
        ("msg", "expected"),
        [
            ("connection closed", True),
            ("EOF", True),
            ("broken pipe", True),
            ("transport error", True),
            ("session closed by remote", True),
            ("E15: Invalid expression", False),
            ("Unknown function", False),
        ],
    )
    def test_nvim_error_keywords(self, msg, expected):
        assert _is_connection_error(NvimError(msg)) is expected


# ===================================================================
# NeovimManager._find_socket_for_terminal
# ===================================================================

class TestFindSocketForTerminal:
    def test_finds_socket_via_process_tree(self):
        instances = [_make_instance(0)]

        def fake_pgrep(cmd, **_kwargs):
            pid_arg = cmd[2]
            if pid_arg == "100":
                return MagicMock(returncode=0, stdout="200\n")
            if pid_arg == "200":
                return MagicMock(returncode=0, stdout="1000\n")
            return MagicMock(returncode=1, stdout="")

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=fake_pgrep):
            result = find_socket_for_terminal(100, instances)
        assert result == instances[0].socket_path

    def test_returns_none_when_no_match(self):
        instances = [_make_instance(0)]

        def fake_pgrep(cmd, **_kwargs):
            return MagicMock(returncode=1, stdout="")

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=fake_pgrep):
            result = find_socket_for_terminal(999, instances)
        assert result is None

    def test_handles_pgrep_timeout(self):
        import subprocess as sp
        instances = [_make_instance(0)]

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=sp.TimeoutExpired("pgrep", 5)):
            result = find_socket_for_terminal(100, instances)
        assert result is None

    def test_handles_pgrep_oserror(self):
        instances = [_make_instance(0)]

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=OSError("no pgrep")):
            result = find_socket_for_terminal(100, instances)
        assert result is None

    def test_handles_cycle_in_process_tree(self):
        instances = [_make_instance(0)]

        def fake_pgrep(cmd, **_kwargs):
            pid_arg = cmd[2]
            if pid_arg == "100":
                return MagicMock(returncode=0, stdout="200\n")
            if pid_arg == "200":
                return MagicMock(returncode=0, stdout="100\n")  # cycle
            return MagicMock(returncode=1, stdout="")

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=fake_pgrep):
            result = find_socket_for_terminal(100, instances)
        assert result is None

    def test_handles_multiple_children(self):
        inst = NvimInstance(socket_path="/s", pid=300, cwd="/c", current_file="f")

        def fake_pgrep(cmd, **_kwargs):
            pid_arg = cmd[2]
            if pid_arg == "100":
                return MagicMock(returncode=0, stdout="200\n250\n")
            if pid_arg == "250":
                return MagicMock(returncode=0, stdout="300\n")
            return MagicMock(returncode=1, stdout="")

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=fake_pgrep):
            result = find_socket_for_terminal(100, [inst])
        assert result == "/s"

    def test_handles_non_numeric_pgrep_output(self):
        instances = [_make_instance(0)]

        def fake_pgrep(cmd, **_kwargs):
            return MagicMock(returncode=0, stdout="notanumber\n")

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=fake_pgrep):
            result = find_socket_for_terminal(100, instances)
        assert result is None

    def test_empty_instances_list(self):
        def fake_pgrep(cmd, **_kwargs):
            return MagicMock(returncode=0, stdout="200\n")

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=fake_pgrep):
            result = find_socket_for_terminal(100, [])
        assert result is None

    def test_terminal_pid_is_nvim_pid(self):
        inst = _make_instance(0)

        def fake_pgrep(cmd, **_kwargs):
            return MagicMock(returncode=1, stdout="")

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=fake_pgrep):
            result = find_socket_for_terminal(inst.pid, [inst])
        assert result == inst.socket_path

    def test_handles_mixed_valid_invalid_children(self):
        """ValueError from non-numeric line aborts the for loop for that pid."""
        inst = _make_instance(0)

        def fake_pgrep(cmd, **_kwargs):
            pid_arg = cmd[2]
            if pid_arg == "100":
                return MagicMock(returncode=0, stdout="abc\n200\n")
            return MagicMock(returncode=1, stdout="")

        with patch("nvim_mcp.discovery.subprocess.run", side_effect=fake_pgrep):
            result = find_socket_for_terminal(100, [inst])
        assert result is None


# ===================================================================
# NeovimManager._format_instance_dict
# ===================================================================

class TestFormatInstanceDict:
    def test_format_two_instances(self):
        instances = [_make_instance(0), _make_instance(1)]
        result = _format_instance_dict(instances)

        assert isinstance(result, dict)
        assert "Multiple Neovim instances" in result["error"]
        assert len(result["instances"]) == 2
        assert result["instances"][0]["index"] == 1
        assert result["instances"][1]["index"] == 2
        for i, inst in enumerate(instances):
            assert result["instances"][i]["socket_path"] == inst.socket_path
            assert result["instances"][i]["cwd"] == inst.cwd

    def test_format_single_instance(self):
        instances = [_make_instance(0)]
        result = _format_instance_dict(instances)
        assert len(result["instances"]) == 1

    def test_empty_current_file(self):
        inst = NvimInstance(socket_path="/s", pid=1, cwd="/c", current_file="")
        result = _format_instance_dict([inst])
        assert result["instances"][0]["file"] == "(none)"


# ===================================================================
# NeovimManager._all_sockets
# ===================================================================

class TestAllSockets:
    def test_nvim_socket_path_override(self):
        with patch.dict(os.environ, {"NVIM_SOCKET_PATH": "/tmp/my_nvim.sock"}):
            with (
                patch("os.path.realpath", return_value="/tmp/my_nvim.sock"),
                patch("os.stat") as mock_stat,
            ):
                mock_stat.return_value.st_mode = stat.S_IFSOCK | 0o755
                result = find_all_sockets()
        assert result == ["/tmp/my_nvim.sock"]

    def test_nvim_socket_path_override_not_socket(self):
        with patch.dict(os.environ, {"NVIM_SOCKET_PATH": "/tmp/not_a_socket"}, clear=False):
            with (
                patch("os.path.realpath", return_value="/tmp/not_a_socket"),
                patch("os.stat") as mock_stat,
            ):
                mock_stat.return_value.st_mode = stat.S_IFREG | 0o644
                with patch("os.path.isdir", return_value=False):
                    result = find_all_sockets()
        assert "/tmp/not_a_socket" not in result

    def test_nvim_socket_path_override_stat_failure(self):
        with patch.dict(os.environ, {"NVIM_SOCKET_PATH": "/tmp/gone"}, clear=False):
            with (
                patch("os.path.realpath", return_value="/tmp/gone"),
                patch("os.stat", side_effect=OSError("no such file")),
                patch("os.path.isdir", return_value=False),
            ):
                result = find_all_sockets()
        assert "/tmp/gone" not in result

    def test_walks_search_dirs(self):
        def fake_walk(base_dir, **kwargs):
            if base_dir == "/run/user/1000":
                yield ("/run/user/1000", ["nvim.user"], ["nvim.sock1"])
                yield ("/run/user/1000/nvim.user", [], ["nvim.0"])
            else:
                return

        def fake_stat(path):
            m = MagicMock()
            if "nvim" in path:
                m.st_mode = stat.S_IFSOCK | 0o755
            else:
                m.st_mode = stat.S_IFREG | 0o644
            return m

        with patch.dict(os.environ, {"NVIM_SOCKET_PATH": ""}, clear=False):
            with (
                patch("os.environ.get", side_effect=lambda k, *a: {
                    "NVIM_SOCKET_PATH": "",
                    "XDG_RUNTIME_DIR": "/run/user/1000",
                    "TMPDIR": None,
                }.get(k, a[0] if a else None)),
                patch("os.getuid", return_value=1000),
                patch("os.path.isdir", return_value=True),
                patch("os.walk", side_effect=fake_walk),
                patch("os.stat", side_effect=fake_stat),
                patch("os.path.realpath", side_effect=lambda p: p),
            ):
                result = find_all_sockets()

        assert len(result) >= 1
        assert any("nvim" in r for r in result)

    def test_skips_non_nvim_entries(self):
        def fake_walk(base_dir, **kwargs):
            yield (base_dir, [], ["other.sock", "nvim.sock"])

        def fake_stat(path):
            m = MagicMock()
            m.st_mode = stat.S_IFSOCK | 0o755
            return m

        with patch.dict(os.environ, {}, clear=True):
            with (
                patch("os.path.isdir", return_value=True),
                patch("os.walk", side_effect=fake_walk),
                patch("os.stat", side_effect=fake_stat),
                patch("os.path.realpath", side_effect=lambda p: p),
                patch("os.getuid", return_value=1000),
            ):
                result = find_all_sockets()

        for r in result:
            assert "nvim" in os.path.basename(r)

    def test_deduplicates_by_realpath(self):
        def fake_walk(base_dir, **kwargs):
            yield (base_dir, [], ["nvim.sock", "nvim.sock.link"])

        def fake_stat(path):
            m = MagicMock()
            m.st_mode = stat.S_IFSOCK | 0o755
            return m

        with patch.dict(os.environ, {}, clear=True):
            with (
                patch("os.path.isdir", return_value=True),
                patch("os.walk", side_effect=fake_walk),
                patch("os.stat", side_effect=fake_stat),
                patch("os.path.realpath", return_value="/canonical/nvim.sock"),
                patch("os.getuid", return_value=1000),
            ):
                result = find_all_sockets()

        assert len(result) == 1

    def test_depth_limit_stops_traversal(self):
        walked_dirs = []

        def fake_walk(base_dir, **kwargs):
            yield (base_dir, ["d1"], [])
            yield (base_dir + "/d1", ["d2"], [])
            yield (base_dir + "/d1/d2", ["d3"], [])
            yield (base_dir + "/d1/d2/d3", ["d4"], [])
            yield (base_dir + "/d1/d2/d3/d4", ["nvim_deep"], ["nvim.deep_sock"])
            walked_dirs.append("too_deep")

        with patch.dict(os.environ, {}, clear=True):
            with (
                patch("os.path.isdir", return_value=True),
                patch("os.walk", side_effect=fake_walk),
                patch("os.stat", side_effect=OSError("irrelevant")),
                patch("os.path.realpath", side_effect=lambda p: p),
                patch("os.getuid", return_value=1000),
            ):
                find_all_sockets()

    def test_stat_failure_for_individual_entry(self):
        def fake_walk(base_dir, **kwargs):
            if base_dir == "/tmp":
                yield ("/tmp", [], ["nvim.ok", "nvim.bad"])
            else:
                return

        def fake_stat(path):
            if "bad" in path:
                raise OSError("permission denied")
            m = MagicMock()
            m.st_mode = stat.S_IFSOCK | 0o755
            return m

        with patch.dict(os.environ, {}, clear=True):
            with (
                patch("os.path.isdir", side_effect=lambda d: d == "/tmp"),
                patch("os.walk", side_effect=fake_walk),
                patch("os.stat", side_effect=fake_stat),
                patch("os.path.realpath", side_effect=lambda p: p),
                patch("os.getuid", return_value=1000),
            ):
                result = find_all_sockets()

        assert len(result) == 1
        assert any("nvim.ok" in r for r in result)

    def test_getuid_attribute_error_windows_compat(self):
        def fake_walk(base_dir, **kwargs):
            if base_dir == "/tmp":
                yield ("/tmp", [], ["nvim.sock"])
            else:
                return

        def fake_stat(path):
            m = MagicMock()
            m.st_mode = stat.S_IFSOCK | 0o755
            return m

        with patch.dict(os.environ, {}, clear=True):
            with (
                patch("os.path.isdir", side_effect=lambda d: d == "/tmp"),
                patch("os.walk", side_effect=fake_walk),
                patch("os.stat", side_effect=fake_stat),
                patch("os.path.realpath", side_effect=lambda p: p),
                patch("os.getuid", side_effect=AttributeError),
            ):
                result = find_all_sockets()

        assert any("nvim.sock" in r for r in result)

    def test_no_search_dirs_exist(self):
        with patch.dict(os.environ, {}, clear=True):
            with (
                patch("os.path.isdir", return_value=False),
                patch("os.getuid", return_value=1000),
            ):
                result = find_all_sockets()
        assert result == []

    def test_tmpdir_env_var_adds_search_dir(self):
        def fake_walk(base_dir, **kwargs):
            if base_dir == "/custom/tmp":
                yield ("/custom/tmp", [], ["nvim.sock"])
            else:
                return

        def fake_stat(path):
            m = MagicMock()
            m.st_mode = stat.S_IFSOCK | 0o755
            return m

        with patch.dict(os.environ, {"TMPDIR": "/custom/tmp"}, clear=True):
            with (
                patch("os.path.isdir", return_value=True),
                patch("os.walk", side_effect=fake_walk),
                patch("os.stat", side_effect=fake_stat),
                patch("os.path.realpath", side_effect=lambda p: p),
                patch("os.getuid", return_value=1000),
            ):
                result = find_all_sockets()

        assert any("nvim.sock" in r for r in result)

    def test_entry_is_not_socket_skipped(self):
        def fake_walk(base_dir, **kwargs):
            yield (base_dir, [], ["nvim.log"])

        def fake_stat(path):
            m = MagicMock()
            m.st_mode = stat.S_IFREG | 0o644
            return m

        with patch.dict(os.environ, {}, clear=True):
            with (
                patch("os.path.isdir", return_value=True),
                patch("os.walk", side_effect=fake_walk),
                patch("os.stat", side_effect=fake_stat),
                patch("os.path.realpath", side_effect=lambda p: p),
                patch("os.getuid", return_value=1000),
            ):
                result = find_all_sockets()

        assert result == []


# ===================================================================
# NeovimManager._probe_socket
# ===================================================================

class TestProbeSocket:
    def test_successful_probe(self):
        mock_nvim = MagicMock(spec=NvimClient)
        mock_nvim.exec_lua.return_value = {
            "pid": 1234,
            "cwd": "/home/user",
            "file": "main.py",
        }
        with patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = probe_socket("/tmp/nvim.sock")

        assert result is not None
        assert result.pid == 1234
        assert result.cwd == "/home/user"
        assert result.current_file == "main.py"
        assert result.socket_path == "/tmp/nvim.sock"
        mock_nvim.close.assert_called_once()

    def test_connect_failure_returns_none(self):
        with patch.object(NvimClient, "connect", side_effect=OSError("refused")):
            result = probe_socket("/tmp/dead.sock")
        assert result is None

    def test_exec_lua_failure_returns_none(self):
        mock_nvim = MagicMock(spec=NvimClient)
        mock_nvim.exec_lua.side_effect = NvimError("failed")
        with patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = probe_socket("/tmp/bad.sock")
        assert result is None
        mock_nvim.close.assert_called_once()

    def test_close_failure_suppressed(self):
        mock_nvim = MagicMock(spec=NvimClient)
        mock_nvim.exec_lua.return_value = {"pid": 1, "cwd": "/", "file": ""}
        mock_nvim.close.side_effect = OSError("already closed")
        with patch.object(NvimClient, "connect", return_value=mock_nvim):
            result = probe_socket("/tmp/s")
        assert result is not None


# ===================================================================
# NeovimManager — sync helpers verify correct Lua dispatch
# ===================================================================

class TestSyncHelpers:
    def test_run_command_sync_output_only(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "hello", "errmsg": ""}
        result = mgr._run_command_sync("echo 'hello'")
        assert result == {"output": "hello"}

    def test_run_command_sync_error_only(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "", "errmsg": "E42"}
        result = mgr._run_command_sync("bad")
        assert result == {"error": "E42"}

    def test_run_command_sync_no_output_no_error(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "", "errmsg": ""}
        result = mgr._run_command_sync("silent cmd")
        assert result == {"output": "(no output)"}

    def test_run_command_sync_both(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "out", "errmsg": "err"}
        result = mgr._run_command_sync("cmd")
        assert result == {"output": "out", "error": "err"}

    def test_run_command_sync_none_values(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": None, "errmsg": None}
        result = mgr._run_command_sync("cmd")
        assert result == {"output": "(no output)"}

    def test_run_command_sync_missing_keys(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {}
        result = mgr._run_command_sync("cmd")
        assert result == {"output": "(no output)"}

    def test_run_commands_sync(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.side_effect = [
            {"output": "a", "errmsg": ""},
            {"output": "b", "errmsg": ""},
        ]
        result = mgr._run_commands_sync(["c1", "c2"])
        assert len(result) == 2
        assert result[0]["output"] == "a"
        assert result[1]["output"] == "b"

    def test_run_keys_sync(self):
        mgr, mock_nvim = _connected_manager()
        result = mgr._run_keys_sync("dd")
        assert result == {"sent": "dd"}
        mock_nvim.input.assert_called_once_with("<Esc>dd")

    def test_get_state_sync(self):
        mgr, mock_nvim = _connected_manager()
        state = {"mode": "normal", "cwd": "/c"}
        mock_nvim.exec_lua.return_value = state
        result = mgr._get_state_sync()
        assert result == state

    def test_get_diagnostics_sync_list(self):
        mgr, mock_nvim = _connected_manager()
        diags = [{"file": "a", "line": 1}]
        mock_nvim.exec_lua.return_value = diags
        result = mgr._get_diagnostics_sync(None)
        assert result == diags

    def test_get_diagnostics_sync_error(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"error": "Buffer not found"}
        with pytest.raises(RuntimeError, match="Buffer not found"):
            mgr._get_diagnostics_sync("missing.py")

    def test_edit_buf_sync(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"total_lines": 10}
        result = mgr._edit_buf_sync("f.py", "old", "new")
        assert result == {"total_lines": 10}

    def test_read_buf_sync(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"lines": ["1: x"], "total_lines": 1}
        result = mgr._read_buf_sync("f.py", None, None)
        assert result["total_lines"] == 1

    def test_highlight_buf_sync(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"highlighted": 3}
        result = mgr._highlight_buf_sync("f.py", 1, 3, "#aabbcc")
        assert result == {"highlighted": 3}
        call_args = mock_nvim.exec_lua.call_args[0]
        assert call_args[4] == "#aabbcc"
        assert call_args[5] is False

    def test_clear_highlights_sync(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"cleared": True}
        result = mgr._clear_highlights_sync("f.py")
        assert result == {"cleared": True}


# ===================================================================
# NeovimManager — constructor
# ===================================================================

class TestNeovimManagerInit:
    def test_initial_state(self):
        mgr = NeovimManager()
        assert mgr._nvim is None
        assert mgr._socket_path is None
        assert mgr._discovery_cache is None
        assert mgr._discovery_cache_ttl == 30.0
