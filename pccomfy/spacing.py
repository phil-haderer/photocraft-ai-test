"""The gaps between the controls (padx / pady of pack and grid, the ``padding`` of ttk styles) follow the interface scale in
the same proportion as the text (user 4.11.).

Tk counts a plain number in pixels, so the gaps did not grow with the display scale while the fonts did: at 100 % (Linux) the
window looked looser than on Windows at 175 %, the scale the look was made at. Now every gap is multiplied by ``scale / REF``,
with REF = 1.75: at the reference nothing changes, at 100 % the gaps are 57 % of the old ones, so the proportions stay.

``install(factor)`` patches pack, grid and ttk.Style.configure / map once; the factor is read at each call. A value that
is already scaled (``Keep``, made by ``App._keep``) is left alone.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

REF = 1.75                 # the interface scale whose proportions the gaps keep (Windows at 175 %, plugin at 100 %)
_factor = 1.0
_installed = False
PAD_KEYS = ("padx", "pady")


class Keep(int):
    """A gap that is already in final pixels (``_px``): not scaled again."""


def scale(v):
    """One gap, or a tuple / list of gaps, scaled; whatever is not a number stays as it is."""
    if isinstance(v, Keep) or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v if v <= 0 else max(1, round(v * _factor))
    if isinstance(v, (tuple, list)):
        return type(v)(scale(x) for x in v)
    return v


def _pads(kw: dict) -> dict:
    return {k: (scale(v) if k in PAD_KEYS else v) for k, v in kw.items()}


def _wrap_layout(orig):
    def wrapper(self, cnf={}, **kw):                 # noqa: B006 (the signature of tkinter's own)
        if isinstance(cnf, dict):
            cnf = _pads(cnf)
        return orig(self, cnf, **_pads(kw))
    wrapper.__wrapped__ = orig
    return wrapper


def _wrap_style(orig, state_lists: bool):
    def wrapper(self, style, *args, **kw):
        if "padding" in kw:
            if state_lists:                          # map: [("selected", (14, 4)), ...]
                kw["padding"] = [(*item[:-1], scale(item[-1])) for item in kw["padding"]]
            else:
                kw["padding"] = scale(kw["padding"])
        return orig(self, style, *args, **kw)
    wrapper.__wrapped__ = orig
    return wrapper


def install(factor: float) -> None:
    """Sets the factor (``scale / REF``) and, the first time, patches tkinter."""
    global _factor, _installed
    _factor = max(0.2, float(factor))
    if _installed:
        return
    _installed = True
    for cls, names in ((getattr(tk, "Pack", None), ("pack_configure", "pack")), (getattr(tk, "Grid", None), ("grid_configure", "grid"))):
        if cls is None:                              # a test's stand-in for tkinter has neither
            continue
        patched = _wrap_layout(getattr(cls, names[0]))
        for n in names:
            setattr(cls, n, patched)
    style = getattr(ttk, "Style", None)
    if style is not None and hasattr(style, "configure") and hasattr(style, "map"):
        style.configure = _wrap_style(style.configure, False)
        style.map = _wrap_style(style.map, True)
