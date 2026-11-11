"""The window's height (user 3.11. to 5.11.): it always gets the height its content needs, even when that is more than the screen
(PC C: it was cut off at a fixed height). It does not scroll, does not move and ignores the screen's size. Also with Tk 9,
whose winfo_reqheight of the root does not follow a child that grew. Also the Linux mouse wheel helpers. Real Tk window
(invisible), the monitor is simulated. Skipped when Tk cannot open a window.

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
from pccomfy import gui, gui_theme, models  # noqa: E402

HOME_Y = 300


def _shape(app):
    r = app.root
    return (r.geometry(), r.winfo_height(), r.winfo_rooty(), app.f_body.winfo_reqheight(), app.cv_body.winfo_height(),
            app.sb_body.shown, getattr(app, "_fit_job", None))


QUIET = 0.25        # longer than the window's own delayed fit (gui_theme._on_content_size: 60 ms) several times over


def settle(app, s=0.6):
    """Lets Tk work until the window has been still for QUIET seconds (no pending fit, same size and place), at most s
    seconds; the first call after start waits the full s (the start-up callbacks run at 100 to 200 ms)."""
    start = time.time()
    end, still, last = start + s, start, None
    while time.time() < end:
        app.root.update()
        now = _shape(app)
        if now != last:
            last, still = now, time.time()
        elif now[-1] is None and time.time() - still >= QUIET and getattr(app, "_settled_once", False):
            return
        time.sleep(0.02)
    app._settled_once = True


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

    # The window always gets the height its content needs, even if that is more than the screen (user 5.11., PC C): it never scrolls,
    # never moves and is never limited by the screen. Tested on screens of every size, and with Tk 9's behaviour (below).
    closed_h = app.root.winfo_height()
    for name, screen in (("big", lambda x, y, work=False: (0, 0, 4000, 10 ** 5)),
                         ("small", lambda x, y, work=False: (0, 0, 4000, closed_h + taskbar + 20 - (taskbar if work else 0))),
                         ("real", app._monitor_at)):
        app._monitor_at = screen
        app.root.geometry(f"+60+{HOME_Y}")
        settle(app)
        home = app.root.winfo_rooty()
        app._toggle_advanced()
        settle(app)
        assert app.v_adv_open.get()
        tall = app.root.winfo_height()
        assert tall > closed_h + app._px(40), (name, "Advanced opened but the window did not grow", closed_h, tall)
        assert not app.sb_body.shown, (name, "no scroll bar: the window is as tall as its content")
        assert app.cv_body.winfo_reqheight() == app.f_body.winfo_reqheight(), (name, "the canvas asks for the body's height (Tk 9: cget gave '7c')")
        assert abs(tall - gui_theme.stack_height(app.root)) <= 2, (name, tall, gui_theme.stack_height(app.root))
        stays_at(app, home, name + ": the window does not move")
        app._toggle_advanced()
        settle(app)
        assert abs(app.root.winfo_height() - closed_h) <= 2, (name, "closed again: back to its old height")
        stays_at(app, home, name + ": closed again: same place")

    # Tk 9 (PC C): the root's own winfo_reqheight keeps the size geometry() set and ignores a child that grew. The window must
    # still follow its content: stack_height adds up the children, and equals the root's value where that one is right.
    app._fit_height()
    assert abs(gui_theme.stack_height(app.root) - app.root.winfo_reqheight()) <= 2, (gui_theme.stack_height(app.root), app.root.winfo_reqheight())
    frozen = app.root.winfo_reqheight()
    app.root.winfo_reqheight = lambda: frozen               # what Tk 9 does
    app._toggle_advanced()
    settle(app)
    assert app.root.winfo_height() > closed_h + app._px(40), ("Tk 9: Advanced opened but the window did not grow", closed_h, app.root.winfo_height())
    app._toggle_advanced()
    settle(app)
    assert abs(app.root.winfo_height() - closed_h) <= 2
    del app.root.winfo_reqheight

    # the mouse wheel helpers: Windows <MouseWheel> (delta), Linux Button-4 (up) and Button-5 (down)
    class Ev:
        def __init__(self, num=0, delta=0, widget=None):
            self.num, self.delta, self.widget = num, delta, widget or app.root
    assert gui.wheel_up(Ev(delta=120)) and not gui.wheel_up(Ev(delta=-120))
    assert gui.wheel_up(Ev(num=4)) and not gui.wheel_up(Ev(num=5))
    app._toggle_advanced()
    settle(app)
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
            # font like the other Advanced settings (Muted, 9 pt), and the box only as wide as "x.x" (user 6.11.)
            assert str(app.cb_native.cget("style")) == "Muted.TCheckbutton" and str(app.lbl_canvas.cget("style")) == "Muted.TLabel"
            assert int(app.w_native_mp.cget("width")) == 3
            # "Custom LoRAs" (no colon) is the last block of the Advanced settings (user 6.11.)
            last = int(app.f_xl.grid_info()["row"])
            assert all(int(w.grid_info()["row"]) < last for w in app.adv_body.grid_slaves() if w is not app.f_xl)
            assert all(("canvas" in t.text) == (mode == "txt2img") for t in app.tt_native), (model, mode)
    # "Send reference images in original size, up to N MP" (Multi Image Edit): on at every start with 2 MP for all models, the MP box follows the tick
    for model in ("flux3", "flux2", "qwen", "fibo"):
        app.v_model.set(model)
        app.v_mode.set("multi_edit")
        app._on_model()
        settle(app)
        assert app.v_ref_native.get() is True and float(app.v_ref_mp.get()) == 2.0, (model, app.v_ref_native.get(), app.v_ref_mp.get())
        assert str(app.w_refpx.cget("state")) == "normal" and str(app.cb_refsize.cget("text")) == "Send ref. images in original size, up to"
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
