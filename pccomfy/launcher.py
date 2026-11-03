"""Start PhotoCraft with the control channel and then the bridge window, like the starter .bat but without a console
window, from a desktop shortcut with PhotoCraft's icon (Windows; user 28.10., option B).

    python -m pccomfy shortcut --photocraft "C:\\path\\to\\photocraft.exe"

creates the shortcut "PhotoCraft AI" on the desktop; it runs `photocraft-ai.pyw --photocraft <path>` with pythonw.exe.
Without --photocraft the exe is searched in the usual places (find_photocraft), else asked once; setup-windows.bat does this
at its end (user 30.10.).

Linux (PLAN.md 18c, stage e): the same command writes a menu entry instead, ~/.local/share/applications/photocraft-ai.desktop,
which runs `python photocraft-ai.pyw --photocraft <binary>`; `photocraft-ai.sh` starts it from a terminal. The binary is
called `photocraft` there (PATH, /opt, ~/Applications, ...). The Windows code above and below is unchanged.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from . import autostart
from . import config as cfgmod
from .appname import APP_NAME
from .hostos import IS_WINDOWS

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "photocraft-ai.pyw"
NAME = APP_NAME
WAIT_S = 30.0       # as the .bat: 150 tries of 0.2 s


class LaunchError(Exception):
    pass


def exe_name() -> str:
    return "photocraft.exe" if IS_WINDOWS else "photocraft"


def photocraft_args(exe: str, cfg: dict) -> list[str]:
    """The command line the starter .bat uses: control port, token file, the exchange folder for reading and writing."""
    pcc = cfg["photocraft"]
    xch = str(Path(pcc["exchange_dir"]).expanduser())       # Linux: "~/.cache/..." (no shell here, PhotoCraft would take "~" literally)
    return [exe, "--control", str(int(pcc["port"])), "--control-token-file", str(Path(pcc["token_file"]).expanduser()),
            "--automation-read-root", xch, "--automation-write-root", xch]


def start_photocraft(exe: str, cfg: dict, is_open=None, popen=subprocess.Popen, sleep=time.sleep, wait_s: float = WAIT_S):
    """Start PhotoCraft unless its control port is open already, then wait for the port. Raises LaunchError."""
    pcc = cfg["photocraft"]
    host, port = pcc["host"], int(pcc["port"])
    is_open = is_open or (lambda: autostart.port_open(host, port))
    if is_open():
        return False                      # running with the control channel: only the window is missing
    if not exe or not Path(exe).exists():
        raise LaunchError(f"PhotoCraft not found:\n{exe or '(no path given; use --photocraft or set PHOTOCRAFT)'}")
    Path(pcc["exchange_dir"]).expanduser().mkdir(parents=True, exist_ok=True)
    kw = {} if IS_WINDOWS else {"start_new_session": True}                # Linux: PhotoCraft outlives the terminal
    popen(photocraft_args(exe, cfg), cwd=str(ROOT), close_fds=True, **kw)       # as the .bat (cd /d "%~dp0")
    end = time.monotonic() + wait_s
    while time.monotonic() < end:
        if is_open():
            return True
        sleep(0.2)
    raise LaunchError(f"PhotoCraft did not open the control port {port}.\n"
                      "Is another PhotoCraft already running? Close it and start again.")


def launch(exe: str) -> int:
    cfg = cfgmod.load()
    if not exe and not IS_WINDOWS:
        exe = find_photocraft() or ""
    try:
        start_photocraft(exe, cfg)
    except LaunchError as e:
        _error(str(e))
        return 1
    from .gui import run_gui
    return run_gui(cfg)


def _error(text: str):
    """No console: the message in a small dialog."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(NAME, text, parent=root)
        root.destroy()
    except Exception:  # noqa: BLE001  (no Tk: nothing more to show)
        pass


# ---------- the shortcut ----------

def shortcut_spec(exe: str, name: str = NAME) -> dict:
    """What the shortcut holds: pythonw.exe runs photocraft-ai.pyw with the PhotoCraft path; PhotoCraft's icon."""
    return {"name": name, "target": autostart.pythonw(), "args": f'"{SCRIPT}" --photocraft "{exe}"',
            "workdir": str(ROOT), "icon": f"{exe},0"}


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def create_shortcut(exe: str, name: str = NAME, folder: str | None = None) -> Path:
    """The .lnk on the user's desktop (the real desktop folder, also when OneDrive moves it), via WScript.Shell.
    `folder`: somewhere else instead (the tests)."""
    spec = shortcut_spec(exe, name)
    where = _ps_quote(folder) if folder else "[Environment]::GetFolderPath('Desktop')"
    ps = (f"$d = {where}; "
          f"$p = Join-Path $d ({_ps_quote(spec['name'])} + '.lnk'); "
          "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($p); "
          f"$s.TargetPath = {_ps_quote(spec['target'])}; $s.Arguments = {_ps_quote(spec['args'])}; "
          f"$s.WorkingDirectory = {_ps_quote(spec['workdir'])}; $s.IconLocation = {_ps_quote(spec['icon'])}; "
          "$s.Description = 'PhotoCraft with the ComfyUI bridge'; $s.Save(); $p")
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise LaunchError(out.stderr.strip() or "could not create the shortcut")
    return Path(out.stdout.strip().splitlines()[-1])


