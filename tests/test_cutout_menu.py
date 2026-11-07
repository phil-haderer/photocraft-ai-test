"""The scissors with a model menu (user 6.11., PLAN: Cutout-Knopf): BiRefNet, RMBG-2.0, Both; the edge colour clean-up (imaging.defringe);
the manifest entry of rmbg-2.0.safetensors. Against the fake PhotoCraft and ComfyUI and the Tk stub.

    python tests/test_cutout_menu.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402
from pccomfy import bridge, imaging, manifest, workflows  # noqa: E402
import test_reference_mode as T  # noqa: E402


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def workflow_checks():
    bi = workflows.load_template(workflows.BIREFNET_WORKFLOW)
    rm = workflows.load_template(workflows.RMBG2_WORKFLOW)
    assert links_ok(rm) and bridge.has_tag(rm, "image") and bridge.has_tag(rm, "output")
    assert {n["class_type"] for n in rm.values()} == {n["class_type"] for n in bi.values()}
    assert next(n for n in rm.values() if n["class_type"] == "LoadBackgroundRemovalModel")["inputs"]["bg_removal_name"] == "rmbg-2.0.safetensors"
    assert next(n for n in bi.values() if n["class_type"] == "LoadBackgroundRemovalModel")["inputs"]["bg_removal_name"] == "birefnet.safetensors"
    # the foreground mask is inverted before it becomes the alpha channel, as for BiRefNet
    inv = next(n for n in rm.values() if n["class_type"] == "InvertMask")
    assert rm[inv["inputs"]["mask"][0]]["class_type"] == "RemoveBackground"
    assert [m[0] for m in workflows.CUTOUT_MODELS] == ["birefnet", "rmbg2"] and workflows.CUTOUT_BOTH == ("birefnet", "rmbg2")
    assert [m[1] for m in workflows.CUTOUT_MODELS] == ["BiRefNet", "RMBG-2.0"]
    try:
        workflows.cutout_model("sam3")
        raise SystemExit("an unknown model is an error")
    except ValueError:
        pass


def manifest_checks():
    f = manifest.FILES["rmbg-2.0.safetensors"]
    assert f.kind == "bg_removal" and f.size == 884878856 and len(f.sha256) == 64 and f.sha256.startswith("566ed80c")
    assert f.url.startswith("https://huggingface.co/") and f.url.endswith("RMBG-2.0/model.safetensors")
    assert "non-commercial" in f.note
    for m in workflows.CUTOUT_MODELS:      # every menu file is a manifest file, optional in every model
        assert m[2] in manifest.FILES
    for tab in manifest.TABS.values():
        spec = tab.modes.get("multi_edit")
        if spec is not None:
            assert "rmbg-2.0.safetensors" in spec.optional and "birefnet.safetensors" in spec.optional, tab


def defringe_checks():
    # a red subject on a white wall: the edge pixels are a mix of both, as a cut-out from a soft mask leaves them
    w, h = 80, 60
    alpha = np.zeros((h, w), np.float32)
    alpha[15:45, 20:60] = 1.0
    for d in range(1, 4):                                   # a soft edge three pixels wide on every side
        f = 1 - d / 4
        alpha[15 - d, 20:60] = alpha[44 + d, 20:60] = f
        alpha[15:45, 20 - d] = alpha[15:45, 59 + d] = f
    red, wall = np.array([200, 30, 30], np.float32), np.array([240, 240, 240], np.float32)
    rgb = alpha[..., None] * red + (1 - alpha[..., None]) * wall
    im = Image.fromarray(rgb.astype("uint8"), "RGB")
    im.putalpha(Image.fromarray((alpha * 255).astype("uint8")))
    out = imaging.defringe(im)
    assert out.mode == "RGBA" and out.size == im.size
    assert out.getchannel("A").tobytes() == im.getchannel("A").tobytes()          # alpha is never touched
    a_edge = (np.asarray(im.getchannel("A")) > 20) & (np.asarray(im.getchannel("A")) < 235)
    before = np.asarray(im.convert("RGB"), np.float32)[a_edge]
    after = np.asarray(out.convert("RGB"), np.float32)[a_edge]
    assert before[:, 1].mean() > 100 and after[:, 1].mean() < 45, (before[:, 1].mean(), after[:, 1].mean())   # the wall's light grey is gone
    assert np.abs(after - red).max() < 25                                          # the edge carries the subject's own colour
    core = np.asarray(im.getchannel("A")) == 255                                    # the inside keeps its pixels (not the 2 px next to the edge)
    inner = np.zeros_like(core)
    inner[20:40, 25:55] = True
    assert np.array_equal(np.asarray(out.convert("RGB"))[inner], np.asarray(im.convert("RGB"))[inner])
    on_black = Image.new("RGBA", im.size, (0, 0, 0, 255))
    on_black.alpha_composite(out)
    assert np.asarray(on_black.convert("RGB"))[a_edge][:, 1].mean() < 30            # no bright rim on black
    # nothing to do: not RGBA, empty, fully opaque, no sure inside
    rgb_only = Image.new("RGB", (10, 10), (1, 2, 3))
    assert imaging.defringe(rgb_only) is rgb_only
    empty = Image.new("RGBA", (10, 10), (9, 9, 9, 0))
    assert imaging.defringe(empty) is empty
    solid = Image.new("RGBA", (10, 10), (9, 9, 9, 255))
    assert imaging.defringe(solid) is solid
    faint = Image.new("RGBA", (10, 10), (9, 9, 9, 100))
    assert imaging.defringe(faint).tobytes() == faint.tobytes()
    # a big picture is worked on at a smaller size and comes back at its own size
    big = Image.new("RGBA", (3000, 2000), (240, 240, 240, 0))
    big.paste((200, 30, 30, 255), (800, 500, 2200, 1500))
    assert imaging.defringe(big).size == (3000, 2000)
    # the footer's cut-out and the slots' cut-out both clean the edge
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    b.comfy.output_images = lambda hist, node_id=None: [im]
    got = b.remove_background(Image.new("RGB", im.size), crop=False)
    assert np.asarray(got.convert("RGB"))[a_edge][:, 1].mean() < 45


class ModelComfy(T.FakeComfy):
    """Gives each model's run its own result: the green of BiRefNet, the blue of RMBG-2.0 (told apart by the model file in the graph)."""
    def output_images(self, hist, node_id=None):
        g = self.graphs[-1]
        name = next(n for n in g.values() if n["class_type"] == "LoadBackgroundRemovalModel")["inputs"]["bg_removal_name"]
        colour = (0, 255, 0, 255) if name == "birefnet.safetensors" else (0, 0, 255, 255)
        im = Image.new("RGBA", self.last_size, (255, 0, 0, 0))
        im.paste(colour, (10, 5, 25, 20))
        return [im]

    def upload_image(self, image, name):
        self.last_size = image.size
        return super().upload_image(image, name)


