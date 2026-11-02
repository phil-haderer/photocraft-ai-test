"""Display scale of the window on Linux (PLAN.md 18c, etappe c). No Tk here.

Windows is DPI aware and Tk follows it, so nothing is done there. On Linux Tk often reports 96 dpi on a scaled display
(WSLg: 200 % panel, ``winfo_fpixels("1i") == 96``), so the window came out far too small. The scale is taken from the first
source that names one:

1. the environment variable ``PCCOMFY_SCALE``
2. ``[window] scale`` in config.toml
3. PhotoCraft's own scale (so the plugin matches PhotoCraft): ``window.pixelsPerPoint`` of ``ui.inspect`` through the control
   port (1.5 at its interface scale of 150 %, measured with PhotoCraft 0.19 on Linux); ``interface.uiScale`` is the fallback
4. ``Xft.dpi`` of the X server (xrdb), when Tk does not already follow it

A value is a factor ("1.5") or a percent ("150", "150%"). Nothing found: Tk's own value stays.
"""
from __future__ import annotations

import re
import subprocess

TK_BASE = 96 / 72          # Tk's scaling (pixels per point) at a scale of 1
MIN_SCALE, MAX_SCALE = 0.5, 4.0


def parse_scale(value) -> float | None:
    """A scale factor from 1.5, "1.5", 150, "150" or "150%"; None when it is none (or out of 0.5 .. 4)."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        v = float(str(value).strip().rstrip("%"))
    except ValueError:
        return None
    if v >= 10:
        v /= 100
    return v if MIN_SCALE <= v <= MAX_SCALE else None


def find_ui_scale(obj) -> float | None:
    """PhotoCraft's scale in the answer of ``ui.inspect``: ``window.pixelsPerPoint`` (the real one), else ``interface.uiScale``
    somewhere in it (the exact shape of the second is not fixed here)."""
    if isinstance(obj, dict):
        win = obj.get("window")
        if isinstance(win, dict):
            found = parse_scale(win.get("pixelsPerPoint"))
            if found:
                return found
        for key, val in obj.items():
            if key in ("uiScale", "interface.uiScale"):
                found = parse_scale(val)
                if found:
                    return found
        if obj.get("path") == "interface.uiScale":
            found = parse_scale(obj.get("value"))
            if found:
                return found
        for val in obj.values():
            found = find_ui_scale(val)
            if found:
                return found
    elif isinstance(obj, list):
        for val in obj:
            found = find_ui_scale(val)
            if found:
                return found
    return None


def xft_dpi(xrdb_text: str) -> float | None:
    """The value of ``Xft.dpi`` in the output of ``xrdb -query``."""
    m = re.search(r"^Xft\.dpi:\s*([0-9.]+)", xrdb_text or "", re.M)
    try:
        return float(m.group(1)) if m else None
    except ValueError:
        return None


def pick_scale(env_value, config_value, photocraft_value) -> float | None:
    """The first of the three explicit sources that holds a usable scale."""
    for v in (env_value, config_value, photocraft_value):
        s = parse_scale(v)
        if s:
            return s
    return None


def tk_scaling(scale: float) -> float:
    return TK_BASE * scale


def _read_xrdb() -> str:
    try:
        return subprocess.run(["xrdb", "-query"], capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _photocraft_scale(pc) -> float | None:
    try:
        return find_ui_scale(pc.call("ui.inspect"))
    except Exception:
        return None


def detect(env: dict, cfg: dict, pc, current_dpi: float) -> float | None:
    """The scale to set, or None to leave Tk's own value. ``current_dpi`` is what Tk reports now (``winfo_fpixels("1i")``)."""
    picked = pick_scale(env.get("PCCOMFY_SCALE"), (cfg.get("window") or {}).get("scale"), _photocraft_scale(pc))
    if picked:
        return picked
    dpi = xft_dpi(_read_xrdb())
    if dpi and abs(dpi - current_dpi) > 1:
        return parse_scale(dpi / 96)
    return None
