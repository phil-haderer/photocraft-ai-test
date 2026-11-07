"""Copy canvas to clipboard (L3, header button, user 29.10. option A): the visible layers of the active picture as one
image, through the export a run makes; hidden layers stay out, the document is left as it was. The window's button
against the Tk stub with a fake clipboard.

    python tests/test_copy_canvas.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy.bridge import BridgeError  # noqa: E402


def bridge_checks():
    pc, _, b = T.make(tempfile.mkdtemp())
    d = pc.docs[0]
    ids0, sel0 = [l["id"] for l in d.layers], d.sel.copy()
    img = b.canvas_image()
    assert img.size == (T.W, T.H) and T.has_yellow(img)                     # the top layer is in it
    assert [l["id"] for l in d.layers] == ids0 and len(pc.docs) == 1           # the duplicate is gone, nothing changed
    assert np.array_equal(np.asarray(d.sel), np.asarray(sel0))                # the selection stays

    d.layers[-1]["visible"] = False                                           # a hidden layer is not copied
    assert not T.has_yellow(b.canvas_image())

    pc.docs.clear()
    pc.active = None                                                          # (PhotoCraft without a document)
    try:
        b.canvas_image()
        raise AssertionError("no document must raise")
    except BridgeError as e:
        assert "Open a document" in str(e)


def gui_checks():
    import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)
    gui = t.gui
    app = gui.App(t.cfgmod.load())
    put = []
    gui.clipboard.write_image = lambda img, **k: put.append(img) or True

    class B:
        def canvas_image(self):
            return "picture"
    app.bridge = B()
    app.copy_canvas()
    app.worker.join(5)
    assert put == ["picture"]
    assert app.events.get_nowait() == ("note", "Canvas copied to the clipboard.")

    class Bad:
        def canvas_image(self):
            raise BridgeError("Open a document in PhotoCraft first.")
    app.bridge = Bad()
    app.copy_canvas()
    app.worker.join(5)
    kind, msg = app.events.get_nowait()
    assert kind == "note-error" and msg == "Error: Open a document in PhotoCraft first.", (kind, msg)

    gui.clipboard.write_image = lambda img, **k: False
    app.bridge = B()
    app.copy_canvas()
    app.worker.join(5)
    assert app.events.get_nowait()[0] == "note-error"


def cut_checks():
    """The scissors beside the clock (user 5.11.): runs Bridge.remove_background_layer in the worker like a generation; greyed out
    while ComfyUI is read and has no birefnet.safetensors."""
    import test_gui_presets as t  # noqa: E402
    gui = t.gui
    app = gui.App(t.cfgmod.load())
    assert app.b_cut.cget("image") and app.b_cut.cget("state") != "disabled" and app.tt_cut.text == gui.CUTOUT_TIP

    class B:
        def __init__(self):
            self.calls = 0
        reset_cancel_all = lambda self: None   # noqa: E731

        def remove_background_layer(self, progress, models=("birefnet",)):
            self.calls += 1
            progress(0.5, "Cutting out the background")
            progress(0.6, "KSampler 1/1", phase="image", phase_fraction=0.5)
            return {"layer": 9}
    app.bridge = B()
    app.cut_background()
    app.worker.join(5)
    kinds = []
    while True:
        try:
            kinds.append(app.events.get_nowait())
        except Exception:
            break
    assert app.bridge.calls == 1 and kinds[0][0] == "progress" and kinds[-1][0] == "done" and kinds[-1][1].startswith("Done"), kinds
    img_ev = [k[1] for k in kinds if k[0] == "progress" and k[1][1] == "Removing background"]
    assert img_ev and img_ev[0][2] == "stage", kinds      # the status line says "Removing background", not "<model> is generating"
    app._set_progress(*img_ev[0])
    assert app.v_pl.get().startswith("Removing background") and "generating" not in app.v_pl.get(), app.v_pl.get()
    assert app._running is True            # the "done" event (_poll) ends the run state like after a generation

    class Bad(B):
        def remove_background_layer(self, progress, models=("birefnet",)):
            raise BridgeError("Open a document in PhotoCraft first.")
    app._running = False
    app.bridge = Bad()
    app.cut_background()
    app.worker.join(5)
    done = [k for k in iter(lambda: next_event(app), None) if k[0] == "done"]
    assert done and done[-1][1] == "Error: Open a document in PhotoCraft first.", done

    class Inv:      # ComfyUI was read and the file is not there: greyed out, the tooltip names it, a click only says so
        def has(self, name):
            return False
    app.inv = Inv()
    app._update_cut_button()
    assert app.b_cut.cget("state") == "disabled" and "birefnet.safetensors" in app.tt_cut.text
    app.bridge = B()
    app.cut_background()
    assert app.bridge.calls == 0

    class Inv2(Inv):
        def has(self, name):
            return True
    app.inv = Inv2()
    app._update_cut_button()
    assert app.b_cut.cget("state") == "normal" and app.tt_cut.text == gui.CUTOUT_TIP


def next_event(app):
    try:
        return app.events.get_nowait()
    except Exception:
        return None


def main():
    bridge_checks()
    gui_checks()
    cut_checks()
    print("test_copy_canvas: ok")


if __name__ == "__main__":
    main()
