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


def _num(v):
    """'2.2.6' -> (2, 2, 6); a part with letters counts with its leading digits and ends it ('13.0.0rc1' -> (13, 0, 0))."""
    import re
    out = []
    for part in v.split("."):
        m = re.match(r"\d+", part)
        if not m:
            break
        out.append(int(m.group()))
        if m.group() != part:
            break
    return tuple(out)


def requirements_met():
    """Every line of requirements.txt that applies here is installed in at least that version (pip honoured the file)."""
    from importlib.metadata import PackageNotFoundError, version
    seen, bad = [], []
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        spec, _, marker = line.partition(";")
        if "python_version" in marker:                           # only the form requirements.txt uses: python_version < "3.11"
            assert "<" in marker and ">" not in marker and "=" not in marker, f"unknown marker: {marker}"
            want_py = _num(marker.split("<", 1)[1].strip().strip("'\""))
            if not sys.version_info[:2] < want_py:
                continue
        name, _, low = spec.partition(">=")
        name, low = name.strip(), low.strip()
        try:
            have = version(name)
        except PackageNotFoundError:
            bad.append(f"{name} missing")
            continue
        seen.append(f"{name} {have}")
        if _num(have) < _num(low):
            bad.append(f"{name} {have} < {low}")
    assert not bad, "; ".join(bad)
    return ", ".join(seen)


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
    probe = config.CONFIG_DIR / "ci-smoke.json"          # data\ (Windows) or ~/.config/pccomfy (Linux); made on the first write
    assert config._write_json(probe, {"ok": True}), config.write_error()
    probe.unlink()
    return f"config loads, {config.CONFIG_DIR} writable"


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
    try:
        root = TkinterDnD.Tk()
    except RuntimeError as e:
        raise RuntimeError(f"{e} Reason: {_tkdnd_reason()}") from None
    try:
        return f"tkdnd {root.tk.call('package', 'require', 'tkdnd')}"
    finally:
        root.destroy()


def _tkdnd_reason():
    """tkinterdnd2 hides Tcl's message ("Unable to load tkdnd library."); ask Tcl again for the real one. On Linux it is
    usually a missing system library: tkdnd needs libX11 and libXcursor (8.11.: missing in the minimal containers)."""
    import tkinter
    import tkinterdnd2
    root = tkinter.Tk()
    try:
        tcl9 = int(root.tk.call("info", "tclversion").split(".")[0]) >= 9
        base = Path(tkinterdnd2.__file__).parent / "tkdnd"
        import platform
        system, machine = platform.system(), os.environ.get("PROCESSOR_ARCHITECTURE", platform.machine())
        rep = {("Linux", "x86_64"): "linux-x64", ("Linux", "aarch64"): "linux-arm64", ("Windows", "AMD64"): "win-x64",
               ("Windows", "ARM64"): "win-arm64", ("Darwin", "arm64"): "osx-arm64", ("Darwin", "x86_64"): "osx-x64"}.get((system, machine))
        if not rep:
            return f"no tkdnd build for {system} {machine}"
        d = base / (rep + "-tcl9") if tcl9 and (base / (rep + "-tcl9")).is_dir() else base / rep
        root.tk.call("lappend", "auto_path", str(d))
        return root.tk.eval("if {[catch {package require tkdnd} msg]} {set msg} else {set msg ok}")
    except Exception as e:  # noqa: BLE001
        return f"(no reason found: {e})"
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
    check("requirements.txt met", requirements_met)
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
