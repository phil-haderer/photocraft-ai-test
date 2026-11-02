"""Images on the clipboard: read (Ctrl+V in a slot, Multi Image Edit) and write (Copy canvas to clip). Windows through ctypes;
Linux through wl-clipboard (Wayland) or xclip (X11), run as programs (see "the Linux part").

Pillow is already a dependency; the Windows calls use ctypes, like winlink.py. Everything that does not touch Windows is
pure (`pick_image_file`, `dib_from_image`, `png_from_image`, `image_from_bytes`) and is tested on any system. The two
functions that really talk to the clipboard (`_win_read_raw`, `_win_write`) are tiny so the tests can replace them.

Writing puts two formats on the clipboard: "PNG" (keeps transparency; Photoshop, browsers and most editors read it) and
CF_DIB (flat, understood by every Windows program; transparent areas become white). Reading prefers PNG, then DIB, then
whatever Pillow's ImageGrab finds (a picture, or files copied in Explorer).
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff")
CF_DIB = 8
GMEM_MOVEABLE = 0x0002
PNG_FORMAT = "PNG"          # the registered clipboard format name that carries real PNG files
DEFAULT_FORMATS = ("png", "dib")


def available() -> bool:
    return sys.platform == "win32" or _linux_backend() is not None


# What the window says when there is no clipboard to talk to.
UNAVAILABLE_TEXT = ("Pasting from the clipboard needs wl-clipboard (Wayland) or xclip (X11); install one of them."
                    if sys.platform.startswith("linux") else "Pasting from the clipboard works on Windows only.")


# ---------- pure helpers ----------

def pick_image_file(paths) -> Path | None:
    """The first path that looks like a picture (files copied in Explorer arrive as a list of paths)."""
    for p in paths or ():
        p = Path(str(p))
        if p.suffix.lower() in IMAGE_SUFFIXES and p.is_file():
            return p
    return None


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)


def flatten(img: Image.Image, background=(255, 255, 255)) -> Image.Image:
    """RGB copy; transparent areas show `background` (CF_DIB has no usable alpha)."""
    if _has_alpha(img):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, background)
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    return img.convert("RGB")


def dib_from_image(img: Image.Image) -> bytes:
    """The bytes of CF_DIB: a BMP file without its 14-byte file header (starts with BITMAPINFOHEADER)."""
    buf = io.BytesIO()
    flatten(img).save(buf, "BMP")
    return buf.getvalue()[14:]


def png_from_image(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    (img.convert("RGBA") if _has_alpha(img) else img.convert("RGB")).save(buf, "PNG")
    return buf.getvalue()


def image_from_bytes(data: bytes) -> Image.Image | None:
    """PNG bytes or DIB bytes (Pillow reads both) -> a loaded image, or None if it is not a picture."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
        return img
    except Exception:
        return None


# ---------- the Windows part ----------

_API = None


def _api():
    """ctypes, user32, kernel32 with argument types set (without them 64-bit handles get cut to 32 bit)."""
    global _API
    if _API is None:
        import ctypes
        from ctypes import wintypes
        user32, kernel32, vp = ctypes.windll.user32, ctypes.windll.kernel32, ctypes.c_void_p
        user32.OpenClipboard.argtypes, user32.OpenClipboard.restype = [vp], wintypes.BOOL
        user32.CloseClipboard.argtypes, user32.CloseClipboard.restype = [], wintypes.BOOL
        user32.EmptyClipboard.argtypes, user32.EmptyClipboard.restype = [], wintypes.BOOL
        user32.SetClipboardData.argtypes, user32.SetClipboardData.restype = [wintypes.UINT, vp], vp
        user32.GetClipboardData.argtypes, user32.GetClipboardData.restype = [wintypes.UINT], vp
        user32.IsClipboardFormatAvailable.argtypes, user32.IsClipboardFormatAvailable.restype = [wintypes.UINT], wintypes.BOOL
        user32.RegisterClipboardFormatW.argtypes, user32.RegisterClipboardFormatW.restype = [wintypes.LPCWSTR], wintypes.UINT
        user32.CreateWindowExA.argtypes = [wintypes.DWORD, wintypes.LPCSTR, wintypes.LPCSTR, wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                           ctypes.c_int, ctypes.c_int, vp, vp, vp, vp]
        user32.CreateWindowExA.restype = vp
        user32.DestroyWindow.argtypes, user32.DestroyWindow.restype = [vp], wintypes.BOOL
        kernel32.GlobalAlloc.argtypes, kernel32.GlobalAlloc.restype = [wintypes.UINT, ctypes.c_size_t], vp
        kernel32.GlobalLock.argtypes, kernel32.GlobalLock.restype = [vp], vp
        kernel32.GlobalUnlock.argtypes, kernel32.GlobalUnlock.restype = [vp], wintypes.BOOL
        kernel32.GlobalSize.argtypes, kernel32.GlobalSize.restype = [vp], ctypes.c_size_t
        kernel32.GlobalFree.argtypes, kernel32.GlobalFree.restype = [vp], vp
        _API = (ctypes, user32, kernel32)
    return _API


