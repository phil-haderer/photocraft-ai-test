"""The tabs under Edit (Edit canvas / Multi image edit / Insert reference; Sketch to image / Scribble on photo, plan B 10.11.)
and the chosen model chip in the real
window (user 10.11.): no tab text is cut (the chosen one is bold), every row uses the full width, and a chosen chip is blue
to its edge (no dark ring inside the blue border). Real Tk window (hidden); skipped when Tk cannot open a window.

    python tests/test_edit_tabs_window.py
"""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP = tempfile.mkdtemp(prefix="pccomfy-edtabs-")
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

import tkinter.font as tkfont  # noqa: E402

from pccomfy import config as cfgmod  # noqa: E402
from pccomfy import gui, models  # noqa: E402
from pccomfy.gui_common import font  # noqa: E402


def check_tabs(app, model):
    app.v_model.set(model)
    app.v_mode.set("edit")
    app._on_model()
    app.root.update()
    bold = tkfont.Font(root=app.root, font=font(9, bold=True))
    plain = tkfont.Font(root=app.root, font=font(9))
    rows = app._edtab_layout
    assert rows and rows[0], (model, rows)
    full = app.f_edtabs.winfo_width()
    for r, row in enumerate(rows):
        frame = app.f_edtab_rows[r]
        assert frame.winfo_width() == full, (model, r, frame.winfo_width(), full)      # every row the full width
        right = 0
        for k in row:
            rb = app.rb_edtabs[k]
            label = dict(app.EDIT_TABS)[k]
            need = rb.winfo_reqwidth() - plain.measure(label) + bold.measure(label)
            assert rb.winfo_width() >= need, (model, k, rb.winfo_width(), need)      # the bold text fits: nothing cut
            right = max(right, rb.winfo_x() + rb.winfo_width())
        assert full - right <= 2 * 4, (model, r, full, right)                         # the last tab reaches the right edge
    if "sketch" in models.BY_KEY[model].modes:      # MiniMax has Edit and Multi image edit only (step 4): one row of two
        assert rows[-1] == ["sketch", "scribble"], (model, rows)                     # plan B: the second pair has its own row
    if len(sum(rows, [])) == 4:
        assert rows == [["edit", "multi"], ["sketch", "scribble"]], rows              # four: always 2 + 2 (plan B, 10.11.)
    return rows


def main():
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    names = sorted({w for m in models.MODELS for w in m.workflows()})
    app.cb_workflow["values"] = [gui.BUILTIN] + names

    # the chosen chip: blue to its edge (the inner ring of clam follows the fill)
    st = gui.ttk.Style(app.root)
    for opt in ("background", "lightcolor", "darkcolor", "bordercolor"):
        assert st.lookup("Chip.Toolbutton", opt, ["selected"]) == gui.ACCENT, opt

    seen = {}
    for m in models.MODELS:
        if "multi_edit" in m.modes or "sketch" in m.modes:
            seen[m.key] = check_tabs(app, m.key)
    assert "flux3" in seen and len(sum(seen["flux3"], [])) == 5, seen      # with Insert reference until it moves under Fill
    assert all(seen[k] == [["edit", "multi"], ["sketch", "scribble"]] for k in ("flux2", "qwen", "fibo")), seen
    assert seen["minimax"] == [["edit", "multi"]], seen

    # the looks swapped (user 10.11.): the tabs filled grey like the small switches, the Sketch templates outlined like the
    # model chips; and every row of buttons starts at the same left edge as the model chips
    assert all(str(rb["style"]) == "Small.Toolbutton" for rb in app.rb_edtabs.values())
    assert all(str(rb["style"]) == "Chip.Toolbutton" for rb in app.rb_sketch.values())
    app.v_model.set("flux3")
    app.v_mode.set("edit")
    app._on_model()
    app.v_edtab.set("scribble")
    app._edtab_clicked()
    app.root.geometry("+-4000+-4000")      # shown off-screen: a withdrawn window is never laid out (its canvas body sits 1 px off)
    app.root.deiconify()
    app.root.update()
    left =app.rb_tabs[models.MODELS[0].key].winfo_rootx()
    firsts = {"function": app.rb_modes["edit"], "tab": app.rb_edtabs["edit"]}
    assert not app.f_sketch.winfo_manager()     # one chip only repeats the tab "Scribble on photo": no chip row yet (user 10.11.)
    for name, w in firsts.items():
        assert w.winfo_manager() and w.winfo_rootx() == left, (name, w.winfo_rootx(), left)
    app.root.destroy()
    print("ALL OK (Edit tabs and chip fill in the real window)")


if __name__ == "__main__":
    main()
