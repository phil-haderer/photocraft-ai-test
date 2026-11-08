"""After setup-windows.bat / setup-linux.sh: does the installed plugin start? Run by the install matrix
(.github/workflows/install-matrix.yml) with the Python the setup chose, on a fresh machine; not part of tests/run_all.py.

    <venv python> tests/ci_install_smoke.py [--expect-shortcut]

FAIL = a new user could not use the plugin (exit code 1). WARN = it works, but with less (drag and drop, the Inter font).
Needs a display (Windows: always; Linux: DISPLAY, the matrix starts Xvfb). Never talks to ComfyUI or PhotoCraft.
"""
from __future__ import annotations

import importlib
import os
import pkgutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

results: list[tuple[str, str, str]] = []      # (FAIL|WARN|ok, check, detail)


def check(name, fn, warn_only=False):
    try:
        detail = fn() or ""
        results.append(("ok", name, str(detail)))
    except Exception as e:  # noqa: BLE001  (every failure is a result here)
        results.append(("WARN" if warn_only else "FAIL", name, f"{type(e).__name__}: {e}"))


def python_version():
    v = sys.version_info
    assert v >= (3, 10), f"Python {v.major}.{v.minor} is older than 3.10"
    return f"{v.major}.{v.minor}.{v.micro} at {sys.executable}"


def packages():
    import numpy  # noqa: F401
    import PIL
    import websocket  # noqa: F401
    if sys.version_info < (3, 11):
        import tomli  # noqa: F401
    return f"pillow {PIL.__version__}, numpy {numpy.__version__}"


def import_all():
    import pccomfy
    bad = []
    for m in pkgutil.iter_modules(pccomfy.__path__):
        try:
            importlib.import_module(f"pccomfy.{m.name}")
        except Exception as e:  # noqa: BLE001
            bad.append(f"{m.name} ({type(e).__name__}: {e})")
    assert not bad, "; ".join(bad)
    return f"{len(list(pkgutil.iter_modules(pccomfy.__path__)))} modules"


def config_and_data():
    from pccomfy import config
    cfg = config.load(None)
    assert cfg.get("photocraft") and cfg.get("comfyui") is not None, "config has no photocraft/comfyui part"
    with tempfile.NamedTemporaryFile(dir=ROOT / "data", delete=True):
        pass
    return "config loads, data folder writable"


def tk_window():
    import tkinter
    from pccomfy import fonts
    fonts.load()
    root = tkinter.Tk()
    try:
        root.geometry("333x200")
        tkinter.Label(root, text="Größe · ÄÖÜ ß ×").pack()
        root.update()
        return f"Tk {root.tk.call('info', 'patchlevel')}"
    finally:
        root.destroy()


def inter_font():
    import tkinter
    import tkinter.font
    from pccomfy import fonts
    fonts.load()
    root = tkinter.Tk()
    try:
        fams = set(tkinter.font.families(root))
    finally:
        root.destroy()
    assert "Inter" in fams, "Inter is not among Tk's fonts (the window falls back to another font)"
    return "Inter available"


def drag_and_drop():
    from tkinterdnd2 import TkinterDnD
    root = TkinterDnD.Tk()
    try:
        return f"tkdnd {root.tk.call('package', 'require', 'tkdnd')}"
    finally:
        root.destroy()


def python_txt():
    """Windows: setup-windows.bat writes the Python it chose to data\\python.txt (cmd's code page); autostart.py reads it as UTF-8."""
    p = ROOT / "data" / "python.txt"
    assert p.is_file(), f"{p} is missing"
    text = p.read_bytes().decode("utf-8").strip()       # strict: a folder name with umlauts in another code page fails here
    assert Path(text).is_file(), f"the Python in python.txt does not exist: {text!r}"
    return text


def shortcut():
    from pccomfy.appname import APP_NAME
    if sys.platform == "win32":
        desk = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetFolderPath('Desktop')"],
                              capture_output=True, text=True, timeout=60).stdout.strip()
        path = Path(desk) / f"{APP_NAME}.lnk"
    else:
        path = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser() / "applications" / "photocraft-ai.desktop"
    assert path.is_file(), f"{path} is missing"
    return str(path)


def main(argv):
    check("Python", python_version)
    check("Packages", packages)
    check("All plugin modules import", import_all)
    check("Config and data folder", config_and_data)
    if sys.platform == "win32":
        check("data\\python.txt readable (UTF-8)", python_txt)
    check("Tk window opens", tk_window)
    check("Inter font", inter_font, warn_only=True)
    check("Drag and drop (tkinterdnd2)", drag_and_drop, warn_only=True)
    if "--expect-shortcut" in argv:
        check("Shortcut / menu entry", shortcut)
    lines = [f"{s:4}  {n}: {d}" for s, n, d in results]
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("| | check | detail |\n|---|---|---|\n")
            f.writelines(f"| {s} | {n} | {d.replace('|', '/')} |\n" for s, n, d in results)
    failed = sum(s == "FAIL" for s, _, _ in results)
    print(f"\n{len(results) - failed} of {len(results)} install checks passed" + (f", {failed} FAILED" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