def _open(user32, hwnd) -> bool:
    for _ in range(10):         # another program may hold the clipboard for a moment
        if user32.OpenClipboard(hwnd or None):
            return True
        time.sleep(0.02)
    return False


def _win_read_raw(hwnd=0):
    """('png' | 'dib', bytes) of the first of those formats on the clipboard, else None."""
    ctypes, user32, kernel32 = _api()
    if not _open(user32, hwnd):
        return None
    try:
        for name, fmt in (("png", user32.RegisterClipboardFormatW(PNG_FORMAT)), ("dib", CF_DIB)):
            if not user32.IsClipboardFormatAvailable(fmt):
                continue
            handle = user32.GetClipboardData(fmt)
            if not handle:
                continue
            size, ptr = kernel32.GlobalSize(handle), kernel32.GlobalLock(handle)
            if not ptr:
                continue
            try:
                return name, ctypes.string_at(ptr, size)
            finally:
                kernel32.GlobalUnlock(handle)
        return None
    finally:
        user32.CloseClipboard()


def _win_write(items, hwnd=0) -> bool:
    """items: [(format, bytes)], format = a number (CF_DIB) or a registered name ("PNG"). True if at least one was set.
    SetClipboardData needs a window that owns the clipboard: the caller's (Tk) window, or a hidden helper window."""
    ctypes, user32, kernel32 = _api()
    own = None
    if not hwnd:
        own = user32.CreateWindowExA(0, b"STATIC", None, 0, 0, 0, 0, 0, None, None, None, None)
        hwnd = own
    try:
        if not _open(user32, hwnd):
            return False
        try:
            user32.EmptyClipboard()
            ok = False
            for fmt, data in items:
                fid = fmt if isinstance(fmt, int) else user32.RegisterClipboardFormatW(fmt)
                handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                if not handle:
                    continue
                ptr = kernel32.GlobalLock(handle)
                if not ptr:
                    kernel32.GlobalFree(handle)
                    continue
                ctypes.memmove(ptr, data, len(data))
                kernel32.GlobalUnlock(handle)
                if user32.SetClipboardData(fid, handle):
                    ok = True                       # the clipboard owns the memory now
                else:
                    kernel32.GlobalFree(handle)
            return ok
        finally:
            user32.CloseClipboard()
    finally:
        if own:
            user32.DestroyWindow(own)


def _pillow_grab():
    """Fallback: Pillow's own reader. An Image, a list of file paths (copied in Explorer) or None."""
    from PIL import ImageGrab
    return ImageGrab.grabclipboard()


# ---------- the Linux part: wl-clipboard (Wayland) or xclip (X11), run as programs ----------

LINUX_TIMEOUT = 5
FILE_TARGETS = ("text/uri-list", "x-special/gnome-copied-files")      # files copied in a file manager


def _linux_backend() -> str | None:
    """"wl" on a Wayland session with wl-clipboard, "xclip" on X11 with xclip, else None (nothing to talk to)."""
    if not sys.platform.startswith("linux"):
        return None
    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-paste") and shutil.which("wl-copy"):
        return "wl"
    if os.environ.get("DISPLAY") and shutil.which("xclip"):
        return "xclip"
    return None


