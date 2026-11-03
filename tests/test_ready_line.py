"""The idle line at the bottom (user 3.11.): "Ready" only when the chosen model and function can run; else it says what to get.
A custom node pack that the workflow needs (ComfyUI-KJNodes for Flux 3 Upscale) is named, and Generate stops with the same hint.
Hidden Tk window.

    python tests/test_ready_line.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-rl-")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as e:
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod, gui, inventory, manifest  # noqa: E402
from test_detection import full_lists  # noqa: E402


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    for _ in range(25):
        app.root.update()
        time.sleep(0.02)
    nodes = set(n for t in manifest.TABS.values() for s in t.modes.values() for n in s.nodes) | {"ColorMatch"}
    app.cb_workflow["values"] = [gui.BUILTIN] + sorted({w for m in gui.models.MODELS for w in m.workflows()})
    app.v_model.set("flux3")
    app.v_mode.set("upscale")
    app._on_model()
    app.inv = inventory.Inventory(full_lists(), nodes=nodes)
    assert app.v_workflow.get().endswith("flux3-klein-upscale.json"), app.v_workflow.get()
    assert app._ready_text() == "Ready", app._ready_text()

    app.inv = inventory.Inventory(full_lists(), nodes=nodes - {"ColorMatch"})          # KJNodes is not installed
    text = app._ready_text()
    assert text.startswith("You need to install ComfyUI-KJNodes in ComfyUI") and text.endswith("to run with these options"), text
    assert any("ComfyUI-KJNodes" in l and "github.com/kijai" in l for l in app._preflight()), app._preflight()   # Generate says so too
    app.inv = inventory.Inventory(full_lists(), nodes=None)                           # nodes not read: no false alarm
    assert app._ready_text() == "Ready" and app._pack_lines(app.inv) == []

    lists = full_lists()                                                              # a model file is missing
    lists["unet"] = [n for n in lists["unet"] if "flux3" not in n]
    app.inv = inventory.Inventory(lists, nodes=nodes)
    text = app._ready_text()
    assert text.startswith("You need to download ") and "in the settings" in text, text

    # the line follows the choice but never overwrites a message
    app.v_status.set("Done · seed 5")
    app._update_ready()
    assert app.v_status.get() == "Done · seed 5"
    app.v_status.set("")
    app._update_ready()
    assert app.v_status.get() == app._idle_text
    app.root.destroy()
    print("ALL OK (ready line)")


if __name__ == "__main__":
    main()