def bridge_checks():
    def names(pc):
        return {l["id"]: l.get("name") for l in pc.docs[0].layers}
    # one model: one layer named after it
    for key, label, file, _wf in workflows.CUTOUT_MODELS:
        pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
        b.comfy = ModelComfy()
        old = {l["id"] for l in pc.docs[0].layers}
        res = b.remove_background_layer(None, (key,))
        new = [l for l in pc.docs[0].layers if l["id"] not in old]
        assert len(new) == 1 and new[0]["name"] == f"Background removed ({label})" and res["layers"] == [new[0]["id"]], (key, new)
        g = b.comfy.graphs[0]
        assert next(n for n in g.values() if n["class_type"] == "LoadBackgroundRemovalModel")["inputs"]["bg_removal_name"] == file
    # the default is still BiRefNet
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = ModelComfy()
    b.remove_background_layer()
    assert b.comfy.graphs[0] and any(n["inputs"].get("bg_removal_name") == "birefnet.safetensors" for n in b.comfy.graphs[0].values())
    # Both: two layers, BiRefNet below, RMBG-2.0 on top, one run each, one bar over both
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = ModelComfy()
    old = {l["id"] for l in pc.docs[0].layers}
    fracs = []
    res = b.remove_background_layer(lambda f, m, **kw: fracs.append(f), workflows.CUTOUT_BOTH)
    stack = pc.docs[0].layers                                                   # bottom first (the fake's order)
    new = [l for l in stack if l["id"] not in old]
    assert [l["name"] for l in new] == ["Background removed (BiRefNet)", "Background removed (RMBG-2.0)"], [l["name"] for l in new]
    assert stack[-1]["id"] == new[1]["id"] and stack.index(new[0]) < stack.index(new[1])     # RMBG-2.0 is the top layer
    assert new[0]["img"].getpixel((12, 8)) == (0, 255, 0, 255) and new[1]["img"].getpixel((12, 8)) == (0, 0, 255, 255)
    assert len(b.comfy.graphs) == 2 and res["layers"] == [l["id"] for l in new] and res["layer"] == new[1]["id"]
    assert fracs == sorted(fracs) and max(fracs) <= 1.0                         # the bar never runs back
    # a bad model name, or none, fails before anything is sent
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = ModelComfy()
    for bad in (("sam3",), ()):
        try:
            b.remove_background_layer(None, bad)
            raise SystemExit("must fail")
        except (ValueError, bridge.BridgeError):
            pass
    assert not b.comfy.graphs and not b.comfy.uploads


