"""The window on a small screen (user 3.11., 4.11.). The window never moves by itself: it stays where the user puts it and grows
downwards. Only when the content does not fit between its top edge and the screen's bottom the body scrolls (mouse
wheel or the thin bar), and opening Advanced settings scrolls them into view. Also the mouse wheel on Linux (Button-4/5).
Real Tk window (invisible), the monitor is simulated. Skipped when Tk cannot open a window.

    python tests/test_window_fits_screen.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-fit-")
os.environ["PCCOMFY_NO_TIPS"] = "1"
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    _r = tkinter.Tk()
    _r.destroy()
except Exception as e:                      # no display / no Tk
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui, models  # noqa: E402

HOME_Y = 300


def settle(app, s=0.6):
    end = time.time() + s
    while time.time() < end:
        app.root.update()
        time.sleep(0.02)


def stays_at(app, home, what):
    """Windows only: on Linux the window manager places the window and may do it after the test has measured (VM 4.11.: 283, then 337)."""
    if sys.platform == "win32":
        assert abs(app.root.winfo_rooty() - home) <= 1, (what, app.root.winfo_rooty(), home)


def visible_in_body(app, w) -> bool:
    cv = app.cv_body
    top, bot = cv.winfo_rooty(), cv.winfo_rooty() + cv.winfo_height()
    return top <= w.winfo_rooty() and w.winfo_rooty() + w.winfo_height() <= bot


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    try:
        app.root.attributes("-alpha", 0.0)
    except Exception:
        pass
    app.cb_workflow["values"] = [gui.BUILTIN] + sorted({w for m in models.MODELS for w in m.workflows()})
    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    app.root.geometry(f"+60+{HOME_Y}")
    settle(app)
    frame = app.root.winfo_rooty() - int(app.root.geometry().split("+")[2])     # a title bar (Linux), 0 without
    home = app.root.winfo_rooty()
    taskbar = app._px(56)

    # how tall the window is with Advanced open, measured on a screen that is big enough
    app._monitor_at = lambda x, y, work=False: (0, 0, 4000, 10 ** 5)
    app._toggle_advanced()
    settle(app)
    tall = app.root.winfo_height()
    app._toggle_advanced()
    settle(app)
    stays_at(app, home, "a big screen moves nothing")

    # 1. the screen reaches below the window's whole height: nothing moves, no scroll bar. Where the window does not fit between
    #    its top edge and the screen's bottom, the body scrolls (the window never moves and is never cut off: user 4.11., PC C)
    screen_h = tall + taskbar + home + 40
    app._monitor_at = lambda x, y, work=False: (0, 0, 4000, screen_h - (taskbar if work else 0))
    app._toggle_advanced()
    settle(app)
    stays_at(app, home, "the window stays where the user put it")
    assert not app.sb_body.shown, "the whole window fits below its top edge: no scroll bar"
    app._toggle_advanced()
    settle(app)
    screen_h = tall + taskbar + home // 2                              # fits from the top of the screen, not from the window's place
    app._monitor_at = lambda x, y, work=False: (0, 0, 4000, screen_h - (taskbar if work else 0))
    app._toggle_advanced()
    settle(app)
    stays_at(app, home, "it does not jump up to fit")
    assert app.sb_body.shown, "not enough room below the window's top edge: the body scrolls"
    assert app.root.winfo_rooty() + app.root.winfo_height() <= screen_h - taskbar + 1, "the window is not cut off at the bottom"
    assert visible_in_body(app, app.btn_adv), "the Advanced heading is in sight after opening"
    app._toggle_advanced()
    settle(app)

    # 2. closed again: same place
    app._toggle_advanced()
    settle(app)
    stays_at(app, home, "closed again: same place")

    # 3. a screen smaller than the window: it stays too, the body scrolls, opening Advanced scrolls them into view
    small = tall // 2 + taskbar + app._px(300)
    app._monitor_at = lambda x, y, work=False: (0, 0, 4000, small - (taskbar if work else 0))
    app._fit_height()
    settle(app)
    app._toggle_advanced()
    settle(app)
    assert app.sb_body.shown, "taller than the screen: the body scrolls"
    assert app.root.winfo_height() <= small - taskbar + 1, (app.root.winfo_height(), small - taskbar)
    assert app.root.winfo_rooty() + app.root.winfo_height() <= small - taskbar + 1, "not cut off at the bottom (it may move up for that)"
    app.root.geometry(f"+60+{HOME_Y}")
    settle(app)
    assert visible_in_body(app, app.btn_adv), "the Advanced heading is in sight after opening"

    # 3b. the window starts so low that not even a strip of the body fits above the work area: only then it moves up, just far
    #     enough (it never ends under the taskbar), and the body scrolls. A taller taskbar than the old guess of 56 px counts.
    app._toggle_advanced()
    settle(app)
    big_bar = app._px(140)
    app._monitor_at = lambda x, y, work=False: (0, 0, 4000, 10 ** 4 - (big_bar if work else 0))
    bottom = 10 ** 4 - big_bar
    app.root.geometry(f"+60+{bottom - app._px(250)}")
    settle(app)
    app._fit_height()
    settle(app)
    assert app.root.winfo_rooty() < bottom - app._px(250), "too low: it moved up"
    assert app.root.winfo_rooty() + app.root.winfo_height() <= bottom + 1, "and is not under the taskbar"
    assert app.sb_body.shown, "the body scrolls"
    app._monitor_at = lambda x, y, work=False: (0, 0, 4000, small - (taskbar if work else 0))      # the small screen again for the wheel
    app.root.geometry(f"+60+{HOME_Y}")
    settle(app)
    app._fit_height()
    settle(app)
    app._toggle_advanced()
    settle(app)

    # 4. the mouse wheel scrolls the body: Windows <MouseWheel> (delta), Linux Button-4 (up) and Button-5 (down)
    class Ev:
        def __init__(self, num=0, delta=0, widget=None):
            self.num, self.delta, self.widget = num, delta, widget or app.root
    assert gui.wheel_up(Ev(delta=120)) and not gui.wheel_up(Ev(delta=-120))
    assert gui.wheel_up(Ev(num=4)) and not gui.wheel_up(Ev(num=5))
    app.cv_body.yview_moveto(0)
    app.sb_body.wheel(Ev(num=5))
    settle(app, 0.2)
    assert app.cv_body.yview()[0] > 0, "wheel down (Button-5) scrolls the body"
    y1 = app.cv_body.yview()[0]
    app.sb_body.wheel(Ev(num=4))
    settle(app, 0.2)
    assert app.cv_body.yview()[0] < y1, "wheel up (Button-4) scrolls back"
    app.sb_body.wheel(Ev(delta=-120))
    settle(app, 0.2)
    assert app.cv_body.yview()[0] > 0, "Windows wheel down scrolls"
    app._toggle_advanced()
    settle(app)

    # "Original size" (user 4.11.): in the window for every function but Upscale / real Refine (Fibo Refine runs as Edit); Text to image starts with it on
    app._toggle_advanced()
    settle(app)
    for model, mode, wanted in (("qwen", "inpaint", True), ("qwen", "upscale", False), ("qwen", "refine", False),
                                ("fibo", "refine", False), ("flux3", "txt2img", True), ("flux3", "edit", True)):
        app.v_model.set(model)
        app.v_mode.set(mode)
        app._on_model()
        settle(app)
        assert app._native_wanted() is wanted, (model, mode)
        assert bool(app.f_native.winfo_manager()) is wanted, (model, mode)
        assert app.v_native.get() is True, (model, mode, app.v_native.get())        # on at every start (user 4.11.)
        assert float(app.v_native_mp.get()) == {"txt2img": 4.0, "outpaint": 1.0}.get(mode, 2.0), (model, mode, app.v_native_mp.get())
        assert str(app.w_native_mp.cget("state")) == ("normal" if (app.v_native.get() or mode == "txt2img") else "disabled")
        # the label follows the function: the whole canvas for Text to image, the area around the selection otherwise
        if wanted:
            # Text to image: no switch, a plain "Use canvas size up to" label; the others keep the "Original size, up to" switch
            assert bool(app.cb_native.winfo_manager()) is (mode != "txt2img"), (model, mode)
            assert bool(app.lbl_canvas.winfo_manager()) is (mode == "txt2img"), (model, mode)
            assert str(app.cb_native.cget("text")) == "Original size, up to"
            assert str(app.lbl_canvas.cget("text")) == "Use canvas size up to"
            assert all(("canvas" in t.text) == (mode == "txt2img") for t in app.tt_native), (model, mode)
    # "Send reference images in original size, up to N MP" (Multi Image Edit): on at every start with 2 MP for all models, the MP box follows the tick
    for model in ("flux3", "flux2", "qwen", "fibo"):
        app.v_model.set(model)
        app.v_mode.set("multi_edit")
        app._on_model()
        settle(app)
        assert app.v_ref_native.get() is True and float(app.v_ref_mp.get()) == 2.0, (model, app.v_ref_native.get(), app.v_ref_mp.get())
        assert str(app.w_refpx.cget("state")) == "normal" and str(app.cb_refsize.cget("text")) == "Send reference images in original size, up to"
        app.v_ref_native.set(False)
        assert str(app.w_refpx.cget("state")) == "disabled"
        app.v_ref_native.set(True)
        c = app._collect()
        assert c["ref_native"] is True and c["ref_mp"] == 2.0
    app.v_ref_native.set(True)
    app.v_ref_mp.set(3.5)
    req = app._request()
    assert req.ref_native is True and req.ref_mp == 3.5 and req.ref_side == (1536 if app.v_model.get() == "flux3" else 1024)
    app.v_ref_mp.set(9.0)
    assert app._request().ref_mp == 4.0                       # the highest value is 4 MP
    app.v_ref_mp.set(2.0)
    app.v_mode.set("txt2img")
    app._on_mode_ui()
    app.v_native.set(True)
    app.v_native_mp.set(6.5)
    assert app._collect()["native"] is True and app._collect()["native_mp"] == 6.5
    app._toggle_advanced()
    settle(app)

    app.root.destroy()

    # Interface scale (Other settings): a value below 100 % makes the whole window smaller, on every system; "Auto" never goes below 100 %
    for value, lo, hi in ((0.7, 0.69, 0.71), (0.5, 0.49, 0.51), (None, 1.0, 10.0)):
        cfgmod.set_setting("ui_scale", value)
        small_app = gui.App(cfg)
        try:
            small_app.root.attributes("-alpha", 0.0)
        except Exception:
            pass
        assert lo <= small_app.ui <= hi, (value, small_app.ui)
        small_app.root.destroy()
    cfgmod.set_setting("ui_scale", None)
    print("test_window_fits_screen: ok")


if __name__ == "__main__":
    main()
