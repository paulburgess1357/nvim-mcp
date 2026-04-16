"""Unit tests for nvim_mcp.server — MCP tool wrappers and main entry point.

Covers: all tool functions delegate correctly to NeovimManager,
highlight_ranges batching logic and edge cases, main() invocation.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nvim_mcp.server import (
    clear_highlights,
    connect,
    find_and_replace_buf,
    get_all_diagnostics,
    get_buf_diagnostics,
    get_state,
    highlight_range,
    highlight_ranges,
    read_buf_range,
    read_full_buf,
    send_command,
    send_keys,
    write_full_buf,
)


@pytest.fixture()
def mock_manager():
    """Patch nvim_mcp.server.manager with an async-mocked NeovimManager."""
    mgr = MagicMock()
    mgr.connect = AsyncMock(return_value={"connected": "/tmp/s"})
    mgr.send_command = AsyncMock(return_value={"output": "ok"})
    mgr.send_keys = AsyncMock(return_value={"sent": "dd"})
    mgr.get_state = AsyncMock(return_value={"mode": "normal"})
    mgr.get_diagnostics = AsyncMock(return_value=[])
    mgr.edit_buffer = AsyncMock(return_value={"total_lines": 5})
    mgr.read_buffer = AsyncMock(return_value={"lines": ["1: hi"], "total_lines": 1})
    mgr.highlight_buffer = AsyncMock(return_value={"highlighted": 3})
    mgr.clear_highlights = AsyncMock(return_value={"cleared": True})
    with patch("nvim_mcp.server.manager", mgr):
        yield mgr


class TestConnectTool:
    def test_delegates_no_args(self, mock_manager):
        result = asyncio.run(connect())
        mock_manager.connect.assert_awaited_once_with(
            socket_path=None, terminal_pid=None, index=None,
        )
        assert result["connected"] == "/tmp/s"

    def test_delegates_socket_path(self, mock_manager):
        asyncio.run(connect(socket_path="/custom"))
        mock_manager.connect.assert_awaited_once_with(
            socket_path="/custom", terminal_pid=None, index=None,
        )

    def test_delegates_terminal_pid(self, mock_manager):
        asyncio.run(connect(terminal_pid=1234))
        mock_manager.connect.assert_awaited_once_with(
            socket_path=None, terminal_pid=1234, index=None,
        )

    def test_delegates_index(self, mock_manager):
        asyncio.run(connect(index=2))
        mock_manager.connect.assert_awaited_once_with(
            socket_path=None, terminal_pid=None, index=2,
        )


class TestSendCommandTool:
    def test_delegates_string(self, mock_manager):
        result = asyncio.run(send_command("w"))
        mock_manager.send_command.assert_awaited_once_with("w")
        assert result == {"output": "ok"}

    def test_delegates_list(self, mock_manager):
        mock_manager.send_command = AsyncMock(return_value=[{"output": "a"}, {"output": "b"}])
        result = asyncio.run(send_command(["c1", "c2"]))
        mock_manager.send_command.assert_awaited_once_with(["c1", "c2"])
        assert isinstance(result, list)


class TestSendKeysTool:
    def test_delegates(self, mock_manager):
        result = asyncio.run(send_keys("gg"))
        mock_manager.send_keys.assert_awaited_once_with("gg")
        assert result == {"sent": "dd"}


class TestGetStateTool:
    def test_delegates(self, mock_manager):
        result = asyncio.run(get_state())
        mock_manager.get_state.assert_awaited_once()
        assert result["mode"] == "normal"


class TestGetDiagnosticsTools:
    def test_all_diagnostics(self, mock_manager):
        result = asyncio.run(get_all_diagnostics())
        mock_manager.get_diagnostics.assert_awaited_once_with()
        assert result == []

    def test_buf_diagnostics(self, mock_manager):
        asyncio.run(get_buf_diagnostics(file="a.py"))
        mock_manager.get_diagnostics.assert_awaited_once_with(file="a.py")


class TestFindAndReplaceBufTool:
    def test_delegates(self, mock_manager):
        result = asyncio.run(find_and_replace_buf("a.py", "old", "new"))
        mock_manager.edit_buffer.assert_awaited_once_with(
            file="a.py", new_string="new", old_string="old",
        )
        assert result == {"total_lines": 5}


class TestWriteFullBufTool:
    def test_delegates(self, mock_manager):
        result = asyncio.run(write_full_buf("b.py", "content"))
        mock_manager.edit_buffer.assert_awaited_once_with(
            file="b.py", new_string="content",
        )
        assert result == {"total_lines": 5}


class TestReadFullBufTool:
    def test_delegates(self, mock_manager):
        result = asyncio.run(read_full_buf("c.py"))
        mock_manager.read_buffer.assert_awaited_once_with(file="c.py")
        assert result["total_lines"] == 1


class TestReadBufRangeTool:
    def test_delegates(self, mock_manager):
        asyncio.run(read_buf_range("d.py", 5, 10))
        mock_manager.read_buffer.assert_awaited_once_with(
            file="d.py", start_line=5, end_line=10,
        )


class TestHighlightRangeTool:
    def test_delegates_with_default_color(self, mock_manager):
        asyncio.run(highlight_range("e.py", 1, 5))
        mock_manager.highlight_buffer.assert_awaited_once_with(
            file="e.py", start_line=1, end_line=5, color="#3b4048",
        )

    def test_delegates_with_custom_color(self, mock_manager):
        asyncio.run(highlight_range("e.py", 1, 5, color="Red"))
        mock_manager.highlight_buffer.assert_awaited_once_with(
            file="e.py", start_line=1, end_line=5, color="Red",
        )


class TestHighlightRangesTool:
    def test_batches_multiple_highlights(self, mock_manager):
        highlights = [
            {"file": "a.py", "start_line": 1, "end_line": 3, "color": "#ff0000"},
            {"file": "b.py", "start_line": 10, "end_line": 12},
        ]
        result = asyncio.run(highlight_ranges(highlights))
        assert len(result) == 2
        assert mock_manager.highlight_buffer.await_count == 2

        calls = mock_manager.highlight_buffer.await_args_list
        assert calls[0].kwargs == {
            "file": "a.py", "start_line": 1, "end_line": 3, "color": "#ff0000",
        }
        assert calls[1].kwargs == {
            "file": "b.py", "start_line": 10, "end_line": 12, "color": "#3b4048",
        }

    def test_empty_list(self, mock_manager):
        result = asyncio.run(highlight_ranges([]))
        assert result == []
        mock_manager.highlight_buffer.assert_not_awaited()

    def test_single_highlight(self, mock_manager):
        result = asyncio.run(highlight_ranges([
            {"file": "f.py", "start_line": 5, "end_line": 5, "color": "Yellow"},
        ]))
        assert len(result) == 1

    def test_uses_default_color_when_missing(self, mock_manager):
        asyncio.run(highlight_ranges([{"file": "x.py", "start_line": 1, "end_line": 1}]))
        call = mock_manager.highlight_buffer.await_args_list[0]
        assert call.kwargs["color"] == "#3b4048"

    def test_propagates_error_from_manager(self, mock_manager):
        mock_manager.highlight_buffer = AsyncMock(
            side_effect=RuntimeError("Buffer not found"),
        )
        with pytest.raises(RuntimeError, match="Buffer not found"):
            asyncio.run(highlight_ranges([
                {"file": "gone.py", "start_line": 1, "end_line": 1},
            ]))

    def test_partial_failure_stops_iteration(self, mock_manager):
        mock_manager.highlight_buffer = AsyncMock(
            side_effect=[{"highlighted": 2}, RuntimeError("fail")],
        )
        with pytest.raises(RuntimeError):
            asyncio.run(highlight_ranges([
                {"file": "a.py", "start_line": 1, "end_line": 2},
                {"file": "b.py", "start_line": 1, "end_line": 1},
            ]))
        assert mock_manager.highlight_buffer.await_count == 2


class TestClearHighlightsTool:
    def test_delegates(self, mock_manager):
        result = asyncio.run(clear_highlights("f.py"))
        mock_manager.clear_highlights.assert_awaited_once_with(file="f.py")
        assert result == {"cleared": True}


class TestMainEntryPoint:
    def test_main_calls_mcp_run(self):
        with patch("nvim_mcp.server.mcp") as mock_mcp:
            from nvim_mcp.server import main
            main()
            mock_mcp.run.assert_called_once_with(transport="stdio")