def gui_checks():
    import test_gui_presets as t  # noqa: E402
    gui = t.gui
    app = gui.App(t.cfgmod.load())
    assert app.b_cut.cget("command") is not None and "BiRefNet" in gui.CUTOUT_TIP and "RMBG-2.0" in gui.CUTOUT_TIP

    class Inv:
        def __init__(self, files):
            self.files = set(files)

        def has(self, name):
            return name in self.files

    # both files there: three entries, all clickable
    app.inv = Inv({"birefnet.safetensors", "rmbg-2.0.safetensors"})
    rows = app._cutout_rows()
    assert [r[0] for r in rows] == ["BiRefNet", "RMBG-2.0", "Both"] and [r[2] for r in rows] == ["item"] * 3, rows

    class B:
        def __init__(self):
            self.calls = []
        reset_cancel_all = lambda self: None   # noqa: E731

        def remove_background_layer(self, progress, models):
            self.calls.append(tuple(models))
            return {"layer": 1}
    for row, want in zip(rows, (("birefnet",), ("rmbg2",), ("birefnet", "rmbg2"))):
        app.bridge = B()
        app._running = False
        row[1]()
        app.worker.join(5)
        assert app.bridge.calls == [want], (row[0], app.bridge.calls)
        done = []
        while True:
            try:
                ev = app.events.get_nowait()
            except Exception:
                break
            if ev[0] == "done":
                done.append(ev[1])
        assert done and done[-1].startswith("Done · background removed, ") and ("2 new layers" in done[-1]) == (len(want) == 2), done
    # RMBG-2.0 missing: its entry and "Both" are greyed out, BiRefNet works, the scissors stays enabled
    app.inv = Inv({"birefnet.safetensors"})
    rows = app._cutout_rows()
    assert [(r[0], r[2], r[1] is None) for r in rows] == [("BiRefNet", "item", False), ("RMBG-2.0 (file missing)", "disabled", True),
                                                          ("Both (file missing)", "disabled", True)], rows
    app._update_cut_button()
    assert app.b_cut.cget("state") == "normal" and app.tt_cut.text == gui.CUTOUT_TIP
    # only RMBG-2.0: BiRefNet is greyed out; a click on a missing model says so and starts nothing
    app.inv = Inv({"rmbg-2.0.safetensors"})
    rows = app._cutout_rows()
    assert rows[0][2] == "disabled" and rows[1][2] == "item" and rows[2][2] == "disabled"
    app.bridge = B()
    app._running = False
    app.cut_background(("birefnet",))
    assert app.bridge.calls == [] and app._running is False
    # no file at all: greyed out with the tooltip naming both files, the click only says so
    app.inv = Inv(set())
    app._update_cut_button()
    assert app.b_cut.cget("state") == "disabled" and "birefnet.safetensors" in app.tt_cut.text and "rmbg-2.0.safetensors" in app.tt_cut.text
    opened = []
    gui_run = sys.modules[type(app).__mro__[0].__module__.rsplit(".", 1)[0] + ".gui_run"]
    real = gui_run.ListPopup
    gui_run.ListPopup = lambda *a, **k: opened.append(a) or type("P", (), {"closed": False, "close": lambda s: None})()
    try:
        app._cutout_menu()
        assert opened == [], "no model file: no menu"
        app.inv = Inv({"birefnet.safetensors", "rmbg-2.0.safetensors"})
        app._cutout_menu()
        assert len(opened) == 1 and [r[0] for r in opened[0][2]] == ["BiRefNet", "RMBG-2.0", "Both"]
        app._cutout_menu()      # a second click closes it
        assert len(opened) == 1
    finally:
        gui_run.ListPopup = real


def main():
    workflow_checks()
    manifest_checks()
    defringe_checks()
    bridge_checks()
    gui_checks()
    print("test_cutout_menu: ok")


if __name__ == "__main__":
    main()
