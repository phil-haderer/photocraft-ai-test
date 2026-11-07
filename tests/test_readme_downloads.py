"""README download menus (7.11.2026): the block between the model-downloads markers is exactly what
tools/update_readme_downloads.py makes from manifest.py and models.json, every model has a menu, every download link
of the manifest appears, and the custom node packs are named with their links.

    python tests/test_readme_downloads.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
import update_readme_downloads as u  # noqa: E402
from pccomfy import manifest  # noqa: E402

text = (ROOT / "README.md").read_text(encoding="utf-8")
assert u.START in text and u.END in text, "markers missing"
assert u.update(text) == text, "README download menus are out of date: run python tools/update_readme_downloads.py"

block = text[text.index(u.START):text.index(u.END)]
for title in u.TITLES.values():
    assert f"<b>{title}</b>" in block, f"no menu for {title}"
assert block.count("<details>") == block.count("</details>") == len(u.TITLES) + 1

# every file that has a link and belongs to a tab appears with its link
used = {n for t in manifest.TABS.values() for n in (*t.required, *t.optional,
                                                    *[x for s in t.modes.values() for x in (*s.requires, *s.optional)])}
for n in sorted(used):
    f = manifest.FILES.get(n)
    if f is not None and f.url:
        assert f.url in block, f"link missing in the README: {n}"

# the custom node packs, named with a link
for name, url in (("ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes"), ("ComfyUI-GGUF", "https://github.com/city96/ComfyUI-GGUF")):
    assert f"[{name}]({url})" in text, f"custom node {name} without a link"
assert any(url == "https://github.com/kijai/ComfyUI-KJNodes" for _p, _n, url in manifest.NODE_PACKS)

print("ALL OK (readme downloads)")
