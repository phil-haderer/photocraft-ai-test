"""Cancel (Esc) also stops the text model while it describes a picture (the LLM button, user 2.11.). Hidden Tk window,
a fake bridge whose describe waits until it is cancelled.

    python tests/test_cancel_describe.py
"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-cd-")
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as e:
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui  # noqa: E402
from pccomfy.comfy import Cancelled  # noqa: E402


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    for _ in range(25):                         # let the start-up refresh report (nothing runs on port 1) before the status is checked
        app.root.update()
        time.sleep(0.02)
    ev = threading.Event()

    def describe(clip=""):
        while not ev.is_set():
            time.sleep(0.01)
        raise Cancelled()
    app.bridge.describe_canvas = describe
    app.bridge.cancel = ev.set
    app._llm_file = lambda: ""
    app.describe_canvas()
    assert app._describing and str(app.b_stop.cget("state")) == "normal"
    app.stop()                                  # Esc / the Cancel button
    for _ in range(100):
        app.root.update()
        if not app._describing:
            break
        time.sleep(0.02)
    assert not app._describing and str(app.b_stop.cget("state")) == "disabled"
    assert app.v_status.get() == "Cancelled.", app.v_status.get()
    app.root.destroy()
    print("ALL OK (cancel stops describe)")


if __name__ == "__main__":
    main()
