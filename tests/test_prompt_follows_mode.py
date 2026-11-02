"""The prompt field follows the function (user 2.11.): a function with a text of its own (Upscale, Refine) shows it, Expand
empties the field, and your own text comes back with the next function that has no text of its own. Hidden Tk window.

    python tests/test_prompt_follows_mode.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-pfm-")
sys.path.insert(0, str(ROOT))

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as e:
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui, models  # noqa: E402


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    app.cb_workflow["values"] = [gui.BUILTIN] + sorted({w for m in models.MODELS for w in m.workflows()})
    text = lambda: app.t_prompt.get("1.0", "end").strip()      # noqa: E731

    def go(mode):
        app.v_mode.set(mode)
        app._on_mode()
        app.root.update()

    app.v_model.set("qwen")
    go("edit")
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "make it night")
    go("upscale")                                          # a text of its own replaces yours
    assert text() == models.QWEN_UPSCALE_DEFAULT, text()
    go("refine")
    assert text() == models.QWEN_UPSCALE_DEFAULT, text()
    go("edit")                                             # no text of its own: yours comes back
    assert text() == "make it night", text()
    go("outpaint")                                         # Expand empties the field ...
    assert text() == "", text()
    go("edit")                                             # ... and the way back brings the text back
    assert text() == "make it night", text()
    go("inpaint")                                          # a plain change keeps the text
    assert text() == "make it night", text()
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "a new text")               # typed after the way back: the old one is not restored over it
    go("outpaint")
    go("edit")
    assert text() == "a new text", text()
    app.v_model.set("moss")                                # no model shows a negative prompt row (user 2.11.)
    go("txt2img")
    assert not app.btn_neg.winfo_manager() and not app.neg_body.winfo_manager()
    app.root.destroy()
    print("ALL OK (prompt follows the function)")


if __name__ == "__main__":
    main()
