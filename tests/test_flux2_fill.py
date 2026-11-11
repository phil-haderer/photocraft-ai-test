"""Fill Selection for Flux 2 (user 10.11., approach C of the Flux Fill round 2, docs/tests/fill-flux-ergebnis.md):
the plugin runs it exactly as the test round did: the edit graph with the red outline, the start values of Flux 2's
Remove, and Qwen's sentence plus "its natural shape". No new files; Flux 3 stays without Fill.

    python tests/test_flux2_fill.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from PIL import Image  # noqa: E402

import live_fill_flux as lf  # noqa: E402
from pccomfy import bridge, manifest, models  # noqa: E402

WF = str(ROOT / "workflows" / "flux2-klein-edit.json")


def test_mode_as_in_the_test_round():
    flux2 = models.BY_KEY["flux2"]
    fill, remove = flux2.modes["inpaint"], flux2.modes["remove"]
    assert fill.workflow == remove.workflow == "flux2-klein-edit.json"
    assert fill.settings == remove.settings == lf.settings("flux2")         # context 40 %, soft mask, Edge feather 10 %
    assert fill.prompt_tip == models.FILL_TIP and flux2.seam == "off"
    assert "Fill Selection" in flux2.tip
    assert "inpaint" not in models.BY_KEY["flux3"].modes                     # Flux 3 failed on large objects (0 of 4 pickups)


def test_no_new_files():
    assert "inpaint" not in manifest.TABS["flux2"].modes                     # nothing on top of the tab's three files


def test_the_wording_is_approach_c():
    sel = Image.new("L", (200, 100), 0)
    sel.paste(255, (50, 20, 150, 80))
    text = bridge.fill_prompt("a red pickup truck.", sel, WF)
    assert text == bridge.FILL_PROMPT_NATURAL.format(text="a red pickup truck", shape="rectangle")
    assert text == lf.SHAPE_PROMPT.format(text="a red pickup truck", shape="rectangle")      # the sentence that was rated
    assert "natural shape" in text and "as large as the red rectangle" in text
    # the others keep theirs
    assert bridge.fill_prompt("x", sel, str(ROOT / "workflows" / "qwen-image-21-edit.json")) == bridge.FILL_PROMPT_LARGE.format(text="x", shape="rectangle")
    assert bridge.fill_prompt("x", sel, str(ROOT / "workflows" / "fibo2-edit.json")) == bridge.FILL_PROMPT.format(text="x", shape="rectangle")


def test_the_edit_graph_is_an_instruction_editor():
    assert bridge.is_editor([WF])                                             # so Fill draws the red outline and wraps the text


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
