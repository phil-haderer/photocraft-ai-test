"""The Sketch workflows (docs/sketch-plan.md, "Bauplan nach Runde 2", step 1 of the build, 9.11.): each is the model's
Edit workflow plus BFL's prompt upsampler, as the test rounds 2 to 7 ran it (tests/live_sketch.py, upsample_any), without
reference slots. The Edit workflows themselves stay as they are (the user calls Flux 3 and Qwen Edit "perfect").
Since 10.11. (writer round on PC A, option B) Flux 2 writes with qwen3vl 4B and an instruction prompt instead."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from pccomfy import models, workflows  # noqa: E402
try:
    import live_sketch as ls  # noqa: E402
except ImportError:          # tests/live_sketch.py stays in the private repo (it names the user's picture folders)
    if __name__ == "__main__":
        print("skipped: tests/live_sketch.py is only in the private working repo")
        sys.exit(0)
    raise

WF = ROOT / "workflows"
PAIRS = {"flux3-klein-sketch.json": "flux3-klein-edit.json", "flux2-klein-sketch.json": "flux2-klein-edit.json",
         "qwen-image-21-sketch.json": "qwen-image-21-edit.json"}
OWN = {"401", "402", "403", "404", "405"}       # the writer's nodes
VL4 = "qwen3vl_4b_int8_convrot.safetensors"


def _writer(name):
    """(file, loader type, system prompt) of the writer in this Sketch workflow."""
    if name.startswith("flux2"):
        return VL4, "stable_diffusion", models.SKETCH_WRITER_SYSTEM
    return ls.UPSAMPLER_FILE, "flux3", ls.EDIT_UPSAMPLER_SYSTEM


def _prompt_nodes(g):
    return [k for k, n in g.items() if "pc:prompt" in n.get("_meta", {}).get("title", "").lower()]


def test_the_upsampler_writes_the_prompt_and_sees_the_picture():
    for name in PAIRS:
        g = workflows.load_template(WF / name)
        assert _prompt_nodes(g) == ["403"], name
        gen = g["403"]
        assert gen["class_type"] == "TextGenerate"
        img = next(k for k, n in g.items() if "pc:image" in n.get("_meta", {}).get("title", "").lower())
        assert gen["inputs"]["image"] == [img, 0], name
        f, typ, system = _writer(name)
        loader = g[gen["inputs"]["clip"][0]]["inputs"]
        assert loader["clip_name"] == f and loader["type"] == typ, (name, loader)
        assert g[gen["inputs"]["system_prompt"][0]]["inputs"]["value"] == system, name
        assert "vgl" in g["404"]["_meta"]["title"]
        assert not workflows.has_ref_slot(g), name


def test_everything_else_is_the_edit_workflow():
    """Apart from the upsampler and the text input of the encoder, the graph is the Edit workflow with its reference slots
    dropped: same model files, sampler, steps and size handling."""
    for name, edit in PAIRS.items():
        g = workflows.load_template(WF / name)
        e = workflows.load_template(WF / edit)
        workflows.drop_ref_slot(e, 1)
        assert set(g) - OWN == set(e), name
        for k in e:
            a, b = json.loads(json.dumps(g[k])), json.loads(json.dumps(e[k]))
            if k in _prompt_nodes(e):       # the encoder: its text now comes from the upsampler
                for n in (a, b):
                    n["_meta"] = {}
                    n["inputs"].pop("text", None)
                    n["inputs"].pop("prompt", None)
            assert a == b, (name, k)


def test_llm_off_sends_the_typed_text():
    """The LLM switch off (bypass_prompt_writer): no text model runs and the encoder gets the typed text; Qwen keeps
    "<image1>" in front, as its Edit workflow does."""
    text = "Replace the coloured scribbles with a rabbit."
    for name in PAIRS:
        g = workflows.bypass_prompt_writer(workflows.load_template(WF / name), text)
        assert not any(n["class_type"] == "TextGenerate" for n in g.values()), name
        # the upsampler's loader may stay (as in Text to image), but nothing uses it: ComfyUI runs only what an output needs
        loaders = {k for k, n in g.items() if n["inputs"].get("clip_name") == _writer(name)[0] and k in OWN}
        assert not any(isinstance(v, list) and v and v[0] in loaders for n in g.values() for v in n["inputs"].values()), name
        graph, _out = workflows.apply_template(g, workflows.GenParams(prompt=text), "pic.png", None)
        if name.startswith("qwen"):
            cat = graph["405"]["inputs"]
            assert cat["string_a"] == "<image1>" and cat["string_b"] == text
            assert graph["8"]["inputs"]["prompt"] == ["405", 0]
        else:
            enc = next(n for n in graph.values() if n["class_type"] == "CLIPTextEncode")
            assert enc["inputs"]["text"] == text, name


def test_llm_on_gives_the_request_to_the_upsampler():
    text = "Replace the coloured scribbles with a rabbit."
    for name in PAIRS:
        graph, out = workflows.apply_template(workflows.load_template(WF / name), workflows.GenParams(prompt=text),
                                              "pic.png", None)
        assert graph["403"]["inputs"]["prompt"] == text, name      # no "<image1>" for the upsampler itself
        assert out is not None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