def pick_target(targets) -> tuple[str, str] | None:
    """('image', mime) for the best picture format on the clipboard (PNG first), ('files', mime) for copied files, else None."""
    mimes = [str(t).strip() for t in targets or () if str(t).strip()]
    images = [m for m in mimes if m.lower().startswith("image/")]
    if images:
        return "image", "image/png" if "image/png" in images else images[0]
    for m in FILE_TARGETS:
        if m in mimes:
            return "files", m
    return None


def paths_from_uri_list(text: str) -> list[Path]:
    """Paths from a text/uri-list (file:// lines; '#' comments and the 'copy'/'cut' line of gnome-copied-files are skipped)."""
    from urllib.parse import unquote, urlsplit
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.lower().startswith("file:"):
            continue
        parts = urlsplit(line)
        if parts.netloc in ("", "localhost"):
            out.append(Path(unquote(parts.path)))
    return out


def _linux_run(args, data: bytes | None = None) -> bytes | None:
    """stdout of a clipboard program, or None when it failed. With ``data`` the program's output is dropped: wl-copy and xclip
    stay in the background to serve the clipboard, and would keep a pipe open."""
    try:
        if data is None:
            done = subprocess.run(args, capture_output=True, timeout=LINUX_TIMEOUT)
            return done.stdout if done.returncode == 0 else None
        done = subprocess.run(args, input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=LINUX_TIMEOUT)
        return b"" if done.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def _linux_targets(backend: str) -> list[str]:
    cmd = ["wl-paste", "--list-types"] if backend == "wl" else ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"]
    out = _linux_run(cmd)
    return out.decode(errors="replace").split() if out else []


def _linux_read_raw(backend: str, mime: str) -> bytes | None:
    cmd = (["wl-paste", "--no-newline", "--type", mime] if backend == "wl"
           else ["xclip", "-selection", "clipboard", "-t", mime, "-o"])
    return _linux_run(cmd)


def _linux_write(backend: str, png: bytes) -> bool:
    cmd = ["wl-copy", "--type", "image/png"] if backend == "wl" else ["xclip", "-selection", "clipboard", "-t", "image/png", "-i"]
    return _linux_run(cmd, png) is not None


def _linux_read_image(backend: str) -> Image.Image | None:
    picked = pick_target(_linux_targets(backend))
    if picked is None:
        return None
    kind, mime = picked
    raw = _linux_read_raw(backend, mime)
    if not raw:
        return None
    if kind == "image":
        return image_from_bytes(raw)
    path = pick_image_file(paths_from_uri_list(raw.decode(errors="replace")))
    if path is None:
        return None
    with Image.open(path) as f:
        f.load()
        return f.copy()


# ---------- what the window calls ----------

def read_image(hwnd=0) -> Image.Image | None:
    """The picture on the clipboard (a copied image, a screenshot, or the first picture file copied in Explorer), else None."""
    if not available():
        return None
    backend = _linux_backend()
    if backend:
        try:
            return _linux_read_image(backend)
        except Exception:
            return None
    try:
        raw = _win_read_raw(hwnd)
        if raw:
            img = image_from_bytes(raw[1])
            if img is not None:
                return img
        got = _pillow_grab()
        if isinstance(got, Image.Image):
            return got
        path = pick_image_file(got) if got else None
        if path is not None:
            with Image.open(path) as f:
                f.load()
                return f.copy()
    except Exception:
        pass
    return None


def write_image(img: Image.Image, formats=DEFAULT_FORMATS, hwnd=0) -> bool:
    """Put the picture on the clipboard as "png" and/or "dib". False if there is no clipboard or nothing could be set."""
    if not available():
        return False
    backend = _linux_backend()
    if backend:                          # Linux: PNG only (keeps transparency; there is no flat DIB there)
        try:
            return _linux_write(backend, png_from_image(img))
        except Exception:
            return False
    try:
        items = []
        for f in formats:
            if f == "png":
                items.append((PNG_FORMAT, png_from_image(img)))
            elif f == "dib":
                items.append((CF_DIB, dib_from_image(img)))
            else:
                raise ValueError(f"unknown clipboard format {f!r}")
        return bool(items) and _win_write(items, hwnd)
    except ValueError:
        raise
    except Exception:
        return False
