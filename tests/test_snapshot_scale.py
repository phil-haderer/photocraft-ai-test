"""The snapshot script of Upscale and Refine (tests/snapshot_scale_graphs.py) is deterministic and covers every model x mode.

    python tests/test_snapshot_scale.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snapshot_scale_graphs as S  # noqa: E402


def main():
    a, b = S.uploads_normal(S.snapshot(True)), S.uploads_normal(S.snapshot(True))
    assert a and not S.diff(a, b), S.diff(a, b)                       # the same twice (no random part left)
    assert not any("error" in v for v in a.values()), [k for k, v in a.items() if "error" in v]
    seen = {(S.json.loads(k)["model"], S.json.loads(k)["mode"]) for k in a}
    assert seen == {("qwen", "upscale"), ("qwen", "refine"), ("flux2", "upscale"), ("flux2", "refine"),
                    ("flux3", "upscale"), ("flux3", "refine"), ("fibo", "refine"), ("fibo", "upscale")}, seen
    k = next(k for k in a if '"mode": "refine"' in k and '"model": "flux3"' in k)
    assert len(a[k]["graphs"]) == 1 and a[k]["layers"] == 1, a[k]["layers"]
    k = next(k for k in a if '"mode": "upscale"' in k and '"model": "qwen"' in k)
    assert a[k]["documents"] == 1 and a[k]["graphs"], a[k]["documents"]
    assert S.diff({"x": 1}, {"x": 2}) and not S.diff({"x": 1}, {"x": 1})   # the comparison sees a difference
    print("ALL OK (snapshot scale)")


if __name__ == "__main__":
    main()
