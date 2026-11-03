"""Right-click on a label or a link symbol offers "Copy" / "Copy link" (user 3.11.); the ComfyUI dot is red or green only;
the "!" of an error sits at the top left; a refused connection gives one short English message. Hidden Tk window.

    python tests/test_copy_menu.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-copy-")
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    from tkinter import ttk
    tkinter.Tk().destroy()
except Exception as e:
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import comfy, config as cfgmod, gui  # noqa: E402


class Ev:
    x_root = y_root = 5


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    popped = []
    gui.tk.Menu.tk_popup = lambda self, *a: (popped.append(self.entrycget(0, "label")), self.invoke(0))

    lb = ttk.Label(app.root, text="ComfyUI is not running at http://127.0.0.1:8188.")
    ev = Ev()
    ev.widget = lb
    assert app._copy_menu(ev) == "break" and popped == ["Copy"]
    assert app.root.clipboard_get() == "ComfyUI is not running at http://127.0.0.1:8188."
    link = ttk.Button(app.root, text="")
    link.copy_text = "https://example.org/pack"
    ev.widget = link
    popped.clear()
    app._copy_menu(ev)
    assert popped == ["Copy link"] and app.root.clipboard_get() == "https://example.org/pack"
    dot = ttk.Label(app.root, text="●")
    ev.widget = dot
    popped.clear()
    assert app._copy_menu(ev) is None and not popped          # the dot and the badge have nothing to copy

    # the dot is red until ComfyUI answers; never grey
    assert str(app.lbl_dot.cget("style")) == "ConnBad.TLabel"
    gui.set_dot(app.lbl_dot, None)
    assert str(app.lbl_dot.cget("style")) == "ConnBad.TLabel"
    gui.set_dot(app.lbl_dot, True)
    assert str(app.lbl_dot.cget("style")) == "ConnOk.TLabel"

    # the exclamation mark sits at the top left of the message
    app._status("Something failed", error=True)
    assert app.lbl_err.pack_info()["anchor"] == "n"

    # a refused connection: one short English message, no system text
    c = comfy.ComfyUI("http://127.0.0.1:1")
    try:
        c.system_stats()
    except comfy.ComfyError as e:
        assert str(e) == "ComfyUI is not running at http://127.0.0.1:1. Start it, then click Refresh.", str(e)
    else:
        raise SystemExit("expected a ComfyError")
    app.root.destroy()
    print("ALL OK (copy menu, dot, badge, message)")


if __name__ == "__main__":
    main()
