"""tests/live_fill_flux.py (the Flux Fill round, user 9.11.): 80 runs as planned, Flux with the settings of its Remove,
the plugin's two Fill sentences, selections inside the photo, and the summary counts "good without any fault" apart.
Retired from the standard run (10.11.: the round is finished; was tests/test_live_fill_flux.py);
tests/run_all.py only collects test_*.py. Run by hand: python tests/selfcheck_live_fill_flux.py"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from PIL import Image  # noqa: E402

import live_fill_flux as lf  # noqa: E402
from pccomfy import bridge, imaging, models  # noqa: E402


def test_the_planned_runs():
    jobs = lf.jobs()
    assert len(jobs) == 80 and len(set(jobs)) == 80
    count = {}
    for _, m, w, _ in jobs:
        count[(m, w)] = count.get((m, w), 0) + 1
    assert count == {("flux3", "fit"): 16, ("flux3", "large"): 16, ("flux2", "fit"): 16, ("flux2", "large"): 16, ("qwen", "large"): 16}
    assert [m for _, m, _, _ in jobs] == sorted([m for _, m, _, _ in jobs], key=["flux3", "flux2", "qwen"].index)   # each model loaded once


def test_round_4_flux2_c_against_c_plus():
    jobs = lf.jobs(4)
    assert len(jobs) == 16 and len(set(jobs)) == 16
    assert {(m, w) for _, m, w, _ in jobs} == {("flux2", "C"), ("flux2", "C+")} and {s for *_, s in jobs} == {11}
    cases = (1, 3, 6, 7, 9, 10, 11, 12)
    assert sorted({c + 1 for c, *_ in jobs}) == list(cases)
    # C is round 2's Flux 2 C on the same cases and seed
    assert {j for j in jobs if j[2] == "C"} == {j for j in lf.jobs(2, ["flux2"], ["C"], [11]) if j[0] + 1 in cases}


def test_settings_and_sentences():
    for m in ("flux3", "flux2"):
        assert lf.settings(m) == models.BY_KEY[m].modes["remove"].settings and lf.settings(m)["context"] == 0.4
        assert Path(lf.workflow(m)).name == models.BY_KEY[m].modes["edit"].workflow
    assert lf.settings("qwen") == models.BY_KEY["qwen"].modes["inpaint"].settings
    assert lf.WORDINGS == {"fit": bridge.FILL_PROMPT, "large": bridge.FILL_PROMPT_LARGE}


def test_selections_inside_the_photo_and_their_shape_word():
    size = (1732, 1155)
    for k, (_, subject, shape, *box) in enumerate(lf.CASES):
        m = lf.selection(size, shape, box)
        b = imaging.mask_bbox(m)
        assert b and b.x >= 0 and b.y >= 0 and b.x + b.w <= size[0] and b.y + b.h <= size[1], subject
        region = imaging.grow_box(b, size, 0.4)
        text = lf.prompt_of(k, "fit", m, region)
        assert text.startswith(subject + ".") and ("rectangle" if shape == "rect" else "outline") in text, text


def test_put_back_keeps_everything_outside_the_crop():
    photo = Image.new("RGB", (600, 400), (40, 120, 60))
    mask = lf.selection(photo.size, "rect", (0.4, 0.4, 0.6, 0.6))
    region = imaging.grow_box(imaging.mask_bbox(mask), photo.size, 0.4)
    out = lf.put_back(photo, Image.new("RGB", (64, 64), (250, 0, 0)), mask, region, "flux3")
    assert out.getpixel((5, 5)) == (40, 120, 60) and out.getpixel((300, 200))[0] > 200


def test_summary_counts_clean_good_apart():
    items = {"001": {"model": "flux3", "wording": "fit", "case": 1, "subject": "a dog", "seed": 11, "secs": 20},
             "002": {"model": "flux3", "wording": "fit", "case": 1, "subject": "a dog", "seed": 12, "secs": 22}}
    data = {"001": {"wahl": lf.GOOD, "fehler": []}, "002": {"wahl": lf.GOOD, "fehler": ["edge"], "notiz": "Rand"}}
    text = lf.summarize({"items": items}, data)
    assert "| flux3 · fit | 2/2 | 1/2 | 1 |" in text and "Bewertet: 2 von 2" in text and "Rand" in text


def test_round2_runs_and_approaches():
    j = lf.jobs(2)
    assert len(lf.cases(2)) == 12 and len(j) == 216 and len(set(j)) == 216
    assert {(m, w) for _, m, w, _ in j} == {(m, a) for m in ("flux3", "flux2") for a in lf.APPROACHES} | {("qwen", "A")}
    assert lf.jobs(1) == lf.jobs()                       # round 1 stays as it ran


def test_round2_prompts_marks_and_workflows():
    size = (1732, 1155)
    _, subject, shape, *box = lf.CASES2[8]                # the pickup truck, a rectangle
    m = lf.selection(size, shape, box)
    region = imaging.grow_box(imaging.mask_bbox(m), size, 0.4)
    c = lf.prompt_of(8, "C", m, region, 2)
    large = bridge.FILL_PROMPT_LARGE.format(text=subject, shape="rectangle")
    assert c.startswith(subject + ".") and "natural shape" in c and " % " not in c and "the red rectangle only marks" in c
    assert c.replace(" Give it its natural shape: the red rectangle only marks the area, it is not the shape of the object.", "") == large
    assert lf.prompt_of(8, "A", m, region, 2) == lf.prompt_of(8, "D", m, region, 2) == bridge.FILL_PROMPT_LARGE.format(text=subject, shape="rectangle")
    assert "Replace the red area" in lf.prompt_of(8, "E", m, region, 2)
    for model in ("flux3", "flux2"):
        assert Path(lf.workflow(model, "D")).name == lf.SKETCH_WF[model] and lf.request(model, "D").enhance
        assert Path(lf.workflow(model, "A")).name == models.BY_KEY[model].modes["edit"].workflow
    crop = Image.new("RGB", (100, 80), (0, 200, 0))
    sel = Image.new("L", (100, 80), 0)
    sel.paste(255, (30, 20, 70, 60))
    area = lf.mark_area(crop, sel)
    r, g, _ = area.getpixel((50, 40))
    assert r > 120 and g < 120 and area.getpixel((5, 5)) == (0, 200, 0)    # see-through red inside, untouched outside


def test_round2_cut_for_pc_b():
    """User 10.11.: Flux 2 only, one seed, the 8 cases without the four that were clean in round 1 = 32 pictures."""
    j = lf.jobs(2, ["flux2"], [], [11], [1, 3, 6, 7, 9, 10, 11, 12])
    assert len(j) == 32 and {m for _, m, _, _ in j} == {"flux2"} and {s for *_, s in j} == {11}
    assert {w for _, _, w, _ in j} == set(lf.APPROACHES) and sorted({c + 1 for c, *_ in j}) == [1, 3, 6, 7, 9, 10, 11, 12]
    assert lf.jobs(2, [], [], [], []) == lf.jobs(2) and lf.jobs(2, ["nope"]) == []
    assert lf._list(" flux3, flux2 ,") == ["flux3", "flux2"] and lf._list("") == []


def test_round3_flux3_with_the_add_verb():
    """User 10.11.: Flux 3 with A, A+, E, E+ on the five hard cases; "+" = "Add a red pickup truck. ..."."""
    j = lf.jobs(3, [], [], [11], [4, 5, 7, 9, 12])
    assert len(j) == 20 and {m for _, m, _, _ in j} == {"flux3"} and {w for _, _, w, _ in j} == {"A", "A+", "E", "E+"}
    size = (1732, 1155)
    _, subject, shape, *box = lf.CASES2[8]                # the pickup truck
    m = lf.selection(size, shape, box)
    region = imaging.grow_box(imaging.mask_bbox(m), size, 0.4)
    a, a_add = lf.prompt_of(8, "A", m, region, 3), lf.prompt_of(8, "A+", m, region, 3)
    assert a == bridge.FILL_PROMPT_LARGE.format(text=subject, shape="rectangle")
    assert a_add == "Add " + a and a_add.startswith("Add a red pickup truck. Make it as large")
    assert lf.prompt_of(8, "E+", m, region, 3) == "Add " + lf.prompt_of(8, "E", m, region, 3)
    assert lf.base("E+") == "E" and lf.base("A") == "A" and lf.base("") == ""
    assert Path(lf.workflow("flux3", "D+")).name == lf.SKETCH_WF["flux3"] and not lf.request("flux3", "E+").enhance is None
    assert lf.jobs(2) == [x for x in lf.jobs(2)] and len(lf.jobs(2)) == 216                # round 2 stays as it ran


def test_merge_renumbers_and_mixes(tmp=None):
    import json
    import tempfile
    base = Path(tmp or tempfile.mkdtemp())
    for name, n, missing in (("a", 3, None), ("b", 2, "002")):      # b: an aborted run whose last picture is missing
        f = base / name
        for d in ("bilder", "eingabe", "gesendet"):
            (f / d).mkdir(parents=True)
        items = {}
        for k in range(1, n + 1):
            fid = f"{k:03d}"
            items[fid] = {"case": k, "model": name, "wording": "A", "seed": 11}
            if fid != missing:
                Image.new("RGB", (4, 4), (k, 0, 0)).save(f / "bilder" / f"{fid}.png")
            Image.new("RGB", (4, 4)).save(f / "eingabe" / f"{k:02d}.png")
        (f / "key.json").write_text(json.dumps({"items": items}), encoding="utf-8")
    key = lf.merge([base / "a", base / "b"], base / "m")
    assert sorted(key["items"]) == ["001", "002", "003", "004"] and sorted(key["order"]) == sorted(key["items"])
    assert key["items"]["004"]["source"] == "b/001" and key["items"]["004"]["model"] == "b"
    assert len(list((base / "m" / "bilder").iterdir())) == 4 and len(list((base / "m" / "eingabe").iterdir())) == 3
    assert json.loads((base / "m" / "key.json").read_text(encoding="utf-8"))["merged"] == ["a", "b"]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
