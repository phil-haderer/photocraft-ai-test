"""The standard mode has ONE function button "Upscale / Refine" with the factors None | 1.5x | 2x | 3x | 4x (PLAN.md 2,
user 6.11.): None runs the inner mode "refine", a factor the inner mode "upscale". Real Tk window
(hidden); skipped when Tk cannot open a window.

    python tests/test_scale_function.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="pccomfy-scalefn-")
os.environ["PCCOMFY_HOME"] = TMP
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


def shown(w) -> bool:
    return bool(w.winfo_manager())


def no_licence_notes():
    """No stage tooltip of a workflow warns about a licence any more (user 7.11.: licence warnings removed; 8.11.: the
    UltraSharp tips of Flux 3 and Fibo Upscale still said "non-commercial")."""
    from pccomfy import workflows
    for wf in sorted((ROOT / "workflows").glob("*.json")):
        for st in workflows.stage_info(workflows.load_template(wf)):
            assert "commercial" not in st["tip"].lower() and "licen" not in st["tip"].lower(), (wf.name, st["tip"])


def main():
    no_licence_notes()
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    app.cb_workflow["values"] = [gui.BUILTIN] + names
    app.v_model.set("qwen")
    app.v_mode.set("inpaint")
    app._on_model()
    app.root.update()

    # the grid: one button in Upscale's place (last of the six: Multi Image Edit is a tab of Edit, 7.11.); Upscale and Refine themselves are hidden
    assert shown(app.rb_scale_fn) and not shown(app.rb_modes["upscale"]) and not shown(app.rb_modes["refine"])
    info = app.rb_scale_fn.grid_info()
    assert (info["row"], info["column"]) == (2, 1), info
    assert app.rb_scale_fn["text"] == "Upscale / Refine", app.rb_scale_fn["text"]
    assert str(app.rb_scale_fn["state"]) == "normal", str(app.rb_scale_fn["state"])
    assert app.v_fn.get() == ""                                         # not chosen while Fill is on
    assert not shown(app.f_scale)

    # a click: Refine = None, the factor row appears with None chosen
    app.v_fn.set("scale")
    app._on_scale_fn()
    app.root.update()
    assert app.v_mode.get() == "refine" and app.v_fac.get() == "r:Default" and shown(app.f_scale) and shown(app.rb_refine["Default"])
    wf_refine = app.v_workflow.get()
    assert wf_refine == models.QWEN.modes["refine"].workflow, wf_refine

    # a factor: Upscale with that factor (the mode's start factor 1.5 does not win), the workflow of Upscale
    app.v_fac.set("x 3")
    app._on_factor()
    assert app.v_mode.get() == "upscale" and app._scale() == 3.0 and app._request().scale == 3.0
    assert app.v_workflow.get() == models.QWEN.modes["upscale"].workflow and app.v_fn.get() == "scale"
    app.v_fac.set("x 2")                                                # another factor: still Upscale, the factor changes
    app._on_factor()
    assert app.v_mode.get() == "upscale" and app._scale() == 2.0
    app.v_fac.set("r:Default")                                          # back to the Refine row: Refine, the saved factor stays for later
    app._on_factor()
    assert app.v_mode.get() == "refine" and app._scale() == 2.0 and app._request().mode == "refine"
    app.v_mode.set("upscale")                                           # set from outside (a saved page): the buttons follow
    app._on_mode_ui()
    assert app.v_fac.get() == "x 2"
    app.v_scale.set("x 4")
    assert app.v_fac.get() == "x 4"

    # the button remembers the last of the two: leave, come back
    app.v_mode.set("inpaint")
    app._on_mode()
    assert app.v_fn.get() == "" and not shown(app.f_scale)
    app.v_fn.set("scale")
    app._on_scale_fn()
    assert app.v_mode.get() == "upscale"

    # Fibo enlarges up to 3x (10.11.; 2x since 6.11.): only 4x is greyed out, the Refine row works
    app.v_model.set("fibo")
    app._on_model()
    assert app.v_mode.get() == "upscale" and app._scale() == 1.5, (app.v_mode.get(), app._scale())
    assert [str(app.rb_scale[k]["state"]) for k in ("x 1.5", "x 2", "x 3", "x 4")] == ["normal", "normal", "normal", "disabled"]
    # ... and they look greyed out like a greyed-out model chip (8.11.): grey text, no fill, a dark outline
    st = gui.ttk.Style(app.root)
    assert st.lookup("Small.Toolbutton", "foreground", ["disabled"]) == gui.DISABLED
    assert st.lookup("Small.Toolbutton", "background", ["disabled"]) == gui.BG
    assert st.lookup("Small.Toolbutton", "bordercolor", ["disabled"]) == st.lookup("Chip.Toolbutton", "bordercolor", ["disabled"])
    assert st.lookup("Small.Toolbutton", "foreground", ["disabled"]) == st.lookup("Chip.Toolbutton", "foreground", ["disabled"])
    assert str(app.rb_refine["Default"]["state"]) == "normal" and list(app.rb_refine) == ["Default"]
    assert app.t_prompt.get("1.0", "end").strip() == models.QWEN_UPSCALE_DEFAULT and app._request().mode == "upscale"
    assert app.v_workflow.get() == "fibo2-upscale.json"
    # Fibo Upscale stages (7.11.): "4x UltraSharp first" on, "Tiles" off, and they exclude each other
    assert [x["label"] for x in app._stages()] == ["4x UltraSharp first", "Tiles"] and [v.get() for v in app.stage_vars[:2]] == [True, False]
    r = app._request()
    assert r.stage_on and r.stages_off == ["102"]
    app.stage_vars[1].set(True)
    app._on_stage(1)
    assert [v.get() for v in app.stage_vars[:2]] == [False, True] and not app._request().stage_on and app._request().stages_off == []
    app.stage_vars[0].set(True)
    app._on_stage(0)
    assert [v.get() for v in app.stage_vars[:2]] == [True, False]
    # the stages in ONE row between "Upscale factor" and "Refine" with a line under it (8.11.), not in the box under the prompt
    app.root.update()
    assert shown(app.f_stage_row) and shown(app.sep_stage_row)
    assert app.f_stage_row.grid_info()["row"] == 1 and app.sep_stage_row.grid_info()["row"] == 2
    assert [cb["text"] for cb in app.stage_row_cbs if shown(cb)] == ["4x UltraSharp first", "Tiles"]
    assert all(str(cb["state"]) == "normal" for cb in app.stage_row_cbs[:2])
    assert not any(shown(cb) for cb in app.stage_cbs) and not shown(app.f_opts)
    assert app.stage_row_cbs[0]["variable"] == app.stage_cbs[0]["variable"]      # the same switch: the request follows the row
    app.stage_row_cbs[1].invoke()           # a click on "Tiles" in the row switches "4x UltraSharp first" off
    assert [v.get() for v in app.stage_vars[:2]] == [False, True] and app._request().stages_off == []
    app.stage_row_cbs[0].invoke()
    assert [v.get() for v in app.stage_vars[:2]] == [True, False]
    # Refine (the edit workflow, no stages): the row stays where it is, greyed out
    app.v_fac.set("r:Default")
    app._on_factor()
    app.root.update()
    assert app.v_mode.get() == "refine" and app.v_workflow.get() == "fibo2-edit.json"
    assert shown(app.f_stage_row) and shown(app.sep_stage_row)
    assert [cb["text"] for cb in app.stage_row_cbs if shown(cb)] == ["4x UltraSharp first", "Tiles"]
    assert all(str(cb["state"]) == "disabled" for cb in app.stage_row_cbs if shown(cb))
    app.v_fac.set("x 1.5")
    app._on_factor()
    app.root.update()
    assert app.v_mode.get() == "upscale" and all(str(cb["state"]) == "normal" for cb in app.stage_row_cbs if shown(cb))
    app.v_model.set("qwen")
    app._on_model()
    assert all(str(rb["state"]) == "normal" for rb in app.rb_scale.values())
    app.v_mode.set("upscale")
    app._on_mode()
    app.root.update()
    assert not shown(app.f_stage_row) and not shown(app.sep_stage_row)       # Qwen has no stage row (user 10.11.: Qwen stays as it is)
    assert str(app.rb_tabs["fibo"]["state"]) == "normal"                  # the chip stays clickable (falls back to None)
    # Flux 2 Upscale: the stage "Tiles" in the row, on at the start (user 10.11.); Refine runs its own graph without it
    app.v_model.set("flux2")
    app._on_model()
    app.v_mode.set("upscale")
    app._on_mode()
    app.root.update()
    assert shown(app.f_stage_row) and [cb["text"] for cb in app.stage_row_cbs if shown(cb)] == ["Tiles"]
    assert app.stage_vars[0].get() is True and app._request().stage_on and app.v_workflow.get() == "flux2-klein-upscale.json"
    app.v_mode.set("refine")
    app._on_mode()
    assert app.v_workflow.get() == "flux2-klein-refine.json"

    # the request through the new buttons is the request of the old way (function Upscale / Refine, then the factor) - PLAN.md 5.3
    import dataclasses

    def snap(model, mode, factor):
        app.v_model.set(model)
        app.v_mode.set("inpaint")
        app._on_model()
        app.v_mode.set(mode)
        app._on_mode()
        if factor:
            app.v_scale.set(factor)
            app._on_scale_pick()
        req = app._request()
        return dataclasses.asdict(req), app.t_prompt.get("1.0", "end").strip(), app.v_steps.get()

    for model in ("qwen", "flux2", "flux3"):
        for factor in ("x 1.5", "x 2", "x 3", "x 4"):
            old = snap(model, "upscale", factor)
            app.v_model.set(model)
            app.v_mode.set("inpaint")
            app._on_model()
            app.v_fn.set("scale")
            app._on_scale_fn()                    # None first (Refine) ...
            app.v_fac.set(factor)
            app._on_factor()                      # ... then the factor
            new = (dataclasses.asdict(app._request()), app.t_prompt.get("1.0", "end").strip(), app.v_steps.get())
            assert new == old, (model, factor, [k for k in old[0] if old[0][k] != new[0][k]], old[1:], new[1:])
        old = snap(model, "refine", None)
        app.v_mode.set("inpaint")
        app._on_model()
        app.v_fn.set("scale")
        app._scale_mode = "refine"                # the button comes back to the last used one: here None
        app._on_scale_fn()
        new = (dataclasses.asdict(app._request()), app.t_prompt.get("1.0", "end").strip(), app.v_steps.get())
        assert new == old, (model, "none", [k for k in old[0] if old[0][k] != new[0][k]])

    # The Refine row (user 6.11.): the ready-made prompts are the Refine modes, one choice over both rows
    app.v_model.set("flux2")
    app.v_mode.set("inpaint")
    app._on_model()
    app.v_fn.set("scale")
    app._on_scale_fn()
    assert list(app.rb_refine) == ["Default", "Neutral", "Studio portrait"] and app.v_fac.get() == "r:Default"
    app.v_fac.set("r:Neutral")
    app._on_factor()                                                    # a preset: Refine, its prompt replaces the field
    assert app.v_mode.get() == "refine" and app._prompt_text() == models.RELIGHT_NEUTRAL and app.v_fac.get() == "r:Neutral"
    app.t_prompt.insert("1.0", "a portrait. ")                          # your text in front: the Refine button stays lit
    app.root.update()
    assert app.v_fac.get() == "r:Neutral"
    app.v_fac.set("x 2")
    app._on_factor()                                                    # a factor: Upscale with the default prompt
    assert app.v_mode.get() == "upscale" and app.v_fac.get() == "x 2"
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "my own text")
    app.v_fac.set("r:Default")
    app._on_factor()                                                    # only switching to the first button: your own text stays
    assert app.v_mode.get() == "refine" and app._prompt_text() == "my own text"
    app.v_fac.set("r:Studio portrait")
    app._on_factor()
    assert app._prompt_text() == models.RELIGHT_STUDIO and app._request().mode == "refine"
    app.v_model.set("flux3")
    app._on_model()
    assert list(app.rb_refine) == ["Default", "Restore"] and app.v_fac.get() == "r:Default" and app._prompt_text() == models.FLUX3_DEFAULT
    app.v_fac.set("r:Restore")
    app._on_factor()
    assert app._prompt_text() == models.FLUX3_RESTORE and app.v_fac.get() == "r:Restore"

    assert shown(app.rb_scale_fn) and not shown(app.rb_modes["upscale"])
    app.root.destroy()
    print("ALL OK (Upscale / Refine function button)")


if __name__ == "__main__":
    main()
