"""After a start the prompt field is on its default: the text of the last session is not restored (user 3.11). Hidden Tk window.

    python tests/test_prompt_start_default.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-psd-")
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
    state = cfgmod.load_state()
    state["prompt"] = "text of the last session"
    cfgmod.save_state(state)
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    text = app.t_prompt.get("1.0", "end").strip()
    assert text in ("", *models.STOCK_PROMPTS), text
    app.root.destroy()
    print("ALL OK (prompt start default)")


if __name__ == "__main__":
    main()
