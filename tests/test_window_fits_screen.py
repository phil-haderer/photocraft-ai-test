"""The window on a small screen (user 3.11., 4.11.). The window never moves by itself: it stays where the user puts it and may be
pushed down, even partly off the screen. Only when the content is taller than the screen's usable height the body scrolls (mouse
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
    app._monitor_at = lambda x, y: (0, 0, 4000, 10 ** 5)
    app._toggle_advanced()
    settle(app)
    tall = app.root.winfo_height()
    app._toggle_advanced()
    settle(app)
    assert abs(app.root.winfo_rooty() - home) <= 1, "a big screen moves nothing"

    # 1. the screen is tall enough for the whole window but not below the window's place: nothing moves, no scroll bar,
    #    the window height does not depend on where it stands (it may hang below the screen)
    screen_h = tall + taskbar + home // 2
    app._monitor_at = lambda x, y: (0, 0, 4000, screen_h)
    app._toggle_advanced()
    settle(app)
    assert abs(app.root.winfo_rooty() - home) <= 1, "the window stays where the user put it"
    assert not app.sb_body.shown, "the whole window fits the screen's height: no scroll bar"
    h_here = app.root.winfo_height()
    app.root.geometry(f"+60+{screen_h - 100}")                      # pushed far down
    settle(app)
    app._fit_height()
    settle(app)
    assert app.root.winfo_height() == h_here and not app.sb_body.shown, "pushing it down changes neither its height nor the scroll bar"
    assert app.root.winfo_rooty() > home, "it stays where it was pushed"
    app.root.geometry(f"+60+{HOME_Y - frame}")
    settle(app)

    # 2. closed again: same place
    app._toggle_advanced()
    settle(app)
    assert abs(app.root.winfo_rooty() - home) <= 1, (app.root.winfo_rooty(), home)

    # 3. a screen smaller than the window: it stays too, the body scrolls, opening Advanced scrolls them into view
    small = tall // 2 + taskbar + app._px(300)
    app._monitor_at = lambda x, y: (0, 0, 4000, small)
    app._fit_height()
    settle(app)
    app._toggle_advanced()
    settle(app)
    assert app.sb_body.shown, "taller than the screen: the body scrolls"
    assert abs(app.root.winfo_rooty() - home) <= 1, "it does not jump to the top"
    assert app.root.winfo_height() <= small - taskbar + 1, (app.root.winfo_height(), small - taskbar)
    assert visible_in_body(app, app.btn_adv), "the Advanced heading is in sight after opening"

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
