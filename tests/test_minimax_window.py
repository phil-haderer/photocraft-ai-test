"""MiniMax H3 Image in the window (PLAN 2.0b, step 3): the size row (4 / 8 / 12 / 16 / 20 MP) and the tick "Downsize to
canvas" are shown only for MiniMax Text to image, where "Use canvas size up to" goes away; they start at 4 MP and off,
travel with saved settings, and go into the request (off = a new document). Other models send gen_mp 0.

    python tests/test_minimax_window.py
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_gui_presets as t  # noqa: E402  (installs the Tk stub and a temporary PCCOMFY_HOME)

gui, cfgmod = t.gui, t.cfgmod
from pccomfy import models  # noqa: E402


def rec(widget, name):
    calls = []
    setattr(widget, name, lambda *a, **k: calls.append((name, k)))
    return calls


def main():
    app = gui.App(cfgmod.load())
    wfdir = Path(app.workflows_dir)
    wfdir.mkdir(parents=True, exist_ok=True)
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    for f in names:
        shutil.copy(t.ROOT / "workflows" / f, wfdir / f)
    app.cb_workflow["values"] = [gui.BUILTIN] + names

    def pick(key, mode):
        app.v_model.set(key)
        app.v_mode.set(mode)
        app._on_model()

    shown, hidden = rec(app.f_gen, "pack"), rec(app.f_gen, "pack_forget")
    native_hidden = rec(app.f_native, "pack_forget")
    pick("minimax", "txt2img")
    assert app._gen_wanted() and shown and native_hidden, "size row shown, canvas limit hidden"
    assert sorted(app.rb_gen) == list(models.GEN_MP_STEPS) and app.cb_downsize["text"] == "Downsize to canvas"
    assert app.v_gen_mp.get() == 4 and app.v_downsize.get() is False          # the start values (user 10.11.)
    req = app._request()
    assert req.mode == "txt2img" and req.gen_mp == 4.0 and req.new_document is True and req.enhance is False
    app.v_gen_mp.set(16)
    app.v_downsize.set(True)
    req = app._request()
    assert req.gen_mp == 16.0 and req.new_document is False
    s = app._collect()
    assert s["gen_mp"] == 16 and s["downsize"] is True
    app._save_state(req)
    assert cfgmod.load_state().get("gen_mp") == 16 and cfgmod.load_state().get("downsize") is True

    for key in ("flux3", "flux2", "qwen", "fibo", "krea2", "moss"):      # the others: no size row, the usual canvas rule
        shown.clear(), hidden.clear()
        pick(key, "txt2img")
        assert not app._gen_wanted() and hidden, key
        assert app._request().gen_mp == 0.0 and app._request().new_document is False, key

    pick("minimax", "txt2img")          # back to MiniMax: its start values again, applied settings travel
    assert app.v_gen_mp.get() == 4 and app.v_downsize.get() is False
    app._apply_settings({"mode": "txt2img", "gen_mp": 12, "downsize": True})
    assert app.v_gen_mp.get() == 12 and app.v_downsize.get() is True
    # Edit and Multi image edit (step 4, user 11.11.): the same row, "Downsize to canvas" starts ON (a layer in the canvas)
    for mode in ("edit", "multi_edit"):
        pick("minimax", mode)
        assert app._gen_wanted() and app.v_gen_mp.get() == 4 and app.v_downsize.get() is True, mode
        req = app._request()
        assert req.mode == "edit" and req.gen_mp == 4.0 and req.new_document is False and req.enhance is False, mode
        app.v_downsize.set(False)
        assert app._request().new_document is True, mode        # off = a new document in full size
    pick("minimax", "txt2img")      # and back: Text to image starts off again
    assert app.v_downsize.get() is False and app._request().new_document is True
    pick("minimax", "edit")
    assert app.v_downsize.get() is True
    pick("qwen", "edit")
    assert not app._gen_wanted() and app._request().gen_mp == 0.0 and app._request().new_document is False
    print("ALL OK (MiniMax window)")


if __name__ == "__main__":
    main()
