"""Pins what each system gets (PLAN.md 18c): the Windows values must never change by accident while the Linux port grows.

Run on Windows and on Linux: each system checks its own column. The Windows column is what always ran.

    python tests/test_platform_pins.py
"""
import os
import sys
from pathlib import Path

os.environ.pop("PCCOMFY_HOME", None)    # the pins are about the defaults
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import comfydir, config, fonts, hostos, launcher, winlink  # noqa: E402

ROOT = Path(config.__file__).resolve().parent.parent


def main():
    assert hostos.IS_WINDOWS == (os.name == "nt")
    assert hostos.IS_LINUX == sys.platform.startswith("linux")
    assert hostos.IS_WINDOWS != hostos.IS_LINUX
    assert winlink.available() == (sys.platform == "win32")

    # Inter is loaded on Windows (gdi32) and Linux (fontconfig); PCCOMFY_NO_INTER switches it off everywhere
    os.environ["PCCOMFY_NO_INTER"] = "1"
    assert fonts.load() is False
    del os.environ["PCCOMFY_NO_INTER"]
    if hostos.IS_LINUX:                          # fontconfig of this process (no Tk needed for the call itself)
        import ctypes.util
        assert fonts.load() is bool(ctypes.util.find_library("fontconfig"))

    # ComfyUI folder detection by process: only for a local server, and for now only on Windows
    assert comfydir.find_root("http://example.com:8188") is None

    # window arguments: Windows gets none and keeps its own resize cursor; elsewhere a WM_CLASS and an X11 cursor
    if hostos.IS_WINDOWS:
        assert hostos.ROOT_KW == {} and hostos.TOP_KW == {}
        assert hostos.GRIP_CURSOR == "size_nw_se"
    else:
        assert hostos.ROOT_KW == {"className": "pccomfy"} and hostos.TOP_KW == {"class_": "Pccomfy"}
        assert hostos.GRIP_CURSOR == "bottom_right_corner"

    if hostos.IS_WINDOWS:
        assert config._config_dir() == ROOT / "data"
        assert config.EXCHANGE_DIR == config.CONFIG_DIR / "exchange"
        assert config.DEFAULTS["photocraft"]["port"] == 7878
        assert config.DEFAULTS["comfyui"]["url"] == "http://127.0.0.1:8188"
    else:
        assert config._config_dir() == Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "pccomfy"

    # the PhotoCraft binary: photocraft.exe on Windows (found by the old search), photocraft elsewhere; the Linux starter exists
    assert launcher.exe_name() == ("photocraft.exe" if hostos.IS_WINDOWS else "photocraft")
    assert (ROOT / "photocraft-ai.sh").read_text(encoding="utf-8").startswith("#!/usr/bin/env bash")

    # the shipped workflows are the default on every system, and they are really there
    assert config.WORKFLOWS_DIR == ROOT / "workflows"
    assert any(config.WORKFLOWS_DIR.glob("*.json"))

    print("platform pins ok:", "windows" if hostos.IS_WINDOWS else "linux")


if __name__ == "__main__":
    main()
