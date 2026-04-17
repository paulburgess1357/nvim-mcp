"""Socket discovery: find, probe, and match running Neovim instances."""

from __future__ import annotations

import os
import stat
import subprocess

from nvim_mcp.client import NvimClient, _parse_tcp_address
from nvim_mcp.types import NvimInstance


def find_all_sockets() -> list[str]:
    """Walk filesystem directories for Unix sockets whose names start with ``nvim``.

    Checks ``NVIM_ADDRESS`` env var first (direct override), then scans
    ``XDG_RUNTIME_DIR``, ``/run/user/<uid>``, ``TMPDIR``, and ``/tmp``.
    Deduplicates by realpath and limits directory depth to 4.
    TCP addresses (``host:port``) are returned as-is without filesystem checks.
    """
    override = os.environ.get("NVIM_ADDRESS")
    if override:
        if _parse_tcp_address(override) is not None:
            return [override]
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
        pass

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


def probe_socket(sock: str) -> NvimInstance | None:
    """Connect to a Neovim socket and extract instance metadata.

    Returns ``None`` on any failure (connection refused, timeout, Lua error).
    Always closes the probe connection.
    """
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


def find_socket_for_terminal(
    terminal_pid: int, instances: list[NvimInstance]
) -> str | None:
    """Find which Neovim instance is a descendant of *terminal_pid*.

    Walks the process tree using ``pgrep -P`` to collect all descendant PIDs,
    then checks if any known Neovim instance PID is among them.
    """
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
                    try:
                        child = int(line.strip())
                    except ValueError:
                        continue
                    if child not in descendants:
                        to_visit.append(child)
        except (subprocess.TimeoutExpired, OSError):
            pass

    for inst in instances:
        if inst.pid in descendants:
            return inst.socket_path
    return None
