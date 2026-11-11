"""Writes the styles of Edit canvas ("edit") and Sketch to image ("sketch") into pccomfy/assets/styles.json.

    python tools/build_style_looks.py

The source is tools/styles-looks.json: one look per style, put into the frame sentence of each tab (models.EDIT_FRAME,
models.SKETCH_FRAME); a style with "fixed" keeps a tested sentence of models.py word for word. "tabs" says where a style is
offered (3D styles only in Sketch to image, user 10.11.2026). The Text to image styles in the file stay as they are
(tools/build_styles.py writes those and keeps these). tests/test_styles.py fails when styles.json is behind this file.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pccomfy import models  # noqa: E402

SOURCE = ROOT / "tools" / "styles-looks.json"
OUT = ROOT / "pccomfy" / "assets" / "styles.json"
FRAMES = {"edit": models.EDIT_FRAME, "sketch": models.SKETCH_FRAME}


def build(source: Path = SOURCE) -> dict:
    """{"edit": {"groups": [...]}, "sketch": {"groups": [...]}} in the format of styles.json; empty groups are left out."""
    out = {}
    for tab, frame in FRAMES.items():
        groups = []
        for g in json.loads(source.read_text(encoding="utf-8"))["groups"]:
            st = []
            for s in g["styles"]:
                if tab not in s["tabs"]:
                    continue
                fixed = s.get("fixed", {}).get(tab)
                st.append({"name": s["name"], "text": getattr(models, fixed) if fixed else frame.format(look=s["look"])})
            if st:
                groups.append({"name": g["name"], "styles": st})
        out[tab] = {"groups": groups}
    return out


def main() -> int:
    data = json.loads(OUT.read_text(encoding="utf-8"))
    modes = data.get("modes", {})
    new = {"txt2img": modes["txt2img"]} if "txt2img" in modes else {}
    new.update(build())
    new.update({k: v for k, v in modes.items() if k not in new})
    data["modes"] = new
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for tab in FRAMES:
        print(f"{tab}: {sum(len(g['styles']) for g in new[tab]['groups'])} styles in {len(new[tab]['groups'])} groups")
    return 0


if __name__ == "__main__":
    sys.exit(main())
