"""Tests for NeovimManager with mocked NvimClient — no real Neovim required."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from nvim_mcp.neovim import NeovimManager, NvimClient, NvimError, NvimInstance

_MOCK_STATE = {
    "file": "test.py",
    "line": 1,
    "col": 1,
    "mode": "n",
    "modified": False,
    "filetype": "python",
    "total_lines": 10,
    "cwd": "/home/user/project",
    "relativenumber": False,
    "windows": [
        {
            "file": "test.py",
            "modified": False,
            "active": True,
            "line": 1,
            "col": 1,
            "context": {"lines": ["1: line 1", "2: line 2"]},
        },
    ],
    "modified_buffers": [],
    "buffer_count": 1,
}


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


class TestSingleInstanceAutoConnect:
    def test_auto_connects_and_sends_command(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.side_effect = [
            {"output": "test output", "errmsg": ""},
            _MOCK_STATE,
        ]

        with (
            patch.object(NeovimManager, "_all_sockets", return_value=[inst.socket_path]),
            patch.object(NeovimManager, "_probe_socket", return_value=inst),
            patch.object(NvimClient, "connect", return_value=mock_nvim),
        ):
            result = asyncio.run(mgr.send("w", "command"))

        assert "test output" in result["result"]


class TestMultiInstanceListing:
    def test_connect_no_args_returns_instance_list(self):
        mgr = NeovimManager()
        instances = [_make_instance(0), _make_instance(1)]

        with (
            patch.object(
                NeovimManager,
                "_all_sockets",
                return_value=[i.socket_path for i in instances],
            ),
            patch.object(
                NeovimManager,
                "_probe_socket",
                side_effect=instances,
            ),
        ):
            result = asyncio.run(mgr.connect())

        assert "Multiple Neovim instances" in result
        assert instances[0].socket_path in result
        assert instances[1].socket_path in result

    def test_connect_by_index(self):
        mgr = NeovimManager()
        instances = [_make_instance(0), _make_instance(1)]
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {
            "cwd": "/home/user/project0",
            "file": "file0.py",
        }

        with (
            patch.object(
                NeovimManager,
                "_all_sockets",
                return_value=[i.socket_path for i in instances],
            ),
            patch.object(NeovimManager, "_probe_socket", side_effect=instances),
            patch.object(NvimClient, "connect", return_value=mock_nvim),
        ):
            result = asyncio.run(mgr.connect(index=1))

        assert "Connected" in result
        assert instances[0].socket_path in result


class TestSendModes:
    def test_command_mode(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.side_effect = [
            {"output": "test output", "errmsg": ""},
            _MOCK_STATE,
        ]
        result = asyncio.run(mgr.send("w", "command"))
        assert "test output" in result["result"]

    def test_keys_mode(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = _MOCK_STATE
        result = asyncio.run(mgr.send("gg", "keys"))
        assert result["result"] == "Keys sent: gg"
        mock_nvim.input.assert_called_once_with("<Esc>gg")


class TestReturnState:
    def test_send_returns_state_by_default(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.side_effect = [
            {"output": "test output", "errmsg": ""},
            _MOCK_STATE,
        ]
        result = asyncio.run(mgr.send("w", "command"))
        assert isinstance(result, dict)
        assert "result" in result
        assert "state" in result
        assert result["state"] == _MOCK_STATE

    def test_send_returns_string_when_return_state_false(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "test output", "errmsg": ""}
        result = asyncio.run(mgr.send("w", "command", return_state=False))
        assert isinstance(result, str)
        assert "test output" in result

    def test_send_returns_state_none_on_state_error(self):
        mgr, mock_nvim = _connected_manager()
        mock_nvim.exec_lua.side_effect = [
            {"output": "test output", "errmsg": ""},
            RuntimeError("state fetch failed"),
        ]
        result = asyncio.run(mgr.send("w", "command"))
        assert isinstance(result, dict)
        assert "test output" in result["result"]
        assert result["state"] is None


class TestReconnect:
    def test_reconnects_on_connection_error(self):
        mgr = NeovimManager()
        mock_nvim_old = _make_mock_nvim()
        mock_nvim_new = _make_mock_nvim()

        mgr._nvim = mock_nvim_old
        mgr._socket_path = "/tmp/nvim.0/0"

        with patch.object(NvimClient, "connect", return_value=mock_nvim_new):
            mock_nvim_old.exec_lua.side_effect = OSError("Broken pipe")
            mock_nvim_new.exec_lua.side_effect = [
                {"output": "after reconnect", "errmsg": ""},
                _MOCK_STATE,
            ]
            result = asyncio.run(mgr.send("w", "command"))

        assert "after reconnect" in result["result"]


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
        assert NeovimManager._is_connection_error(exc) is expected

    def test_nvim_error_with_connection_keyword(self):
        err = NvimError("connection closed")
        assert NeovimManager._is_connection_error(err) is True

    def test_nvim_error_without_connection_keyword(self):
        err = NvimError("E15: Invalid expression")
        assert NeovimManager._is_connection_error(err) is False


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

        with patch("subprocess.run", side_effect=fake_pgrep):
            result = NeovimManager._find_socket_for_terminal(100, instances)

        assert result == instances[0].socket_path

    def test_returns_none_when_no_match(self):
        instances = [_make_instance(0)]

        def fake_pgrep(cmd, **_kwargs):
            return MagicMock(returncode=1, stdout="")

        with patch("subprocess.run", side_effect=fake_pgrep):
            result = NeovimManager._find_socket_for_terminal(999, instances)

        assert result is None


class TestFormatInstanceList:
    def test_format_two_instances(self):
        instances = [_make_instance(0), _make_instance(1)]
        result = NeovimManager._format_instance_list(instances)

        assert "Multiple Neovim instances found:" in result
        assert "1." in result
        assert "2." in result
        for inst in instances:
            assert inst.socket_path in result
            assert inst.cwd in result
            assert inst.current_file in result
        assert "index=N" in result
