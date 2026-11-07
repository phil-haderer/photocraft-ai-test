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
    print("test_linkpicker: ok")


if __name__ == "__main__":
    main()
