"""Edit starts on the tab "Edit canvas" (user 7.11.): a saved Multi image edit comes back as Edit canvas, other functions as they were.
Hidden Tk window.

    python tests/test_edit_canvas_start.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-ec-")
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as e:
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod, gui  # noqa: E402


def start(mode):
    cfgmod.save_state({"mode": mode})
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    for _ in range(10):
        app.root.update()
        time.sleep(0.02)
    got = app.v_mode.get()
    app.root.destroy()
    return got


assert start("multi_edit") == "edit"
assert start("edit") == "edit"
assert start("inpaint") == "inpaint"
print("ALL OK (edit canvas start)")
