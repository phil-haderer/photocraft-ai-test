"""The window font: Inter, the font of PhotoCraft itself, shipped in pccomfy/assets/fonts (SIL OFL 1.1, OFL-Inter.txt).

Tk cannot open a font file. On Windows AddFontResourceExW with FR_PRIVATE adds the files for this process only (no
installation, no admin rights); it must run before Tk asks for its first font. When that fails (another system, a
missing file), the window keeps Segoe UI. On Linux the files go into the process's own fontconfig; that needs a Tk with Xft
(the Python of the distribution, python3-tk; the Tk inside uv's standalone Python has only X core fonts and shows "fixed").
"""
from __future__ import annotations

import os
from pathlib import Path

from .hostos import IS_LINUX, IS_WINDOWS

DIR = Path(__file__).resolve().parent / "assets" / "fonts"
FILES = ("Inter-Regular.ttf", "Inter-SemiBold.ttf")    # family "Inter" and "Inter SemiBold" (our bold)
FR_PRIVATE = 0x10


def _load_fontconfig() -> bool:
    """Linux: add the files to this process's own fontconfig (FcConfigAppFontAddFile), the counterpart of FR_PRIVATE: nothing is
    installed and no other program sees them. Tk draws through Xft, which asks fontconfig."""
    try:
        import ctypes
        import ctypes.util
        lib = ctypes.CDLL(ctypes.util.find_library("fontconfig") or "libfontconfig.so.1")
        add = lib.FcConfigAppFontAddFile
        add.argtypes = (ctypes.c_void_p, ctypes.c_char_p)
        add.restype = ctypes.c_int
        return all((DIR / f).exists() and add(None, str(DIR / f).encode()) for f in FILES)
    except Exception:
        return False


def load() -> bool:
    """Add the Inter files for this process; True when all of them were added."""
    if os.environ.get("PCCOMFY_NO_INTER") or not (IS_WINDOWS or IS_LINUX):
        return False
    if IS_LINUX:
        return _load_fontconfig()
    try:
        import ctypes
        add = ctypes.windll.gdi32.AddFontResourceExW
        add.argtypes = (ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p)
        return all((DIR / f).exists() and add(str(DIR / f), FR_PRIVATE, None) > 0 for f in FILES)
    except Exception:
        return False
