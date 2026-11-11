"""PLAN.md stays an index (user 11.11.): at most 120 lines, and every file it links to exists (docs/plan/ and the topic
plans under docs/). PLAN.md is private (the release export leaves it out), so the test skips without it.
Run: python tests/test_plan_size.py"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_LINES = 120

plan = ROOT / "PLAN.md"
if not plan.exists():
    print("skip: no PLAN.md (release export)")
    raise SystemExit(0)
text = plan.read_text(encoding="utf-8")
n = len(text.splitlines())
assert n <= MAX_LINES, f"PLAN.md has {n} lines (at most {MAX_LINES}): move details into docs/plan/ and link them"
links = set(re.findall(r"`((?:docs|tests|tools)/[^`\s]+\.(?:md|py))`", text))
assert any(p.startswith("docs/plan/") for p in links), "PLAN.md links no file in docs/plan/"
missing = sorted(p for p in links if not (ROOT / p).exists())
assert not missing, f"PLAN.md links files that do not exist: {missing}"
for f in sorted((ROOT / "docs" / "plan").glob("*.md")):            # every sub-file is reachable from the index
    assert f"docs/plan/{f.name}" in text, f"docs/plan/{f.name} is not linked from PLAN.md"
print(f"ok ({n} lines, {len(links)} links)")
