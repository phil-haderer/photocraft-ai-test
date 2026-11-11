"""P6 (user 10.11.): from Sketch to image / Scribble on photo to Upscale / Refine the scribble text (edited or not) does not
count as own text: the Upscale / Refine prompt goes into the field, the scribble text waits aside and comes back with its
tab. Other own texts (Edit canvas) still stay. Real Tk window (hidden); skipped when Tk cannot open a window.

    python tests/test_scribble_upscale_prompt.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-scribup-")
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
from pccomfy import gui, models  # noqa: E402


def text(app):
    return app.t_prompt.get("1.0", "end").strip()


def put(app, s):
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", s)


def go(app, mode):
    app.v_mode.set(mode)
    app._on_mode()
    app.root.update()


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    app.v_model.set("fibo")
    app.v_mode.set("scribble")
    app._on_model()
    app.root.update()
    up = models.FIBO.modes["upscale"].prompt_hint
    assert up in models.STOCK_PROMPTS and "<" not in up

    # scribble sentence, unedited: replaced by the Upscale text, back on return
    go(app, "scribble")
    assert text(app) == models.SKETCH_SCRIBBLE, text(app)
    go(app, "upscale")
    assert text(app) == up, text(app)
    go(app, "scribble")
    assert text(app) == models.SKETCH_SCRIBBLE, text(app)

    # edited scribble sentence: aside, Upscale text in the field, edited text back with the tab
    mine = models.SKETCH_SCRIBBLE.replace(models.SKETCH_MARK, "a red fox")
    assert mine != models.SKETCH_SCRIBBLE
    put(app, mine)
    go(app, "upscale")
    assert text(app) == up, text(app)
    go(app, "refine")                      # leaving Upscale for Refine keeps the aside text for its tab
    go(app, "scribble")
    assert text(app) == mine, text(app)
    go(app, "upscale")
    go(app, "scribble")                    # the aside text came back once and is gone: the stock sentence
    assert text(app) == mine or text(app) == models.SKETCH_SCRIBBLE
    put(app, mine)
    go(app, "refine")
    first = models.FIBO.modes["refine"].prompt_hint
    assert text(app) == first, text(app)

    # own text of Edit canvas still stays when switching to Upscale
    go(app, "edit")
    put(app, "my own edit text")
    go(app, "upscale")
    assert text(app) == "my own edit text", text(app)
    print("OK")


main()
