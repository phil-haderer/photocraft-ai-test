"""MiniMax H3 Image, Text to image (PLAN 2.0b, step 3; docs/plan-minimax-h3-image.md).

- the workflow is the official template as an API graph: 6 steps, CFG 1, euler / simple, no negative prompt, the user's
  files (UNet w4a8, encoder nvfp4), the writer chain StringReplace -> TextGenerateV2 -> JsonExtractString
- the size row: the chosen area in the canvas' aspect ratio, a megapixel = 1024 x 1024 like MiniMax' own table
- "Downsize to canvas" off (the start): the result opens as a new document in full size; on: a layer in the canvas
- the other models' Text to image is unchanged (canvas size, at most 4 MP)

    python tests/test_minimax_t2i.py
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from pccomfy import bridge, imaging, manifest, models, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402
import test_reference_mode as T  # noqa: E402

WF = ROOT / "workflows" / "minimax-h3-image-t2i.json"


def links_ok(g):
    return all(str(v[0]) in g for n in g.values() for v in n.get("inputs", {}).values() if isinstance(v, list) and v)


def run(gen_mp, new_document, wf=WF, mode="txt2img"):
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode=mode, workflow=str(wf), preset="X", run_no=1, gen_mp=gen_mp, new_document=new_document, enhance=False,
                  layer_mask="none")
    req.params = workflows.GenParams(prompt="a red fox in the snow", seed=5)
    before = len(pc.docs[0].layers)
    res = b.run(req)
    return pc, b, res, len(pc.docs[0].layers) - before


def main():
    # the workflow
    tpl = workflows.load_template(WF)
    assert links_ok(tpl) and not bridge.mask_is_used(tpl)
    ks = tpl["7"]["inputs"]
    assert (ks["steps"], ks["cfg"], ks["sampler_name"], ks["scheduler"], ks["denoise"]) == (6, 1, "euler", "simple", 1)
    assert tpl["6"]["class_type"] == "ConditioningZeroOut" and ks["negative"] == ["6", 0] and ks["latent_image"] == ["5", 1]
    assert tpl["1"]["inputs"]["unet_name"] == "minimax_h3_image_pruned_w4a8.safetensors"
    assert tpl["2"]["inputs"] == {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}
    assert tpl["20"]["inputs"]["value"].endswith("input_text: {input text}\noutput_text:\n")       # the official task prompt
    assert len(tpl["20"]["inputs"]["value"]) == 15823 and tpl["17"]["inputs"]["value"].startswith("Reason in the thinking section first.")
    t = tpl["15"]["inputs"]
    assert (t["max_length"], t["thinking"], t["sampling_mode.temperature"], t["sampling_mode.top_k"], t["sampling_mode.top_p"]) == (8192, True, 1, 20, 0.95)
    assert workflows.writer_name(tpl) == "Qwen 3.5 9B" and workflows.writer_chain(tpl) == {"19", "15", "26"}
    assert workflows.size_multiple(tpl) == 32 and bridge.prompt_phase_nodes(tpl)
    g, out = workflows.apply_template(tpl, workflows.GenParams(prompt="a fox", seed=3, width=4096, height=4096), None, None)
    assert links_ok(g) and g[out]["class_type"] == "PreviewImage" and g["19"]["inputs"]["replace"] == "a fox"
    assert (g["5"]["inputs"]["width"], g["5"]["inputs"]["height"]) == (4096, 4096)
    off = workflows.bypass_prompt_writer(g, "a fox")
    assert links_ok(off) and off["5"]["inputs"]["prompt"] == "a fox" and not {"15", "18", "19", "26"} & set(off)

    # the model, its files, its start values
    m = models.BY_KEY["minimax"]
    assert m.label == "MiniMax H3 Image" and models.SHORT["minimax"] == "MiniMax" and models.MODELS[-1] is m
    assert list(m.modes) == ["txt2img", "edit", "multi_edit"] and m.modes["txt2img"].workflow == WF.name    # Edit and Multi image edit: test_minimax_edit.py
    s = m.modes["txt2img"].settings
    assert s["gen_mp"] == 4 and s["downsize"] is False and s["enhance"] is False and s["layer_mask"] == "none"
    assert models.GEN_MP_STEPS == (4, 8, 12, 16, 20)
    assert set(m.requires) == set(manifest.tab_required("minimax"))
    assert manifest.mode_optional("minimax", "txt2img") == ("qwen3.5_9b_w4a8_gptq.safetensors",)   # the writer starts off
    for n in m.requires:
        assert manifest.FILES[n].sha256 and manifest.FILES[n].size and "MiniMax-H3-Image Community License" in manifest.FILES[n].note

    # the official 16 MP table (1 MP = 1024 x 1024), from a canvas of that shape; 4 MP = min_generation_area 2048 x 2048
    for canvas, want in (((1000, 1000), (4096, 4096)), ((4000, 3000), (4736, 3552)), ((3000, 4000), (3552, 4736)),
                         ((1920, 1080), (5472, 3072)), ((3000, 2000), (5024, 3360))):
        assert imaging.area_size(*canvas, 16, 32) == want, (canvas, imaging.area_size(*canvas, 16, 32))
    assert imaging.area_size(512, 512, 4, 32) == (2048, 2048) and imaging.area_size(8000, 8000, 4, 32) == (2048, 2048)
    assert imaging.area_size(1920, 1080, 20, 32) == (6112, 3424)

    # "Downsize to canvas" off: a new document in full size, no layer; the conditioning gets the chosen area
    pc, b, res, added = run(16, True)
    cond = b.comfy.graphs[0]["5"]["inputs"]
    assert (cond["width"], cond["height"]) == imaging.area_size(T.W, T.H, 16, 32), cond
    assert res["documents"] == 1 and res["layers"] == [], res
    new = pc.docs[-1]
    assert len(pc.docs) == 2 and new.name.endswith(" generated 64x64.png") and "upscaled" not in new.name, [d.name for d in pc.docs]
    assert new.raw.size == (64, 64)        # opened in the size the model drew it, not scaled to the canvas
    assert added == 0, "a layer was added to the canvas"

    # on: a layer in the canvas (scaled down to the canvas by the usual placing), drawn at the chosen area all the same
    pc, b, res, added = run(8, False)
    cond = b.comfy.graphs[0]["5"]["inputs"]
    assert (cond["width"], cond["height"]) == imaging.area_size(T.W, T.H, 8, 32), cond
    assert added >= 1 and len(pc.docs) == 1 and res["layers"] and not res.get("documents") and res["region"] == {"x": 0, "y": 0, "w": T.W, "h": T.H}, res

    # the other models are unchanged: canvas size, at most 4 MP, never larger (gen_mp 0)
    pc, b, res, added = run(0, False, wf=ROOT / "workflows" / "qwen-image-21-t2i.json")
    lat = next(n for n in b.comfy.graphs[0].values() if n["class_type"] == "EmptyLatentImage")["inputs"]
    assert (lat["width"], lat["height"]) == imaging.canvas_size(T.W, T.H, 4.0, 32) and res["layers"], lat
    assert Request().gen_mp == 0 and Request().new_document is False
    print("ALL OK (MiniMax text to image)")


if __name__ == "__main__":
    main()
