"""Layout checks in the real window (hidden Tk): a stage marked `advanced` (MOSS' skip-layer guidance) has its checkbox at the top of the
Advanced settings, Fibo Upscale shows its two stages in the switch box, and the reference images show the BBOX row only for Flux 3.

    python tests/test_stage_advanced.py
"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-sa-")
os.environ["PCCOMFY_NO_TIPS"] = "1"
sys.path.insert(0, str(ROOT))
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception as e:                      # no display / no Tk
    print(f"SKIPPED (no Tk window: {e})")
    sys.exit(0)

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui, models  # noqa: E402


def shown(w) -> bool:
    return bool(w.winfo_manager())


def pick(app, model, mode):
    app.v_model.set(model)
    app.v_mode.set(mode)
    app._on_model()
    app.root.update()


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    app.cb_workflow["values"] = [gui.BUILTIN] + sorted({w for m in models.MODELS for w in m.workflows()})
    for _ in range(10):
        app.root.update()
        time.sleep(0.02)

    pick(app, "moss", "txt2img")        # skip-layer guidance: a twin at the top of the Advanced settings, the UltraReal LoRA stays in the box
    assert shown(app.stage_adv_cbs[1]) and app.stage_adv_cbs[1].grid_info()["row"] == 0 and int(app.f_post.grid_info()["row"]) == 1
    assert not shown(app.stage_cbs[1]) and shown(app.stage_cbs[0]) and not shown(app.stage_adv_cbs[0])
    app.stage_adv_cbs[1].invoke()
    assert app.v_stage2.get() and app._request().stages_off == []        # the twin switches the same stage
    app.stage_adv_cbs[1].invoke()
    assert not app.v_stage2.get()

    pick(app, "fibo", "upscale")        # two stages in the box, none in the Advanced settings; they exclude each other
    assert shown(app.stage_cbs[0]) and shown(app.stage_cbs[1]) and not shown(app.stage_adv_cbs[0]) and not shown(app.stage_adv_cbs[1])
    assert [c["text"] for c in app.stage_cbs[:2]] == ["4x UltraSharp first", "Tiles"]

    pick(app, "flux2", "multi_edit")
    app._refs_update()
    app.root.update()
    # no empty row under "Reference images" without the BBOX tick (user 7.11.)
    app._refs_update()
    app.root.update()
    assert not shown(app.f_refhead2) and not shown(app.cb_bbox)
    pick(app, "flux3", "multi_edit")
    app._refs_update()
    app.root.update()
    assert shown(app.f_refhead2) and shown(app.cb_bbox)
    print("ALL OK (stage in Advanced, Fibo stages, reference row)")


if __name__ == "__main__":
    main()
