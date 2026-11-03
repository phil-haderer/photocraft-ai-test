"""Display scale of the window on Linux (PLAN.md 18c, etappe c). No Tk here.

Windows is DPI aware and Tk follows it, so nothing is done there. On Linux Tk often reports 96 dpi on a scaled display
(WSLg: 200 % panel, ``winfo_fpixels("1i") == 96``), so the window came out far too small. The scale is taken from the first
source that names one:

1. the environment variable ``PCCOMFY_SCALE``
2. "Interface scale" in the plugin's Other settings (``ui_scale`` in settings.json; "auto" = not set)
3. ``[window] scale`` in config.toml
4. PhotoCraft's own scale (so the plugin matches PhotoCraft): ``window.pixelsPerPoint`` of ``ui.inspect`` through the control
   port (1.5 at its interface scale of 150 %, measured with PhotoCraft 0.19 on Linux); ``interface.uiScale`` is the fallback
5. the desktop: ``GDK_SCALE`` or ``QT_SCALE_FACTOR`` (set by the user for X11 programs), then GNOME's text scaling factor
   (``gsettings``). GNOME's whole-screen ``scaling-factor`` is not used on purpose: the compositor already enlarges X11
   programs by it, so using it too would count it twice.
6. ``Xft.dpi`` of the X server (xrdb), when Tk does not already follow it

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


def pick_scale(*values) -> float | None:
    """The first of the explicit sources (in order) that holds a usable scale."""
    for v in values:
        s = parse_scale(v)
        if s:
            return s
    return None


def _read_gsettings() -> str:
    try:
        return subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "text-scaling-factor"],
                              capture_output=True, text=True, timeout=2).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def gnome_text_scale(gsettings_text: str) -> float | None:
    """GNOME's text scaling factor from ``gsettings get ... text-scaling-factor`` ("1.25" or "double 1.25"); 1.0 counts as none."""
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*$", (gsettings_text or "").strip())
    v = parse_scale(m.group(1)) if m else None
    return v if v and abs(v - 1.0) > 0.01 else None


def desktop_scale(env: dict) -> tuple[float | None, str]:
    """(scale, name of the source) from the user's own environment variables or GNOME's text scaling; (None, "") if none."""
    for key in ("GDK_SCALE", "QT_SCALE_FACTOR"):
        v = parse_scale(env.get(key))
        if v and abs(v - 1.0) > 0.01:
            return v, key
    v = gnome_text_scale(_read_gsettings())
    return (v, "GNOME text scaling") if v else (None, "")


def sources(env: dict, cfg: dict, pc, setting=None) -> list[tuple[str, float | None]]:
    """Every source in order of use with the scale it names (None = names none). The first with a value is used (``detect``)."""
    dpi = xft_dpi(_read_xrdb())
    ds, dname = desktop_scale(env)
    return [
        ("PCCOMFY_SCALE", parse_scale(env.get("PCCOMFY_SCALE"))),
        ("Other settings (Interface scale)", parse_scale(setting)),
        ("config.toml [window] scale", parse_scale((cfg.get("window") or {}).get("scale"))),
        ("PhotoCraft", _photocraft_scale(pc)),
        (dname or "GDK_SCALE / QT_SCALE_FACTOR / GNOME text scaling", ds),
        ("Xft.dpi", parse_scale(dpi / 96) if dpi else None),
    ]


def detect(env: dict, cfg: dict, pc, current_dpi: float, setting=None) -> float | None:
    """The scale to set, or None to leave Tk's own value. ``current_dpi`` is what Tk reports now (``winfo_fpixels("1i")``).
    ``setting``: the Interface scale of Other settings (``ui_scale`` in settings.json)."""
    picked = pick_scale(env.get("PCCOMFY_SCALE"), setting, (cfg.get("window") or {}).get("scale"), _photocraft_scale(pc))
    if picked:
        return picked
    ds, _name = desktop_scale(env)
    if ds:
        return ds
    dpi = xft_dpi(_read_xrdb())
    if dpi and abs(dpi - current_dpi) > 1:
        return parse_scale(dpi / 96)
    return None


def report(env: dict, cfg: dict, pc, current_dpi: float, setting=None) -> str:
    """Text for ``python -m pccomfy scale``: what each source says and what the plugin will use."""
    lines = [f"Tk reports {current_dpi:.0f} dpi.", "Sources, first with a value wins:"]
    for name, val in sources(env, cfg, pc, setting):
        lines.append(f"  {name:<46} {('%g' % val) if val else '-'}")
    lines.append(f"Used: {detect(env, cfg, pc, current_dpi, setting) or 'none (Tk keeps its own value)'}")
    return "\n".join(lines)
