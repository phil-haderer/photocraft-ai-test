"""The search window of the chain symbol (user 7.11.): filter by every typed word, alphabetical, copies of the expected file first with
a line below them. The window itself needs a real Tk; this pins the ordering and that the settings code uses the window.

    python tests/test_linkpicker.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import linkpicker  # noqa: E402

FILES = ["moss_image_sft_int8_convrot.safetensors", "Zeta.safetensors", "alpha.safetensors", "Moss\\x.safetensors",
         "beta\\Alpha_two.safetensors", "my_moss_copy.safetensors"]


def real_tk_checks():
    """The window in real Tk (skipped when there is no display): the list is as wide as its longest name, the file in use is green, a click
    outside closes it, a click inside does not, and the plugin's own binding on "all" survives."""
    import time
    import tkinter as tk
    try:
        root = tk.Tk()
    except tk.TclError:
        print("  (no display: window checks skipped)")
        return
    try:
        root.withdraw()
        btn = tk.Button(root, text="x")
        hits = []
        root.bind_all("<ButtonPress>", lambda e: hits.append(1), add="+")
        long = "flux/" + "x" * 90 + "_model_int8_convrot.safetensors"
        p = linkpicker.LinkPicker(root, (50, 50), [long, "a.safetensors", "moss.safetensors"], ["moss.safetensors"],
                                  {"moss.safetensors": "in use"}, None, strong=["moss.safetensors"])
        t0 = time.time()
        while time.time() - t0 < 0.4:
            root.update()
        lines = p.lb.get(0, "end")
        assert lines[0].startswith("● moss.safetensors") and "(in use)" in lines[0] and lines[1].startswith("─"), lines
        assert p.lb.itemcget(0, "foreground") != p.lb.itemcget(2, "foreground")                      # the file in use stands out
        import tkinter.font as tkfont
        need = tkfont.Font(root=root, font=linkpicker.font(9)).measure(lines[-1])
        assert p.lb.winfo_reqwidth() >= need, (p.lb.winfo_reqwidth(), need)                           # no name is cut off
        assert p._outside_id
        e = type("E", (), {})()
        e.widget = p.lb
        p._outside(e)
        assert not p.closed                                                                           # a click inside stays
        e.widget = btn
        p._outside(e)
        assert p.closed                                                                               # a click outside closes
        script = str(root.tk.call("bind", "all", "<ButtonPress>"))
        assert "lambda" in script and "_outside" not in script, script         # our line is gone, the plugin's own one stays
    finally:
        root.destroy()


def main():
    top, rest = linkpicker.order(FILES, (), "")
    assert top == [] and rest == sorted(FILES, key=lambda n: n.replace("\\", "/").lower()), rest      # alphabetical, case ignored
    assert rest[0] == "alpha.safetensors" and rest[-1] == "Zeta.safetensors"
    # typing: every word, any case, sub-folder counts
    _, hit = linkpicker.order(FILES, (), "MOSS safe")
    assert hit == ["Moss\\x.safetensors", "moss_image_sft_int8_convrot.safetensors", "my_moss_copy.safetensors"], hit
    assert linkpicker.order(FILES, (), "moss nothing") == ([], [])
    assert linkpicker.order(FILES, (), "  ") == linkpicker.order(FILES, (), "")
    # copies of the expected file first, then a line, then the rest
    pinned = ["my_moss_copy.safetensors", "Zeta.safetensors"]
    got = linkpicker.rows(FILES, pinned, "")
    assert got[:2] == ["my_moss_copy.safetensors", "Zeta.safetensors"] and got[2] is None and got[3] == "alpha.safetensors", got
    assert got.count(None) == 1 and len(got) == len(FILES) + 1
    # the top group keeps the order it was given (best first), not alphabetical
    assert linkpicker.order(FILES, ["Zeta.safetensors", "alpha.safetensors", "Zeta.safetensors"], "") [0] == ["Zeta.safetensors", "alpha.safetensors"]
    assert linkpicker.order(FILES, ["Zeta.safetensors", "alpha.safetensors"], "zeta")[0] == ["Zeta.safetensors"]
    # no line when one group is empty, also while typing
    assert None not in linkpicker.rows(FILES, [], "")
    assert None not in linkpicker.rows(FILES, FILES, "")
    assert None not in linkpicker.rows(FILES, pinned, "zeta")
    assert linkpicker.rows(FILES, pinned, "zeta") == ["Zeta.safetensors"]
    assert linkpicker.rows([], pinned, "") == []
    # the settings window opens this window and no tk.Menu any more
    src = (ROOT / "pccomfy" / "ui_settings.py").read_text(encoding="utf-8")
    body = src.split("def _choose_for", 1)[1].split("def _link_models", 1)[0]
    assert "linkpicker.LinkPicker" in body and "tk.Menu" not in body
    real_tk_checks()
    print("test_linkpicker: ok")


if __name__ == "__main__":
    main()
