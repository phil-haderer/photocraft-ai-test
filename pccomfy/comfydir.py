"""Where ComfyUI's ``models`` folder is (no Tk here), so a download can go straight into it.

Order: the test override ``PCCOMFY_MODELS_DIR``, the folder you chose once (settings), the folder of the ComfyUI process that
listens on the port the plugin talks to (Windows: PowerShell; Linux: /proc), else the window asks. ComfyUI's API names no paths.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
from pathlib import Path

from .hostos import IS_LINUX, IS_WINDOWS

LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


def models_dir_of(path: str | Path) -> Path | None:
    """The ``models`` folder for a folder the user (or the process) points at: the ComfyUI folder (main.py and models), the
    folder above it (a portable install), or the models folder itself."""
    p = Path(path)
    for cand in (p, p / "models", p / "ComfyUI" / "models"):
        if cand.name.lower() == "models" and cand.is_dir():
            return cand
    return None


def root_from_process(exe: str, cmdline: str, cwd: str = "") -> Path | None:
    """The ComfyUI folder (it holds main.py and models) from a running process: its working folder (Linux passes it), an
    absolute main.py in the command line, else the folders above its Python (a portable install starts
    ``.\\python_embeded\\python.exe ComfyUI\\main.py``)."""
    if cwd:
        for cand in (Path(cwd), Path(cwd) / "ComfyUI"):
            if (cand / "main.py").exists() and (cand / "models").is_dir():
                return cand
    for tok in (cmdline or "").replace('"', " ").split():
        if tok.lower().endswith("main.py") and os.path.isabs(tok) and Path(tok).exists() and (Path(tok).parent / "models").is_dir():
            return Path(tok).parent
    p = Path(exe or "").parent
    for _ in range(5):
        for cand in (p / "ComfyUI", p):
            if (cand / "main.py").exists() and (cand / "models").is_dir():
                return cand
        if p.parent == p:
            break
        p = p.parent
    return None


def listen_inodes(tcp_text: str, port: int) -> set[str]:
    """The socket inodes that listen on ``port`` in the text of /proc/net/tcp (or tcp6); state 0A = LISTEN."""
    found = set()
    for line in tcp_text.splitlines()[1:]:
        f = line.split()
        if len(f) > 9 and f[3] == "0A":
            try:
                if int(f[1].rsplit(":", 1)[1], 16) == port:
                    found.add(f[9])
            except (IndexError, ValueError):
                continue
    return found


def _find_root_linux(port: int, proc: str = "/proc") -> Path | None:
    """Linux: the process that listens on ``port`` (/proc/net/tcp, then the socket in its fds), its working folder and command line."""
    inodes: set[str] = set()
    for name in ("tcp", "tcp6"):
        try:
            with open(os.path.join(proc, "net", name), encoding="ascii", errors="replace") as fh:
                inodes |= listen_inodes(fh.read(), port)
        except OSError:
            continue
    if not inodes:
        return None
    try:
        pids = [e for e in os.listdir(proc) if e.isdigit()]
    except OSError:
        return None
    for pid in pids:
        fd_dir = os.path.join(proc, pid, "fd")
        try:
            links = (os.readlink(os.path.join(fd_dir, fd)) for fd in os.listdir(fd_dir))
            if not any(link.startswith("socket:[") and link[8:-1] in inodes for link in links):
                continue
            base = os.path.join(proc, pid)
            with open(os.path.join(base, "cmdline"), "rb") as fh:
                cmdline = fh.read().replace(b"\0", b" ").decode(errors="replace").strip()
            return root_from_process(os.readlink(os.path.join(base, "exe")), cmdline, os.readlink(os.path.join(base, "cwd")))
        except OSError:
            continue        # a process of someone else, or gone meanwhile
    return None


def find_root(url: str, timeout: float = 10.0) -> Path | None:
    """The ComfyUI folder of the process that listens on the port of ``url`` (only for a local server), or None."""
    parts = urllib.parse.urlsplit(url)
    if (parts.hostname or "") not in LOCAL_HOSTS or not (IS_WINDOWS or IS_LINUX):
        return None
    port = parts.port or 8188
    if IS_LINUX:
        return _find_root_linux(port)
    script = (f"$c = Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; "
              "if ($c) { Get-CimInstance Win32_Process -Filter \"ProcessId=$($c.OwningProcess)\" | "
              "Select-Object ExecutablePath, CommandLine | ConvertTo-Json -Compress }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True,
                             timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout.strip()
        info = json.loads(out) if out else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return root_from_process(info.get("ExecutablePath") or "", info.get("CommandLine") or "")
