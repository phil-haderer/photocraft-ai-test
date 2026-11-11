"""Sketch (docs/sketch-plan.md, build steps 3 and 4, 10.11.): the mode `sketch` of the four edit models, its templates in the
prompt field, the lock of only the tab Sketch without the upsampler, and "Scribble on photo" in the bridge (find the scribble,
generate only a crop, put it back with a fading layer mask, hide the scribble layer). Bridge against the PhotoCraft simulator
of test_reference_mode, window with the stubbed Tk.

    python tests/test_sketch_mode.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

# a data folder of its own before pccomfy is imported: the window part saves the chosen style (settings.json), which must
# never land in the plugin's real data folder (it did once, 10.11.)
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-sketch-")
os.environ["PCCOMFY_NO_TIPS"] = "1"

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as tr  # noqa: E402
from pccomfy import bridge, manifest, models, scribble, workflows  # noqa: E402
from pccomfy.bridge import BridgeError, Request  # noqa: E402

ROOT = tr.ROOT
W, H = tr.W, tr.H
UPS = "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors"
VL4 = "qwen3vl_4b_int8_convrot.safetensors"        # Flux 2's Sketch writer (10.11.)


def photo():
    """A photo-like picture: smooth colours and a little noise (no pure red or green)."""
    rng = np.random.default_rng(3)
    y, x = np.mgrid[0:H, 0:W]
    a = np.stack([90 + x * 0.3, 110 + y * 0.4, 140 + 0 * x], -1) + rng.normal(0, 6, (H, W, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).convert("RGBA")


def strokes(colour, box=(120, 30, 170, 80), width=2):
    """Thin scribble strokes on an empty layer."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = box
    for k in range(5):
        d.line([(x0, y0 + k * (y1 - y0) // 4), (x1, y1 - k * (y1 - y0) // 4)], fill=colour + (255,), width=width)
    return im


def doc(layers):
    tmp = tempfile.mkdtemp()
    pc = tr.FakePC(tmp)
    pc.docs.append(tr.Doc("photo.png", [{"id": i + 1, "img": im, "visible": True, "name": f"L{i + 1}"} for i, im in enumerate(layers)]))
    b = bridge.Bridge(pc, tr.FakeComfy(), tmp)
    return pc, b


def run(pc, b, prompt, wf="flux2-klein-sketch.json", scribble_on=True, enhance=True):
    req = Request(mode="edit", workflow=str(ROOT / "workflows" / wf), enhance=enhance, layer_mask="none", scribble=scribble_on)
    req.params = workflows.GenParams(prompt=prompt, seed=7)
    return b.run(req)


def sent_prompt(b):
    g = b.comfy.graphs[-1]
    for n in g.values():
        if "pc:prompt" in n.get("_meta", {}).get("title", ""):
            return n["inputs"].get("prompt") or n["inputs"].get("text") or ""
    return ""


def test_models_and_texts():
    for key in ("flux3", "flux2", "qwen", "fibo"):
        spec = models.BY_KEY[key].modes["sketch"]
        # Sketch to image (plan B, 10.11.): no templates, the style comes from Styles; an empty field starts empty
        assert spec.run_as == "edit" and spec.prompts == () and spec.prompt_hint == "" and spec.prompt_tip == models.SKETCH_TIP
        assert spec.settings["enhance"] is (key != "fibo"), key          # the writer always, Fibo without one
        assert spec.workflow == {"flux3": "flux3-klein-sketch.json", "flux2": "flux2-klein-sketch.json",
                                 "qwen": "qwen-image-21-sketch.json", "fibo": "fibo2-edit.json"}[key]
        sc = models.BY_KEY[key].modes["scribble"]            # Scribble on photo: its own tab, the same workflow and values
        assert (sc.workflow, sc.settings, sc.run_as) == (spec.workflow, spec.settings, "edit")
        assert sc.prompts == models.SCRIBBLE_PROMPTS and sc.prompt_hint == models.SKETCH_SCRIBBLE and sc.prompt_tip == models.SCRIBBLE_TIP
    for key in ("krea2", "moss"):
        assert "sketch" not in models.BY_KEY[key].modes and "scribble" not in models.BY_KEY[key].modes
    assert [lb for lb, _t, _tip in models.SCRIBBLE_PROMPTS] == ["Scribble on photo"]
    # old saved runs and states: Scribble on photo was a template of Sketch
    assert models.legacy_sketch_mode("sketch", models.SKETCH_SCRIBBLE.replace(models.SKETCH_MARK, "a dog")) == "scribble"
    assert models.legacy_sketch_mode("sketch", models.SKETCH_PHOTO) == "sketch"
    assert models.legacy_sketch_mode("edit", models.SKETCH_SCRIBBLE) == "edit"
    assert models.legacy_sketch_mode("sketch", models.SKETCH_SCRIBBLE, models.EDIT_TABS_VERSION) == "sketch"    # saved since plan B
    assert [lb for lb, _t, _tip in models.SKETCH_PROMPTS] == ["Photo", "Illustration", "Scribble on photo"]
    for _lb, text, _tip in models.SKETCH_PROMPTS:
        assert models.SKETCH_MARK in text and text in models.STOCK_PROMPTS
    # the wordings of the test rounds (tests/live_sketch.py); without "expressive faces" (round 3b)
    assert "expressive faces" not in models.SKETCH_ILLUSTRATION and "cel shading" in models.SKETCH_ILLUSTRATION
    # the marker: replaced = the sentence as typed; left in = the generic sentence of the test rounds
    assert bridge.sketch_text(models.SKETCH_PHOTO.replace(models.SKETCH_MARK, "a house")).startswith("Turn this sketch of a house into")
    assert bridge.sketch_text(models.SKETCH_PHOTO).startswith("Turn this sketch into a realistic photograph.")
    assert bridge.sketch_text(models.SKETCH_SCRIBBLE).startswith("Replace the coloured scribbles with what they show, realistic")
    assert models.SKETCH_MARK not in bridge.sketch_text("A " + models.SKETCH_MARK + " here")
    assert bridge.sketch_text("make it night") == "make it night"


def test_manifest_lock_only_the_tab():
    for key in ("flux3", "qwen"):
        assert manifest.mode_alone(key, "sketch") and UPS in manifest.mode_extra(key, "sketch")
    for key in ("flux3", "flux2", "qwen", "fibo"):          # Scribble on photo needs what Sketch needs (plan B)
        assert manifest.mode_extra(key, "scribble") == manifest.mode_extra(key, "sketch"), key
    # Flux 2 writes with qwen3vl 4B since 10.11. (option B): no upsampler, the 4B file locks only its tab
    assert manifest.mode_alone("flux2", "sketch") and manifest.mode_extra("flux2", "sketch") == (VL4,)
    assert not manifest.mode_alone("fibo", "sketch") and manifest.mode_extra("fibo", "sketch") == ()
    assert not manifest.mode_alone("flux3", "upscale")
    import test_settings_ui as su
    from pccomfy import inventory
    nodes = su.NODES | {n["class_type"] for f in (ROOT / "workflows").glob("*.json") for n in json.loads(f.read_text(encoding="utf-8")).values()}
    inv = inventory.Inventory(su.lists_without(clip=UPS), nodes)
    for key in ("flux3", "qwen"):
        assert inv.mode_status(key, "sketch").state == "missing", key
        assert inv.tab_status(key).state == "ready", (key, inv.tab_status(key))     # the model stays offered (user 9.11.)
        row = next(r for r in inv.rows() if r["key"] == key)
        assert [lv for f, _fd, lv in row["files"] if f.name == UPS] == ["optional"], key   # listed with the additional features
    assert inv.mode_status("fibo", "sketch").state == "ready"
    assert inv.mode_status("flux2", "sketch").state == "ready"           # needs no upsampler any more
    assert not any(f.name == UPS for f, _fd, _lv in next(r for r in inv.rows() if r["key"] == "flux2")["files"])
    no4b = inventory.Inventory(su.lists_without(clip=VL4), nodes)
    assert no4b.mode_status("flux2", "sketch").state == "missing" and no4b.tab_status("flux2").state == "ready"
    full = inventory.Inventory(su.td.full_lists(), nodes)
    assert all(full.mode_status(k, "sketch").state == "ready" for k in ("flux3", "flux2", "qwen", "fibo"))


def test_scribble_on_its_own_layer():
    pc, b = doc([photo(), strokes((40, 90, 230))])          # blue: only the layer finds it, the colour search does not
    res = run(pc, b, models.SKETCH_SCRIBBLE)
    assert res["scribble"] == "layer"
    r = res["region"]
    assert (r["w"], r["h"]) != (W, H) and r["x"] > 60, r       # only the crop around the scribble was generated
    assert "what they show" in sent_prompt(b) and models.SKETCH_MARK not in sent_prompt(b)
    d = pc.docs[0]
    top = d.layers[-1]
    assert top["name"].startswith("AI edit") and top.get("mask") is not None
    m = np.asarray(top["mask"])
    assert m[:, : max(0, r["x"] - 1)].max() == 0 and m[60, 145] == 255       # nothing outside the crop, opaque over the scribble
    scribble_layer = next(l for l in d.layers if l.get("name") == "L2")
    assert scribble_layer["visible"] is False                                # hidden after the run (user 9.11.)
    assert next(l for l in d.layers if l.get("name") == "L1")["visible"]
    assert len(pc.docs) == 1                                                 # the throw-away duplicates are closed


def test_scribble_by_colour():
    base = photo()
    base.alpha_composite(strokes((252, 2, 2), box=(20, 20, 70, 70), width=3))
    pc, b = doc([base])
    res = run(pc, b, models.SKETCH_SCRIBBLE.replace(models.SKETCH_MARK, "a red vintage car"))
    assert res["scribble"] == "red" and res["region"]["x"] < 40
    assert "a red vintage car" in sent_prompt(b)
    # green wins over red (decided 9.11.)
    base = photo()
    base.alpha_composite(strokes((252, 2, 2), box=(20, 20, 70, 70), width=3))
    base.alpha_composite(strokes((0, 255, 0), box=(130, 40, 180, 90), width=3))
    pc, b = doc([base])
    res = run(pc, b, models.SKETCH_SCRIBBLE)
    assert res["scribble"] == "green" and res["region"]["x"] > 80


def test_no_scribble_no_run():
    pc, b = doc([photo()])
    try:
        run(pc, b, models.SKETCH_SCRIBBLE)
    except BridgeError as e:
        assert str(e) == models.NO_SCRIBBLE
    else:
        raise AssertionError("ran without a scribble")
    assert b.comfy.graphs == [] and len(pc.docs[0].layers) == 1
    # a filled shape on its own layer is no scribble layer (rule "thin strokes", user 9.11.)
    blob = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    blob.paste((40, 90, 230, 255), (100, 20, 170, 90))
    pc, b = doc([photo(), blob])
    try:
        run(pc, b, models.SKETCH_SCRIBBLE)
        raise AssertionError("a filled blob counted as a scribble")
    except BridgeError as e:
        assert str(e) == models.NO_SCRIBBLE


def test_whole_sketch():
    pc, b = doc([photo()])
    res = run(pc, b, models.SKETCH_PHOTO, scribble_on=False)
    assert res["scribble"] == "" and (res["region"]["w"], res["region"]["h"]) == (W, H)
    assert sent_prompt(b).startswith("Turn this sketch into")
    top = pc.docs[0].layers[-1]
    assert top.get("mask") is None and len(pc.docs[0].layers) == 2           # a new layer on top, no layer mask
    # Fibo without a writer: the text goes in as it is
    pc, b = doc([photo()])
    run(pc, b, models.SKETCH_PHOTO.replace(models.SKETCH_MARK, "a barn"), wf="fibo2-edit.json", scribble_on=False, enhance=False)
    assert "a barn" in json.dumps(b.comfy.graphs[-1])


def test_window():
    import shutil
    import test_gui_presets as t
    gui, cfgmod = t.gui, t.cfgmod
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in gui.models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names

    def pick(model, mode):
        app.v_model.set(model)
        app.v_mode.set(mode)
        app._on_model()

    def tab(key):
        app.v_edtab.set(key)
        app._edtab_clicked()

    def prompt():
        return app.t_prompt.get("1.0", "end").strip()

    def where(key):         # (row, column) from the row layout (one frame per row since 10.11.); None when not shown
        if app.rb_edtabs[key].__dict__.get("_grid") is None:
            return None
        return next((r, row.index(key)) for r, row in enumerate(app._edtab_layout) if key in row)

    pick("flux3", "edit")
    app._edtabs_ensure()
    for rb in app.rb_edtabs.values():      # the stub keeps no grid places: record them (as test_model_chip_menu)
        rb.grid = lambda *a, w=rb, **k: w.__dict__.__setitem__("_grid", (k["row"], k["column"]))
        rb.grid_remove = lambda w=rb: w.__dict__.pop("_grid", None)
    app._edtabs_update()
    # plan B (10.11.): the edit tabs in the first row, Sketch to image and Scribble on photo in the second (Flux 3 with
    # Insert reference until it moves under Fill)
    assert [where(k) for k in ("edit", "multi", "bbox", "sketch", "scribble")] == [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1)]
    app.t_prompt.delete("1.0", "end")
    tab("sketch")
    assert app.v_mode.get() == "sketch" and app.v_fn.get() == "edit"
    assert prompt() == "", repr(prompt()[:80])                       # no style chosen yet: empty with the grey placeholder
    assert app._hint_text == models.SKETCH_TIP
    assert not app._llm_row_wanted()                                               # no LLM row: the writer always runs
    app._apply_style(models.SKETCH_PHOTO, "Realistic photo")
    req = app._request()
    assert req.mode == "edit" and req.enhance and not req.scribble and req.workflow.endswith("flux3-klein-sketch.json")
    tab("scribble")
    assert app.v_mode.get() == "scribble" and app.v_fn.get() == "edit"
    assert prompt() == models.SKETCH_SCRIBBLE and app.v_sketch.get() == "Scribble on photo" and app._hint_text == models.SCRIBBLE_TIP
    req = app._request()
    assert req.scribble and req.enhance and req.mode == "edit" and req.workflow.endswith("flux3-klein-sketch.json")
    tab("sketch")                                                    # the style chosen last comes back
    assert prompt() == models.SKETCH_PHOTO and not app._request().scribble
    # Flux 2 (no Insert reference): 2 + 2
    pick("flux2", "sketch")
    assert app.v_mode.get() == "sketch" and app.v_edtab.get() == "sketch"
    assert [where(k) for k in ("edit", "multi", "sketch", "scribble")] == [(0, 0), (0, 1), (1, 0), (1, 1)] and where("bbox") is None
    # Fibo: no writer, so no LLM enhancement
    pick("fibo", "sketch")
    req = app._request()
    assert not req.enhance and req.workflow.endswith("fibo2-edit.json")
    # a model without Sketch: back to Edit canvas
    pick("krea2", "txt2img")
    pick("flux3", "sketch")
    pick("moss", "txt2img")
    assert app.v_mode.get() == "txt2img"
    # an edited text stays when the tab changes
    pick("qwen", "scribble")
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", "Replace the coloured scribbles with a dog")
    pick("qwen", "edit")
    assert prompt() == "Replace the coloured scribbles with a dog"
    # an old saved Sketch run with the scribble sentence loads into the tab Scribble on photo
    from pccomfy import history as runhistory
    before = {k: v for k, v in app._collect().items() if k != "edit_tabs"}       # saved before plan B: no version
    old = runhistory.entry("Sketch 3", "Qwen Image 2.1", {**before, "mode": "sketch",
                                                           "prompt": models.SKETCH_SCRIBBLE.replace(models.SKETCH_MARK, "a dog")})
    app.load_history(old)
    assert app.v_mode.get() == "scribble" and app._request().scribble
    # a Sketch run from the history (way A, user 10.11.): the written prompt runs as it is, without the upsampler
    from pccomfy import history as runhistory
    pick("flux2", "sketch")
    assert app._request().enhance
    written = "A realistic photograph of a red barn in a green summer meadow, soft morning light."
    e = runhistory.entry("Sketch", "Flux 2 Klein Edit", app._collect(), llm=written)
    pick("qwen", "edit")
    app.load_history(e)
    assert app.v_model.get() == "flux2" and app.v_mode.get() == "sketch" and prompt() == written
    assert not app._request().enhance and app._hint_text == models.WRITTEN_TIP
    app.t_prompt.insert("end", " A dog.")                     # an edited written prompt still runs as it is
    assert not app._request().enhance
    app._history_begin(app._request())                        # the run keeps it as written: it loads back the same way
    assert app._hist_run["llm"].endswith("A dog.")
    app._apply_style(models.SKETCH_PHOTO, "Realistic photo")  # a style: the writer again
    assert app._request().enhance and app._hint_text == models.SKETCH_TIP
    app.load_history(e)
    pick("flux3", "sketch")                                   # another model: the upsampler again
    assert app._request().enhance
    app.load_history(e)
    app.v_edtab.set("edit")                                   # another tab
    app._edtab_clicked()
    app.v_edtab.set("sketch")
    app._edtab_clicked()
    assert app._request().enhance
    e_plain = runhistory.entry("Sketch", "Flux 2 Klein Edit", e["settings"])      # a run without a written prompt
    app.load_history(e_plain)
    assert app._request().enhance
    # the tab Sketch is greyed out without the upsampler, the model stays offered (user 9.11.)
    import test_settings_ui as su
    from pccomfy import inventory
    nodes = su.NODES | {n["class_type"] for f in (ROOT / "workflows").glob("*.json") for n in json.loads(f.read_text(encoding="utf-8")).values()}
    app._apply_refresh({"_detect": True, "_inv": inventory.Inventory(su.lists_without(clip=UPS), nodes)})
    pick("flux3", "edit")
    app._edtabs_update()
    for k in ("sketch", "scribble"):       # both tabs of the writer (plan B)
        assert str(app.rb_edtabs[k].cget("state")) == "disabled" and UPS in app.tt_edtabs[k].text, k
    pick("flux2", "edit")                   # Flux 2 writes with qwen3vl 4B (10.11.): no upsampler needed
    app._edtabs_update()
    assert str(app.rb_edtabs["sketch"].cget("state")) == str(app.rb_edtabs["scribble"].cget("state")) == "normal"
    pick("fibo", "edit")
    app._edtabs_update()
    assert str(app.rb_edtabs["sketch"].cget("state")) == "normal"


def test_edtab_rows():
    """The tabs under Edit in rows (user 10.11.): as few rows as fit, larger rows first, no text cut."""
    from pccomfy.refslots import edtab_rows
    assert edtab_rows([80, 100, 100], 300) == [[0, 1, 2]]                  # three fit: one row
    assert edtab_rows([80, 100, 100, 60], 360) == [[0, 1, 2, 3]]           # four fit: one row
    assert edtab_rows([80, 100, 100, 60], 300) == [[0, 1], [2, 3]]         # four do not: 2 + 2, never 3 + 1
    assert edtab_rows([120, 130, 90], 250) == [[0, 1], [2]]                # 2 + 1: the first row is the larger one
    assert edtab_rows([120, 130, 90], 200) == [[0], [1], [2]]
    assert edtab_rows([500], 300) == [[0]]                                 # wider than the room: still shown
    for needs, room in (([70, 95, 95, 50], 309), ([90, 120, 120, 60], 270), ([70, 95, 50], 230)):
        for row in edtab_rows(needs, room):
            assert len(row) == 1 or sum(needs[i] for i in row) <= room, (needs, room, row)


def main():
    test_window()           # first: importing test_settings_ui swaps the stub's Text for one that reads back empty
    test_models_and_texts()
    test_edtab_rows()
    test_manifest_lock_only_the_tab()
    test_scribble_on_its_own_layer()
    test_scribble_by_colour()
    test_no_scribble_no_run()
    test_whole_sketch()
    print("ALL OK (sketch mode)")


if __name__ == "__main__":
    main()
