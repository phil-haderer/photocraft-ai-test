"""Snapshot of every graph that Upscale and Refine send to ComfyUI (PLAN.md 2 "Upscale und Refine zusammenlegen", step 1).

Runs the whole bridge (Bridge.run) against the PhotoCraft simulator and a fake ComfyUI for every model x mode (upscale with
factor 1.5/2/3/4, refine) x switch (Turbo on/off, every stage switch on/off) x variants (1 and 3) x prompt (the mode's
default and each of its ready-made prompts) x sampler (workflow's own and a changed steps value) and writes the graphs, the
queue order and the result (layers, documents) as JSON. Run it before and after the merge of the two functions; the two
files must be equal (the order of the keys does not matter).

    python tests/snapshot_scale_graphs.py write <name>      writes data/snapshot-scale/<name>.json (data/ is git-ignored)
    python tests/snapshot_scale_graphs.py diff <a> <b>      compares two snapshots, exit code 1 when they differ
    python tests/snapshot_scale_graphs.py selftest          runs the generator twice and checks that both files are equal

Not a test of the runner (no test_ prefix); tests/test_snapshot_scale.py runs the selftest on a small slice.
"""
import itertools
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_reference_mode as T  # noqa: E402  (the PhotoCraft simulator and the fake ComfyUI)
from pccomfy import models, workflows  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402

OUT = ROOT / "data" / "snapshot-scale"
MODES = ("upscale", "refine")
FACTORS = (1.5, 2.0, 3.0, 4.0)
RANDOM = re.compile(r"pcc-[0-9a-f]{8}[0-9]*-")        # the random part of an uploaded file name
REQUEST_FIELDS = set(Request.__dataclass_fields__)


def prompts_of(mode: models.Mode) -> list[tuple[str, str]]:
    """The default text the field starts with, then each ready-made prompt (Default / Neutral / Restore ...)."""
    out = [("default", mode.prompt_hint)]
    out += [(f"pick:{label}", text) for label, text, _tip in mode.prompts]
    return out


def cases(slice_only: bool = False):
    """Every combination as a dict (the key of the snapshot is its sorted JSON)."""
    for model in models.MODELS:
        for key in MODES:
            mode = model.modes.get(key)
            if mode is None:
                continue
            run_mode = mode.run_as or key
            wf = ROOT / "workflows" / mode.workflow
            stages = [nid for nid, _ in workflows.stage_switches(workflows.load_template(wf))]
            factors = FACTORS if key == "upscale" else (1.0,)
            for factor, turbo, stage_bits, variants, (plabel, prompt), steps in itertools.product(
                    factors, (True, False), itertools.product((True, False), repeat=len(stages)), (1, 3),
                    prompts_of(mode), (None, 12)):
                if slice_only and (factor not in (1.5, 1.0) or steps or not turbo or plabel != "default"):
                    continue
                yield dict(model=model.key, mode=key, run_mode=run_mode, factor=factor, turbo=turbo, stages=dict(zip(stages, stage_bits)),
                           variants=variants, prompt=plabel, steps=steps), mode, prompt


def graph_key(g: dict) -> str:
    return json.dumps(g, sort_keys=True)


def run_case(spec: dict, mode: models.Mode, prompt: str) -> dict:
    pc, _, b = T.make(tempfile.mkdtemp(), with_sel=False, layers=2)
    b.comfy = T.FakeComfy()
    kw = {k: v for k, v in mode.settings.items() if k in REQUEST_FIELDS}       # the mode's start values, as the window sends them
    kw.update(mode=spec["run_mode"], workflow=str(ROOT / "workflows" / mode.workflow), scale=spec["factor"], turbo=spec["turbo"],
              variants=spec["variants"], stage_on=True)
    ids = list(spec["stages"])
    if ids:
        kw["stage_on"] = spec["stages"][ids[0]]
        kw["stages_off"] = [nid for nid in ids[1:] if not spec["stages"][nid]]
    if spec["steps"]:
        kw["sampler_override"] = {"steps": spec["steps"]}
    req = Request(**kw)
    req.params = workflows.GenParams(prompt=prompt, seed=7)
    res = b.run(req)
    return {"graphs": [json.loads(RANDOM.sub("pcc-X-", graph_key(g))) for g in b.comfy.graphs],
            "uploads": sorted(b.comfy.uploads),
            "layers": len(res.get("layers", [])), "documents": res.get("documents", 0), "seed": res.get("seed"),
            "group": bool(res.get("group")), "doc_names": [d.name for d in pc.docs]}


def snapshot(slice_only: bool = False) -> dict:
    out = {}
    for spec, mode, prompt in cases(slice_only):
        key = json.dumps(spec, sort_keys=True)
        try:
            out[key] = run_case(spec, mode, prompt)
        except Exception as e:      # an error is part of the snapshot too (a combination the bridge refuses)
            out[key] = {"error": f"{type(e).__name__}: {e}"}
    return out


def uploads_normal(snap: dict) -> dict:
    """The upload names carry a random part: only their number counts."""
    for v in snap.values():
        if "uploads" in v:
            v["uploads"] = len(v["uploads"])
        if "doc_names" in v:
            v["doc_names"] = [n.split("#")[0] if "#" in n else n for n in v["doc_names"]]
    return snap


def write(name: str, slice_only: bool = False) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{name}.json"
    path.write_text(json.dumps(uploads_normal(snapshot(slice_only)), indent=1, sort_keys=True), encoding="utf-8")
    return path


def diff(a: dict, b: dict) -> list[str]:
    out = []
    for k in sorted(set(a) | set(b)):
        if k not in a:
            out.append(f"only in the second: {k}")
        elif k not in b:
            out.append(f"only in the first: {k}")
        elif a[k] != b[k]:
            out.append(f"different: {k}")
    return out


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "write":
        p = write(argv[1])
        n = len(json.loads(p.read_text(encoding="utf-8")))
        print(f"{n} cases written to {p}")
        return 0
    if len(argv) >= 3 and argv[0] == "diff":
        a, b = (json.loads((OUT / f"{x}.json").read_text(encoding="utf-8")) for x in argv[1:3])
        d = diff(a, b)
        print("\n".join(d[:50]) or f"equal ({len(a)} cases)")
        return 1 if d else 0
    if argv[:1] == ["selftest"]:
        a, b = uploads_normal(snapshot(True)), uploads_normal(snapshot(True))
        assert a and not diff(a, b), diff(a, b)
        assert not any("error" in v for v in a.values()), [k for k, v in a.items() if "error" in v]
        print(f"selftest ok ({len(a)} cases)")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
