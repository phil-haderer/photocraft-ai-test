"""Tip of the day: the tips file, the choice without repeats, the saved tick, and the popup in a real (hidden) Tk window.
The window part is skipped when Tk cannot open a window.

    python tests/test_tips.py
"""
import os
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-tips-")
os.environ["PCCOMFY_NO_TIPS"] = "1"
sys.path.insert(0, str(ROOT))

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui_tips  # noqa: E402
from pccomfy.tips import TIPS  # noqa: E402


def logic():
    assert len(TIPS) == 25 and all(isinstance(t, str) and t.strip() for t in TIPS) and len(set(TIPS)) == 25
    # tips removed on 3.11. (user): the shown list keeps the tips' ids, an old list of numbers still counts
    for gone in ("disk icon", "Mask density", "value box", "no <obj_1>", "\"x1\"", "Hover a function button", "LLM button"):
        assert not [t for t in TIPS if gone in t], gone
    ids = [gui_tips.tip_id(t) for t in TIPS]
    assert len(set(ids)) == len(ids) and len(gui_tips.LEGACY_IDS) == 31
    fill = TIPS.index(next(t for t in TIPS if t.startswith("Fill Selection")))
    assert gui_tips.shown_indices([0, 10, 99, True, "x"]) == [fill]          # old 0 = Fill; old 10 = Mask density, removed
    assert gui_tips.shown_indices([ids[3], ids[3], 0]) == [3, fill]
    assert gui_tips.shown_indices(None) == [] and gui_tips.shown_indices({}) == []
    cfgmod.set_setting(gui_tips.SHOWN_KEY, [0])
    i = gui_tips.next_tip(rng=random.Random(2))
    assert i != fill and cfgmod.get_setting(gui_tips.SHOWN_KEY) == [ids[fill], ids[i]]
    # the very first start shows no tip; it leaves an empty list, so the next start does
    cfgmod.set_setting(gui_tips.SHOWN_KEY, None)
    assert gui_tips.first_start() and cfgmod.get_setting(gui_tips.SHOWN_KEY) == []
    assert not gui_tips.first_start()
    cfgmod.set_setting(gui_tips.SHOWN_KEY, None)
    rng = random.Random(1)
    shown, seen = [], []
    for _ in range(30):                                     # a whole round: every tip exactly once
        i, shown = gui_tips.pick_tip(30, shown, rng)
        seen.append(i)
    assert sorted(seen) == list(range(30)), seen
    i, shown = gui_tips.pick_tip(30, shown, rng)            # then a new round; the last tip is not first again
    assert shown == [i] and i != seen[-1]
    # broken state is repaired, not fatal
    for bad in (None, "x", [99, -1, True, "a"], {}):
        i, new = gui_tips.pick_tip(30, bad, rng)
        assert 0 <= i < 30 and new == [i], (bad, i, new)
    assert gui_tips.pick_tip(1, [0], rng) == (0, [0])
    # the tick and the shown list live in settings.json
    assert not gui_tips.tips_hidden()
    cfgmod.set_setting(gui_tips.HIDE_KEY, True)
    assert gui_tips.tips_hidden()
    cfgmod.set_setting(gui_tips.HIDE_KEY, None)
    assert not gui_tips.tips_hidden()
    assert gui_tips.HIDE_TEXT == "Don’t show tips at startup"


def window():
    try:
        import tkinter
        tkinter.Tk().destroy()
    except Exception as e:
        print(f"window part SKIPPED (no Tk window: {e})")
        return
    from pccomfy import gui
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    app.root.update()
    assert getattr(app, "_tip_win", None) is None            # PCCOMFY_NO_TIPS: nothing at start

    cfgmod.set_setting(gui_tips.SHOWN_KEY, None)
    app.root.deiconify()
    app.root.update()
    app._show_tip_popup()                                    # the very first start: no popup (user 3.11.)
    assert getattr(app, "_tip_win", None) is None and cfgmod.get_setting(gui_tips.SHOWN_KEY) == []
    app._show_tip_popup()
    app.root.update()
    win = app._tip_win
    assert win is not None and win.winfo_exists()
    assert win.wm_overrideredirect()                         # no title bar
    x, _ = app._tip_position(300, 200)                       # inside the screen, and beside (not on) the plugin when there is room
    sw = app.root.winfo_vrootx() + app.root.winfo_vrootwidth()
    assert 0 <= x and x + 300 <= sw
    rl, rr = app.root.winfo_rootx(), app.root.winfo_rootx() + app.root.winfo_width()
    if sw - rr >= 308 or rl >= 308:
        assert x >= rr or x + 300 <= rl
    btn = max(rb.winfo_reqheight() for rb in app.rb_modes.values())
    assert app._tip_gap() >= max(btn, 8) > 0                 # the room between plugin and popup: as high as a function button (user 4.11.)
    if sw - rr >= 300 + app._tip_gap():
        assert x - rr >= btn
    assert bool(win.attributes("-topmost")) == (bool(app.v_top.get()) and not gui_tips.winlink.available())   # like the plugin
    shown = cfgmod.get_setting(gui_tips.SHOWN_KEY)
    assert isinstance(shown, list) and len(shown) == 1
    app._show_tip_popup()                                    # no second popup while one is open
    assert app._tip_win is win

    # the arrows browse the tips (user 2.11.): back is greyed on the first one; next shows a new tip, back the one before
    first = app._tip_label.cget("text")
    assert str(app._tip_back.cget("state")) == "disabled"
    app._tip_step(1)
    second = app._tip_label.cget("text")
    assert second != first and str(app._tip_back.cget("state")) == "normal"
    assert len(cfgmod.get_setting(gui_tips.SHOWN_KEY)) == 2
    app._tip_step(-1)
    assert app._tip_label.cget("text") == first and str(app._tip_back.cget("state")) == "disabled"
    app._tip_step(-1)                                        # before the first: nothing happens
    assert app._tip_label.cget("text") == first
    app._tip_step(1)
    assert app._tip_label.cget("text") == second and len(cfgmod.get_setting(gui_tips.SHOWN_KEY)) == 2     # no new tip counted

    kids = list(_walk(win))
    next(w for w in kids if w.winfo_class() == "TCheckbutton").invoke()     # the tick in the popup is saved at once
    assert gui_tips.tips_hidden()
    next(w for w in kids if w.winfo_class() == "TButton").invoke()          # OK closes
    app.root.update()
    assert app._tip_win is None

    app._show_tip_popup()                                    # tips are off: no popup
    assert app._tip_win is None

    row = app._tips_setting_row(app.root)                    # the same tick in the settings window
    assert app._tips_setting_var.get() is True
    row.invoke()
    assert not gui_tips.tips_hidden() and cfgmod.get_setting(gui_tips.HIDE_KEY) is None
    app._show_tip_popup()                                    # on again: the popup appears
    assert app._tip_win is not None
    app._tip_win.destroy()
    app._tip_win = None

    app.root.withdraw()                                      # hidden window (no title bar, so no iconify): no popup
    app.root.update()
    app._show_tip_popup()
    assert app._tip_win is None
    app.root.destroy()


def _walk(w):
    yield w
    for c in w.winfo_children():
        yield from _walk(c)


if __name__ == "__main__":
    logic()
    window()
    print("OK test_tips")
