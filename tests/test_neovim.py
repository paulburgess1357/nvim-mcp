"""Tests for NeovimManager with mocked pynvim — no real Neovim required."""

import asyncio
from unittest.mock import MagicMock, patch

import pynvim
import pytest

from nvim_mcp.neovim import NeovimManager, NvimInstance


def _make_instance(idx: int = 0) -> NvimInstance:
    return NvimInstance(
        socket_path=f"/tmp/nvim.{idx}/0",
        pid=1000 + idx,
        cwd=f"/home/user/project{idx}",
        current_file=f"file{idx}.py",
    )


def _make_mock_nvim() -> MagicMock:
    mock = MagicMock(spec=pynvim.Nvim)
    mock.exec_lua.return_value = {"output": "", "errmsg": ""}
    return mock


class TestSingleInstanceAutoConnect:
    def test_auto_connects_and_sends_command(self):
        mgr = NeovimManager()
        inst = _make_instance()
        mock_nvim = _make_mock_nvim()
        mock_nvim.exec_lua.return_value = {"output": "test output", "errmsg": ""}

        with (
            patch.object(NeovimManager, "_all_sockets", return_value=[inst.socket_path]),
            patch.object(NeovimManager, "_probe_socket", return_value=inst),
            patch("pynvim.attach", return_value=mock_nvim),
        ):
            result = asyncio.run(mgr.send("w", "command"))

        assert "test output" in result


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
            patch("pynvim.attach", return_value=mock_nvim),
        ):
            result = asyncio.run(mgr.connect(index=1))

        assert "Connected" in result
        assert instances[0].socket_path in result


class TestSendModes:
    def _connected_manager(self) -> tuple[NeovimManager, MagicMock]:
        mgr = NeovimManager()
        mock_nvim = _make_mock_nvim()
        mgr._nvim = mock_nvim
        mgr._socket_path = "/tmp/nvim.0/0"
        return mgr, mock_nvim

    def test_command_mode(self):
        mgr, mock_nvim = self._connected_manager()
        mock_nvim.exec_lua.return_value = {"output": "test output", "errmsg": ""}
        result = asyncio.run(mgr.send("w", "command"))
        assert "test output" in result

    def test_eval_mode(self):
        mgr, mock_nvim = self._connected_manager()
        mock_nvim.eval.return_value = "42"
        result = asyncio.run(mgr.send("1+1", "eval"))
        assert result == "42"

    def test_keys_mode(self):
        mgr, mock_nvim = self._connected_manager()
        result = asyncio.run(mgr.send("gg", "keys"))
        assert result == "Keys sent: gg"
        mock_nvim.input.assert_called_once_with("<Esc>gg")

    def test_eval_nvim_error(self):
        mgr, mock_nvim = self._connected_manager()
        mock_nvim.eval.side_effect = pynvim.NvimError("E15: Invalid expression")
        result = asyncio.run(mgr.send("bad expr", "eval"))
        assert "Error:" in result
        assert "E15" in result


class TestReconnect:
    def test_reconnects_on_connection_error(self):
        mgr = NeovimManager()
        mock_nvim_old = _make_mock_nvim()
        mock_nvim_new = _make_mock_nvim()
        mock_nvim_new.exec_lua.return_value = {"output": "after reconnect", "errmsg": ""}

        mgr._nvim = mock_nvim_old
        mgr._socket_path = "/tmp/nvim.0/0"

        call_count = 0

        def _send_sync_side_effect(input_str, mode):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise OSError("Broken pipe")
            mgr._nvim = mock_nvim_new
            return mock_nvim_new.exec_lua.return_value

        with patch("pynvim.attach", return_value=mock_nvim_new):
            mock_nvim_old.exec_lua.side_effect = OSError("Broken pipe")
            mock_nvim_new.exec_lua.return_value = {"output": "after reconnect", "errmsg": ""}
            result = asyncio.run(mgr.send("w", "command"))

        assert "after reconnect" in result


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
        err = pynvim.NvimError("connection closed")
        assert NeovimManager._is_connection_error(err) is True

    def test_nvim_error_without_connection_keyword(self):
        err = pynvim.NvimError("E15: Invalid expression")
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
