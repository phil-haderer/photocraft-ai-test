"""MiniMax H3 Image, Edit and Multi image edit (PLAN 2.0b, step 4; docs/plan-minimax-h3-image.md).

- the workflow is the official edit template as an API graph (task prompt word for word, ends "User input: {input text}"),
  the picture is `images.image_1` of the conditioning and `images.image1` of the writer, 6 reference slots follow
- the model: Edit and Multi image edit with 6 references, "<Picture {n}>", size row 4 MP, "Downsize to canvas" starts ON
- the run: the picture goes in at the chosen area (canvas' aspect ratio), tick on = a layer in the canvas, off = a new document
- the prompt gets "<Picture 1>" in front, with the writer on (in the StringReplace) and off (straight into the conditioning)
- unused reference slots drop out of the graph, also behind the writer
- the files: Edit and Multi image edit need no extra file; the writer (Qwen 3.5 9B) stays optional

    python tests/test_minimax_edit.py
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pccomfy import bridge, imaging, manifest, models, refslots, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402
import test_reference_mode as T  # noqa: E402

WF = ROOT / "workflows" / "minimax-h3-image-edit.json"
WRITER = "qwen3.5_9b_w4a8_gptq.safetensors"


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def run(gen_mp, new_document, enhance=False, refs=0, mode="edit", prompt="make the fox red"):
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode=mode, workflow=str(WF), preset="X", run_no=1, gen_mp=gen_mp, new_document=new_document, enhance=enhance,
                  layer_mask="none",
                  refs=[Image.new("RGB", (40 + 10 * i, 30), (i * 30, 90, 200)) for i in range(refs)])
    req.params = workflows.GenParams(prompt=prompt, seed=5)
    before = len(pc.docs[0].layers)
    res = b.run(req)
    return pc, b, res, len(pc.docs[0].layers) - before


def main():
    # the workflow
    tpl = workflows.load_template(WF)
    assert links_ok(tpl) and not bridge.mask_is_used(tpl)
    ks = tpl["7"]["inputs"]
    assert (ks["steps"], ks["cfg"], ks["sampler_name"], ks["scheduler"], ks["denoise"]) == (6, 1, "euler", "simple", 1)
    assert tpl["6"]["class_type"] == "ConditioningZeroOut" and ks["latent_image"] == ["5", 1]
    task = tpl["20"]["inputs"]["value"]
    assert task.startswith("You are an expert at enhancing a short image-editing instruction")
    assert task.endswith("User input: {input text}\noutput_text:\n") and len(task) == 38449      # the official edit task prompt
    assert tpl["17"]["inputs"]["value"].startswith("Reason in the thinking section first.")
    assert tpl["5"]["class_type"] == "MiniMaxH3ImageConditioning" and tpl["5"]["inputs"]["images.image_1"] == ["30", 0]
    assert tpl["15"]["class_type"] == "TextGenerateV2" and tpl["15"]["inputs"]["images.image1"] == ["30", 0]
    for n in range(1, 7):      # picture + 6 references on both the conditioning and the writer
        assert tpl["5"]["inputs"][f"images.image_{n + 1}"] == [str(30 + n), 0]
        assert tpl["15"]["inputs"][f"images.image{n + 1}"] == [str(30 + n), 0]
        assert tpl[str(30 + n)]["class_type"] == "LoadImage" and tpl[str(30 + n)]["_meta"]["pc_slot"] == n
    assert workflows.ref_slot_count(tpl) == 6 and workflows.has_ref_slot(tpl)
    assert workflows.writer_chain(tpl) == {"19", "15", "26"} and workflows.writer_name(tpl) == "Qwen 3.5 9B"
    assert workflows.size_multiple(tpl) == 32 and workflows.image_tag(tpl["19"]) == "<Picture 1>"

    # one picture: the reference slots drop out of the conditioning and the writer
    g, out = workflows.apply_template(tpl, workflows.GenParams(prompt="make it red", seed=3, width=2048, height=2048), "pic.png", None)
    assert links_ok(g) and g[out]["class_type"] == "PreviewImage" and g["30"]["inputs"]["image"] == "pic.png"
    assert g["19"]["inputs"]["replace"] == "<Picture 1> make it red"
    assert not any(k.startswith(("images.image_", "images.image")) and k not in ("images.image_1", "images.image1")
                   for nid in ("5", "15") for k in g[nid]["inputs"]), g["5"]["inputs"]
    assert not any(str(30 + n) in g for n in range(1, 7))
    # three references: slots 1..3 stay, 4..6 go; slot 1 is <Picture 2>
    g, _ = workflows.apply_template(tpl, workflows.GenParams(prompt="x", seed=3, width=2048, height=2048), "pic.png", None,
                                    ["a.png", "b.png", "c.png"], ref_first=False)
    assert links_ok(g) and [g[str(30 + n)]["inputs"]["image"] for n in (1, 2, 3)] == ["a.png", "b.png", "c.png"]
    assert all(str(30 + n) not in g for n in (4, 5, 6))
    assert sorted(k for k in g["5"]["inputs"] if k.startswith("images.")) == [f"images.image_{n}" for n in (1, 2, 3, 4)]
    assert sorted(k for k in g["15"]["inputs"] if k.startswith("images.")) == [f"images.image{n}" for n in (1, 2, 3, 4)]
    # the writer off: the typed text goes straight into the conditioning, with the picture's tag in front
    off = workflows.bypass_prompt_writer(g, workflows.tagged_for_writer_off(tpl, "make it red"))
    assert links_ok(off) and off["5"]["inputs"]["prompt"] == "<Picture 1> make it red" and not {"15", "19", "26"} & set(off)
    assert workflows.tagged_for_writer_off(tpl, "has <Picture 1> already") == "has <Picture 1> already"
    assert workflows.tagged_for_writer_off(tpl, "") == ""
    # other models: their writer has no tag, the prompt stays as typed
    assert workflows.tagged_for_writer_off(workflows.load_template(ROOT / "workflows" / "minimax-h3-image-t2i.json"), "a fox") == "a fox"

    # the model
    m = models.BY_KEY["minimax"]
    assert list(m.modes) == ["txt2img", "edit", "multi_edit"]
    assert m.max_refs == 6 and m.tag_style == "<Picture {n}>" and m.ref_side == 1024
    assert m.tag_style.format(n=1, i=0) == "<Picture 1>" and m.tag_style.format(n=2, i=1) == "<Picture 2>"
    for k in ("edit", "multi_edit"):
        spec = m.modes[k]
        assert spec.workflow == WF.name and spec.settings["gen_mp"] == 4 and spec.settings["downsize"] is True, k
        assert spec.settings["enhance"] is False and spec.settings["layer_mask"] == "none", k
    assert m.modes["edit"].prompt_tip == models.EDIT_TIP and m.modes["multi_edit"].prompt_tip == models.MULTI_TIP
    assert m.modes["multi_edit"].run_as == "edit" and m.modes["txt2img"].settings["downsize"] is False
    assert set(m.workflows()) == {"minimax-h3-image-t2i.json", WF.name}

    # the files: nothing extra for either mode, the writer is optional (it starts off)
    for k in ("edit", "multi_edit"):
        assert manifest.mode_extra("minimax", k) == () and WRITER in manifest.mode_optional("minimax", k), k
        assert set(manifest.mode_required("minimax", k)) == set(m.requires)
    assert "birefnet.safetensors" in manifest.mode_optional("minimax", "multi_edit")

    # run: "Downsize to canvas" on (the start): a layer in the canvas, drawn at the chosen area in the canvas' shape
    pc, b, res, added = run(8, False)
    gr = b.comfy.graphs[0]
    cond = gr["5"]["inputs"]
    assert (cond["width"], cond["height"]) == imaging.area_size(T.W, T.H, 8, 32), cond
    assert cond["prompt"] == "<Picture 1> make the fox red" and cond["images.image_1"] == ["30", 0], cond
    assert added >= 1 and len(pc.docs) == 1 and res["layers"] and not res.get("documents"), res
    up = b.comfy.uploads
    pic = next(v for k, v in up.items() if k.endswith("-image.png"))
    assert pic.size == (cond["width"], cond["height"]), pic.size          # the picture went in at the chosen size

    # off: a new document in full size, named "edited", the canvas untouched
    pc, b, res, added = run(16, True)
    cond = b.comfy.graphs[0]["5"]["inputs"]
    assert (cond["width"], cond["height"]) == imaging.area_size(T.W, T.H, 16, 32)
    assert res["documents"] == 1 and res["layers"] == [] and added == 0, res
    assert len(pc.docs) == 2 and pc.docs[-1].name.endswith(" edited 64x64.png"), [d.name for d in pc.docs]

    # Multi image edit: three references (run as Edit), the references named <Picture 2> ...; the writer on
    pc, b, res, added = run(4, False, enhance=True, refs=3, mode="edit", prompt="Put the bag from <Picture 2> on the table.")
    gr = b.comfy.graphs[0]
    assert links_ok(gr) and gr["19"]["inputs"]["replace"] == "<Picture 1> Put the bag from <Picture 2> on the table.", gr["19"]["inputs"]
    assert gr["5"]["inputs"]["prompt"] == ["26", 0] and gr["15"]["inputs"]["images.image4"] == ["33", 0]
    assert "images.image5" not in gr["15"]["inputs"] and "34" not in gr
    assert sum(1 for k in b.comfy.uploads if "-ref" in k) == 3
    # six references fit, seven do not
    pc, b, res, added = run(4, False, refs=6)
    assert "36" in b.comfy.graphs[0] and b.comfy.graphs[0]["5"]["inputs"]["images.image_7"] == ["36", 0]
    try:
        run(4, False, refs=7)
    except bridge.BridgeError as e:
        assert "room for 6" in str(e), e
    else:
        raise AssertionError("7 references must not fit")

    # the text to image run and the other models are unchanged
    assert Request().gen_mp == 0
    print("ALL OK (MiniMax edit)")


if __name__ == "__main__":
    main()
