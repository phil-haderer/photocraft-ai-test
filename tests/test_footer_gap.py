"""The status line between the progress bar and the footer is shown only while it has text (user 8.11., decision D: b):
empty, it shrinks to 1 px without its gap; with a message (or an error with its red "!") it comes back. The frame itself
stays packed, because the live preview and the tabs are placed before it. Real Tk window (hidden); skipped without Tk.

    python tests/test_footer_gap.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-footgap-")
os.environ["PCCOMFY_NO_TIPS"] = "1"
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    _r = tkinter.Tk()
    _r.destroy()
except Exception as e:
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui  # noqa: E402


def shown(w) -> bool:
    return bool(w.winfo_manager())


def pady(w) -> list:
    v = w.pack_info()["pady"]
    return [int(str(x)) for x in (v if isinstance(v, (tuple, list)) else str(v).split())]


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    app.root.update()

    app._status("Copying the canvas…")
    app.root.update()
    assert shown(app.f_status) and shown(app.lbl_status) and not shown(app.lbl_err)
    assert app.f_status.winfo_reqheight() > 10 and pady(app.f_status)[0] > 0, (app.f_status.winfo_reqheight(), pady(app.f_status))
    with_text = app.f_status.winfo_reqheight()

    app._status("")                     # a run ended well: nothing to say, no empty line above the footer
    app.root.update()
    assert shown(app.f_status) and not shown(app.lbl_status) and not shown(app.lbl_err)
    assert app.f_status.winfo_reqheight() <= 1, app.f_status.winfo_reqheight()
    assert pady(app.f_status) in ([0], [0, 0]), pady(app.f_status)

    app._status("Error: ComfyUI did not answer", error=True)
    app.root.update()
    assert shown(app.lbl_err) and shown(app.lbl_status)
    assert app.lbl_err.winfo_x() < app.lbl_status.winfo_x() or app.f_status.pack_slaves()[0] is app.lbl_err
    assert app.f_status.winfo_reqheight() >= with_text

    app.v_status.set("")                # a direct set (the settings window) hides it too
    app.root.update()
    assert not shown(app.lbl_status) and not shown(app.lbl_err) and app.f_status.winfo_reqheight() <= 1
    app.v_status.set("Ready")
    app.root.update()
    assert shown(app.lbl_status) and not shown(app.lbl_err), "an old error badge does not come back with a plain text"
    print("ALL OK (empty status line takes no room)")


if __name__ == "__main__":
    main()
