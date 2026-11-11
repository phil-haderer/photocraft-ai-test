"""tests/live_style_round.py: --half and --other-half cut parts A and B into two halves that together are the full round
(round 7b ran --half; the other half runs later on another PC). Not part of the runner; run by hand:
python tests/selfcheck_live_style_round.py   (no ComfyUI, no GPU, no photos needed: the sources are stubbed)"""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import live_style_round as ls  # noqa: E402


def _jobs(**kw):
    ls.photo_sources = lambda folder: [{"src": "x", "file": f"p{i}.png", "desc": f"photo {i}"} for i in range(3)]
    ls.sketch_sources = lambda files=None: [{"src": "x", "file": f"s{i}.jpg", "desc": f"sketch {i}"} for i in range(len(files or ()))]
    a = SimpleNamespace(photos="", part=["A", "B"], models=["flux2", "fibo"], sketches=["hyenas", "landscape"],
                        half=False, other_half=False)
    a.__dict__.update(kw)
    return [(p, m, st, s["file"]) for p, m, st, s in ls.jobs(a)]


def test_halves_make_the_full_round():
    full, h, o = _jobs(), _jobs(half=True), _jobs(other_half=True)
    n_styles = len(ls.LOOKS)
    assert len(full) == len(set(full)) == n_styles * 2 * (3 + 2), len(full)      # 11 x 2 models x (3 photos + 2 sketches)
    assert not set(h) & set(o), "the halves overlap"
    assert sorted(h + o) == sorted(full), "half + other-half is not the full round"
    assert abs(len(h) - len(o)) <= 2
    assert h == _jobs(half=True) and o == _jobs(other_half=True), "not deterministic"
    for m in ("flux2", "fibo"):                       # every style at least once per model and part in each half
        for part in ("A", "B"):
            for half in (h, o):
                assert {st for p, mk, st, _ in half if mk == m and p == part} == set(ls.LOOKS)
    return len(full), len(h), len(o)


if __name__ == "__main__":
    print("ok test_halves_make_the_full_round (full, half, other half) =", test_halves_make_the_full_round())