def _version(folder: Path) -> tuple:
    """The numbers in a folder name ("photocraft-0.17.0-windows-x64-portable" -> (0, 17, 0, 64)), to take the newest."""
    return tuple(int(n) for n in re.findall(r"\d+", folder.name))


def find_photocraft(roots: list[Path] | None = None) -> str | None:
    """photocraft.exe in the usual places: next to this folder (portable copies), Program Files, the user's Programs
    folder, Downloads and Desktop. Several copies: the one with the highest version in its folder name."""
    if not IS_WINDOWS:
        return _find_photocraft_linux(roots)
    if roots is None:
        home = Path.home()
        env = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)")]
        roots = [ROOT.parent] + [Path(e) for e in env if e] + [Path(os.environ.get("LOCALAPPDATA", home)) / "Programs",
                                                              home / "Downloads", home / "Desktop"]
    found = []
    for root in roots:
        try:
            for d in root.iterdir():
                if d.is_dir() and "photocraft" in d.name.lower() and (d / "photocraft.exe").is_file():
                    found.append(d)
        except OSError:
            continue
    return str(max(found, key=_version) / "photocraft.exe") if found else None


def _find_photocraft_linux(roots: list[Path] | None = None) -> str | None:
    """The `photocraft` binary: $PHOTOCRAFT, then PATH (/usr/bin ...), then folders with "photocraft" in their name under the
    usual roots (next to this folder, /opt, ~/Applications, ~/.local/opt, Downloads, Desktop), then a photocraft*.AppImage.
    With `roots` only those are searched (the tests). Several copies: the highest version in the folder name."""
    if roots is None:
        env = os.environ.get("PHOTOCRAFT")
        if env and Path(env).is_file():
            return env
        on_path = shutil.which("photocraft")
        if on_path:
            return on_path
        home = Path.home()
        roots = [ROOT.parent, Path("/opt"), home / "Applications", home / ".local" / "opt", home / "Downloads", home / "Desktop"]
    found = []
    for root in roots:
        try:
            for d in root.iterdir():
                name = d.name.lower()
                if "photocraft" not in name:
                    continue
                if d.is_dir() and (d / "photocraft").is_file() and os.access(d / "photocraft", os.X_OK):
                    found.append((_version(d), d / "photocraft"))
                elif d.is_file() and name.endswith(".appimage") and os.access(d, os.X_OK):
                    found.append((_version(d), d))
        except OSError:
            continue
    return str(max(found, key=lambda f: f[0])[1]) if found else None


def _desktop_arg(s: str) -> str:
    """One argument of an Exec line: always in double quotes; the characters " ` $ and backslash get a
    backslash, then every backslash is doubled (string value escaping), % becomes %% (field codes)."""
    s = re.sub(r'(["`$\\])', r"\\\1", s).replace("\\", "\\\\").replace("%", "%%")
    return f'"{s}"'


def desktop_entry(exe: str, python: str | None = None, name: str = NAME) -> str:
    """The text of the menu entry: runs photocraft-ai.pyw with the PhotoCraft path; StartupWMClass is the window's WM_CLASS."""
    exec_line = " ".join(_desktop_arg(a) for a in (python or sys.executable, str(SCRIPT), "--photocraft", exe))
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name}", "Comment=PhotoCraft with the ComfyUI bridge",
             f"Exec={exec_line}", f"Path={ROOT}", "Terminal=false", "Categories=Graphics;", "StartupWMClass=pccomfy"]
    return "\n".join(lines) + "\n"


def create_desktop_entry(exe: str, name: str = NAME, folder: str | None = None) -> Path:
    """photocraft-ai.desktop in the user's applications folder (XDG_DATA_HOME), or in `folder` (the tests)."""
    if folder:
        where = Path(folder)
    else:
        where = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "applications"
    where.mkdir(parents=True, exist_ok=True)
    path = where / "photocraft-ai.desktop"
    path.write_text(desktop_entry(exe, name=name), encoding="utf-8")
    path.chmod(0o755)
    return path


def ask_photocraft() -> str | None:
    """No copy found: ask for photocraft.exe once (a file dialog); None when nothing is chosen or there is no Tk."""
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(title=f"Where is {exe_name()}?", filetypes=[("PhotoCraft", exe_name())])
        root.destroy()
        return path or None
    except Exception:  # noqa: BLE001  (no Tk: nothing to ask with)
        return None


def main_shortcut(exe: str | None = None, name: str = NAME) -> int:
    if not IS_WINDOWS and not sys.platform.startswith("linux"):
        print("Only on Windows and Linux.")
        return 1
    if not exe:
        exe = find_photocraft() or ask_photocraft()
        if not exe:
            print(f"{exe_name()} not found. Create the shortcut later: python -m pccomfy shortcut --photocraft <{exe_name()}>")
            return 1
        print(f"PhotoCraft: {exe}")
    if not Path(exe).exists():
        print(f"PhotoCraft not found: {exe}")
        return 1
    try:
        print(f"Created: {(create_shortcut if IS_WINDOWS else create_desktop_entry)(exe, name)}")
    except (LaunchError, OSError, subprocess.SubprocessError) as e:
        print(f"Error: {e}")
        return 1
    return 0
