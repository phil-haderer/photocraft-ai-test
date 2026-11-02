"""Upscale and Refine with several variants run one after the other (Bridge._run_sequence, user 2.11.): one run per variant
with its own seed, each result placed as soon as it is done, the layers of Refine grouped at the end.

    python tests/test_scale_variants.py
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402
from pccomfy import workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

REFINE = ROOT / "workflows" / "flux3-klein-refine.json"
UPSCALE = ROOT / "workflows" / "flux3-klein-upscale.json"


def seeds(graphs):
    out = []
    for g in graphs:
        for n in g.values():
            if n.get("_meta", {}).get("title", "").startswith("pc:sampler") and "seed" in n["inputs"]:
                out.append(n["inputs"]["seed"])
                break
            if n.get("_meta", {}).get("title", "").startswith("pc:sampler") and "value" in n["inputs"]:
                out.append(n["inputs"]["value"])
                break
    return out


def same_picture(comfy, n):
    """Every variant is made from the picture as it was at Generate: not one with the result of the variant before in it."""
    ups = [im for name, im in comfy.uploads.items() if name.endswith("-image.png")]
    assert len(ups) == n, list(comfy.uploads)
    assert all(list(im.getdata()) == list(ups[0].getdata()) for im in ups[1:]), "a later variant got a different picture"


def refine():
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    events = []
    req = Request(mode="refine", workflow=str(REFINE), scale=1.0, variants=3)
    req.params = workflows.GenParams(prompt="", seed=7)
    res = b.run(req, lambda f, m="", **kw: events.append((round(f, 3), m)))
    assert len(b.comfy.graphs) == 3, len(b.comfy.graphs)                     # three runs, not one batch
    s = seeds(b.comfy.graphs)
    assert s[0] == 7 and len(set(s)) == 3, s
    assert res["seed"] == 7 and len(res["layers"]) == 3 and res["group"]
    top = pc.doc.layers[-1]                                                   # the fake lists the stack bottom first
    assert top["id"] == res["group"] and len(top["members"]) == 3, [l.get("name") for l in pc.doc.layers]
    names = [m["name"] for m in top["members"]]
    assert [n[-2:] for n in names] == ["#1", "#2", "#3"], names               # arrival order: the newest is the top one
    vis = [m["visible"] for m in top["members"]]
    assert vis == [False, False, True], vis                                   # only the newest is shown
    same_picture(b.comfy, 3)
    fr = [f for f, _ in events]
    assert fr == sorted(fr) and fr[-1] == 1.0, fr
    assert any(m.startswith("Variant 2/3") for _, m in events)
    for g in b.comfy.graphs:                                                  # no batch in the graph
        for n in g.values():
            if n.get("_meta", {}).get("title", "").startswith("pc:latent"):
                assert n["inputs"].get("batch_size", 1) == 1, n


def upscale():
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="upscale", workflow=str(UPSCALE), scale=1.5, stage_on=False, variants=2)
    req.params = workflows.GenParams(prompt="", seed=7)
    res = b.run(req)
    assert len(b.comfy.graphs) == 2 and res["documents"] == 2, (len(b.comfy.graphs), res)
    docs = [d.name for d in pc.docs]
    assert docs[0] == "scene.png" and docs[1].endswith("#1.png") and docs[2].endswith("#2.png"), docs
    assert pc.active == 2                                                     # the last result opened is the active one
    same_picture(b.comfy, 2)                                                  # variant 2 did not start from variant 1's new document


def single():
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False)
    b.comfy = T.FakeComfy()
    req = Request(mode="refine", workflow=str(REFINE), scale=1.0, variants=1)
    req.params = workflows.GenParams(prompt="", seed=7)
    res = b.run(req)
    assert len(b.comfy.graphs) == 1 and len(res["layers"]) == 1 and not res.get("group")


if __name__ == "__main__":
    refine()
    upscale()
    single()
    print("ALL OK (scale variants)")
