"""The window on a small screen (user 3.11., a third PC: Advanced settings lay under the status line, out of sight).
While the whole window fits on the screen it moves up instead of scrolling and goes back to its place when it is smaller
again; only when it is taller than the screen the body scrolls, and opening Advanced settings scrolls them into view.
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

    # 1. the screen is tall enough for the whole window, but not below the window's place: it moves up, no scroll bar
    screen_h = tall + taskbar + home // 2
    app._monitor_at = lambda x, y: (0, 0, 4000, screen_h)
    app._toggle_advanced()
    settle(app)
    bottom = app.root.winfo_rooty() + app.root.winfo_height()
    assert not app.sb_body.shown, "the whole window fits on the screen: no scroll bar"
    assert app.root.winfo_rooty() < home, "the window moved up"
    assert bottom <= screen_h - taskbar + 1, (bottom, screen_h - taskbar)
    assert visible_in_body(app, app.f_adv), "Advanced settings are in sight"
    # the saved place stays the user's one, not the moved one
    app._remember_pos()
    assert abs(app._win_pos[1] + frame - home) <= 1, (app._win_pos, home, frame)

    # 2. closed again: back to its place
    app._toggle_advanced()
    settle(app)
    assert abs(app.root.winfo_rooty() - home) <= 1, (app.root.winfo_rooty(), home)

    # 3. a screen smaller than the window: it goes to the top, the body scrolls, opening Advanced scrolls them into view
    small = tall // 2 + taskbar + app._px(300)
    app._monitor_at = lambda x, y: (0, 0, 4000, small)
    app._fit_height()
    settle(app)
    app._toggle_advanced()
    settle(app)
    assert app.sb_body.shown, "taller than the screen: the body scrolls"
    assert app.root.winfo_rooty() < home, app.root.winfo_rooty()        # up as far as the system lets it (GNOME: top bar)
    assert app.root.winfo_rooty() + app.root.winfo_height() <= small - taskbar + 1
    assert visible_in_body(app, app.btn_adv), "the Advanced heading is in sight after opening"

    # 4. a drag (the user's new place) is the new home
    app._toggle_advanced()
    settle(app)
    app._monitor_at = lambda x, y: (0, 0, 4000, 10 ** 5)
    app.root.geometry(f"+60+{HOME_Y + 40 - frame}")
    settle(app)
    app._fit_height()
    settle(app)
    assert abs(app.root.winfo_rooty() - (HOME_Y + 40)) <= 1, app.root.winfo_rooty()
    app.root.destroy()
    print("test_window_fits_screen: ok")


if __name__ == "__main__":
    main()
