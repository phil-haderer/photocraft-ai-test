"""At every start the sliders, sampler, steps and LoRAs are the standard ones; model, function and prompt stay (user 4.11.).

    python tests/test_start_factory.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = tempfile.mkdtemp(prefix="pccomfy-start-")
os.environ["PCCOMFY_HOME"] = HOME
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


def start(state: dict):
    cfgmod.save_state(state)
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    try:
        app.root.attributes("-alpha", 0.0)
    except Exception:
        pass
    app.root.update()
    return app


def main():
    spec = models.BY_KEY["qwen"].modes["inpaint"]
    left_over = {"model": "qwen", "mode": "inpaint", "workflow": spec.workflow, "prompt": "my own words", "steps": 77, "cfg": 9.5, "sampler": "dpmpp_2m",
                 "sharpen": 0.9, "context": 0.9, "detail": 0.3, "variants": 3, "loras": [["x/y.safetensors", 0.5]],
                 "lora_strength": 0.4, "mask_grow": 40, "mask_blur": 33}
    app = start(left_over)
    try:
        assert app.v_model.get() == "qwen" and app.v_mode.get() == "inpaint"      # model and function stay
        app.t_prompt.insert("1.0", "my own words")          # a prompt in the field stays through the start routine
        app._start_fresh()
        assert app.t_prompt.get("1.0", "end").strip() == "my own words"
        assert app.v_variants.get() == 3
        assert app.v_steps.get() != 77 and abs(app.v_cfg.get() - 9.5) > 1e-6 and app.v_sampler.get() != "dpmpp_2m"
        assert app.v_sharpen.get() == float(spec.settings.get("sharpen", 0.0)) and app.v_detail.get() == 1.0
        assert app.v_context.get() != 0.9 and app.v_grow.get() != 40 and app.v_blur.get() != 33
        assert app._loras() == [], app._loras()
        assert app.v_status.get() == "Ready"
    finally:
        app.root.destroy()
    # "Set current settings as my standard settings" is loaded at the start (user 4.11., evening); a value not saved stays at the standard
    cfgmod.set_saved_page("qwen", "inpaint", {"sharpen": 0.4, "context": 0.65})
    app = start(left_over)
    try:
        app._start_fresh()
        assert abs(app.v_sharpen.get() - 0.4) < 1e-6 and abs(app.v_context.get() - 0.65) < 1e-6, (app.v_sharpen.get(), app.v_context.get())
    finally:
        app.root.destroy()
    cfgmod.set_saved_page("qwen", "inpaint", None)
    print("ALL OK (start with the standard settings, saved pages loaded)")


if __name__ == "__main__":
    main()
