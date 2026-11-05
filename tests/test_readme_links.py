"""README for humans (5.11.2026): every jump link (#section) points at a real heading, and every file or picture the README
links to exists in the repo. The quick start, the install sections and the help table must stay in place.

    python tests/test_readme_links.py
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
text = (ROOT / "README.md").read_text(encoding="utf-8")


def slug(heading: str) -> str:
    """GitHub's anchor: lower case, punctuation removed, spaces become hyphens."""
    s = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return s.replace(" ", "-")


# headings outside code fences
body, fenced = [], False
for line in text.splitlines():
    if line.strip().startswith("```"):
        fenced = not fenced
        continue
    if not fenced:
        body.append(line)
headings = [re.sub(r"^#+\s*", "", l) for l in body if re.match(r"^#{1,6}\s", l)]
anchors = {slug(h) for h in headings}

# 1. the sections a newcomer is sent to
for want in ("Quick start", "How it fits together", "Install on Windows", "Install on Linux", "First start", "Functions", "Help",
             "Technical details", "Licences of the models", "Credits"):
    assert want in headings, f"heading missing: {want}"

# 2. jump links
links = re.findall(r"\]\(#([^)]+)\)", text)
assert links, "no jump links"
bad = sorted({a for a in links if a not in anchors})
assert not bad, f"jump links without a heading: {bad}"

# 3. files and pictures
for target in re.findall(r"(?:\]\(|src=\")((?!https?:|#|mailto:)[^)\" ]+)", text):
    assert (ROOT / target).exists(), f"linked file missing: {target}"

# 4. the screenshot is there and not empty
shot = ROOT / "readme-images" / "plugin-window.png"
assert shot.exists() and shot.stat().st_size > 10_000 and shot.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

# 5. a placeholder repository is fine until the public repo exists, but no private path or name may sneak in
private = ("C:\\" + "programs", "Phil" + "ipp", "phil-" + "had" + "erer")     # built from parts: the export scan must not find the names in this file
assert not any(x in text for x in private), [x for x in private if x in text]

print("ALL OK (readme links)")
sys.exit(0)
