"""Builds data/vergleich-fibo-runde4.html: A/B viewer for the round of tests/live_fibo_round4.py (tiles, UltraSharpV2 pre-stage, UltraSharpV2 alone).

Same page as make_fibo_viewer.py (tools/ab_viewer_template.html): thumbnails top left choose A, top right choose B; the prompt is shown above each picture.
One set per picture and source size (1 MP / 2 MP). The page links images relatively, so it has to stay in data/ (git-ignored).
Private repo only: tools/export_release.py leaves it out.

    python tools/make_round4_viewer.py [run folder name, default run1]
"""
import json
import os
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import models  # noqa: E402

DATA = ROOT / "data"
RUN = DATA / "compare-fibo-round4" / (sys.argv[1] if len(sys.argv) > 1 else "run1")
OUT = DATA / "vergleich-fibo-runde4"
(OUT / "thumbs").mkdir(parents=True, exist_ok=True)
PRO = models.QWEN_UPSCALE_DEFAULT
NO = "(no prompt: no AI redraw)"
TITLES = {"craig": "Craig (b/w, beard)", "philip": "Philip (whole body, small face)", "rocks": "Rocks (landscape)", "chocolate": "Chocolate box (food, texture)",
          "flowers": "Flowers (water drops)"}


def rel(p: Path) -> str:
    return os.path.relpath(p, DATA).replace("\\", "/")


def item(label, short, path, prompt):
    th = OUT / "thumbs" / (rel(path).replace("/", "_").replace(".png", ".jpg"))
    if not th.exists():
        im = Image.open(path).convert("RGB")
        im.thumbnail((120, 90), Image.LANCZOS)
        im.save(th, quality=85)
    return {"label": label, "short": short, "src": rel(path), "thumb": rel(th), "prompt": prompt}


sets = []
for d in sorted(RUN.iterdir()):
    if not (d / "source.png").exists():
        continue
    name, mp = d.name.rsplit("_", 1)
    src = Image.open(d / "source.png")
    L = [item(f"Original, shrunk to {mp} ({src.width}x{src.height})", "Original", d / "source.png", "(the picture that goes into every run)")]
    for f in ("1.5", "2"):
        tiled = d / f"tiled_{f}x.png"
        if not tiled.exists():
            continue
        size = Image.open(tiled).size
        lz = OUT / f"lanczos_{d.name}_{f}x.png"
        if not lz.exists():
            src.convert("RGB").resize(size, Image.LANCZOS).save(lz)
        L.append(item(f"Lanczos {f}x (no AI) {size[0]}x{size[1]}", f"Lanczos {f}x", lz, NO))
        for m, short, label, prompt in (
                ("fibo", "Fibo", "Fibo C alone, one pass", PRO),
                ("us_fibo", "US+Fibo", "UltraSharpV2 first, then Fibo C, one pass", "Model stage: 4x-UltraSharpV2, then Fibo with prompt C:\n" + PRO),
                ("tiled", "Tiled", "Fibo C in tiles like Flux 3 (+ Color Match)", "Tiles of about 1280 px + 128 overlap, each tile is its own reference, Color Match back to the original; prompt C:\n" + PRO),
                ("us_only", "US only", "4x-UltraSharpV2 only (+ Lanczos to the size)", NO)):
            path = d / f"{m}_{f}x.png"
            if path.exists():
                capped = m in ("fibo", "us_fibo") and path.stat().st_size and (Image.open(path).width * Image.open(path).height) <= 3.05e6 and Image.open(path).size != size
                note = " [capped at 3 MP; also the result for the higher factors]" if capped else ""
                L.append(item(f"{label}, {f}x{note} {Image.open(path).width}x{Image.open(path).height}", f"{short} {f}x", path, prompt))
    sets.append({"title": f"{TITLES.get(name, name)}, source {mp}", "images": L})

HTML = (Path(__file__).resolve().parent / "ab_viewer_template.html").read_text(encoding="utf-8")
(DATA / "vergleich-fibo-runde4.html").write_text(HTML.replace("__SETS__", json.dumps(sets, ensure_ascii=False)), encoding="utf-8")
print("ok", [(s["title"], len(s["images"])) for s in sets])
