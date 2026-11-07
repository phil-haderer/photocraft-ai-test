"""Builds data/vergleich-fibo-runde3.html: A/B viewer for the Fibo Upscale round of 7.11.2026 (prompts, stability, model pre-stage).

Layout (user's wish 7.11.): small labelled thumbnails at the top left choose picture A, at the top right picture B; below, the two
pictures side by side or toggled in place, at 100 % / 200 % / fit. The page links images relatively, so it has to stay in data/ (git-ignored).
Private repo only: tools/export_release.py leaves it out. For a new round change the folders and `sets`.

    python tools/make_fibo_viewer.py
"""
import json
import os
from pathlib import Path

from PIL import Image

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import models  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
P_OLD = DATA / "compare-fibo-prompts" / "20261106-223426"      # sepia 1.5x A-D, 2x A-B
P_CUP = DATA / "compare-fibo-prompts" / "20261106-222359"      # cup 1.5x A-D, 2x A-B
P_NEW = DATA / "compare-fibo-prompts" / "20261107-104225"      # sepia + cup 2x C, D
PRE = DATA / "compare-fibo-prestage" / "20261107-105141"       # model pre-stage + Fibo, prompt C
STAB = DATA / "compare-fibo-stability" / "20261107-104540"     # sepia at 2.0 / 2.7 / 3.1 MP, 3 runs each
MOD = DATA / "compare-upscale-models" / "20261106-222257"      # plain models, no Fibo
OUT = DATA / "vergleich-fibo-runde3"
(OUT / "thumbs").mkdir(parents=True, exist_ok=True)


def rel(p: Path) -> str:
    return os.path.relpath(p, DATA).replace("\\", "/")


PROMPTS = {  # same texts as tests/live_fibo_prompts.py
    "A": models.FIBO_UPSCALE_DEFAULT,
    "B": "Upscale this image to higher resolution. Preserve every detail, the composition, colors and lighting exactly; add fine natural texture and clean edges.",
    "C": models.QWEN_UPSCALE_DEFAULT,
    "D": "in <image_1>, increase the resolution and sharpness, remove noise and compression artifacts. preserve the style, colors and all details.",
}
NO_PROMPT = "(no prompt: no AI redraw)"


def item(label, short, path, prompt=NO_PROMPT):
    path = Path(path)
    if not path.exists():
        return None
    th = OUT / "thumbs" / (rel(path).replace("/", "_").replace(".png", ".jpg"))
    if not th.exists():
        im = Image.open(path).convert("RGB")
        im.thumbnail((120, 90), Image.LANCZOS)
        im.save(th, quality=85)
    return {"label": label, "short": short, "src": rel(path), "thumb": rel(th), "prompt": prompt}


def lanczos(source: Path, size, name):
    f = OUT / f"lanczos_{name}.png"
    Image.open(source).convert("RGB").resize(size, Image.LANCZOS).save(f)
    return f


def size_of(p: Path):
    return Image.open(p).size


sepia_src = P_OLD / "sepia_source.png"
cup_src = P_CUP / "cup_source.png"
sets = []


def prompts_set(title, src, size_ref, name, abpaths, cdpaths, pre_prefix, models_prefix):
    fl = lanczos(src, size_of(size_ref), name)
    L = [item("Original (source picture, 1024 px long side)", "Original", src, "(the picture that goes into every run)"), item("Lanczos (no AI)", "Lanczos", fl)]
    for k, p in zip("AB", abpaths):
        L.append(item(f"Fibo alone, prompt {k}" + (" (FIBO_UPSCALE_DEFAULT)" if k == "A" else ""), f"Fibo {k}", p, PROMPTS[k]))
    for k, p in zip("CD", cdpaths):
        L.append(item(f"Fibo alone, prompt {k}" + (" (Qwen upscale text)" if k == "C" else ""), f"Fibo {k}", p, PROMPTS[k]))
    L.append(item("2xNomosUni first, then Fibo (prompt C)", "Nomos+Fibo", PRE / f"{pre_prefix}_nomos.png", "Model stage: 2xNomosUni_esrgan_multijpg, then Fibo with prompt C:\n" + PROMPTS["C"]))
    L.append(item("4xLSDIR first, then Fibo (prompt C)", "LSDIR+Fibo", PRE / f"{pre_prefix}_lsdir.png", "Model stage: 4xLSDIR, then Fibo with prompt C:\n" + PROMPTS["C"]))
    if models_prefix:
        L.append(item("2xNomosUni only (no Fibo)", "Nomos only", MOD / f"{models_prefix}_2xNomosUni_esrgan_multijpg.png"))
        L.append(item("4xLSDIR only (no Fibo)", "LSDIR only", MOD / f"{models_prefix}_4xLSDIR.png"))
    sets.append({"title": title, "images": [i for i in L if i]})


prompts_set("Sepia photo 2x (1280x2096)", sepia_src, P_NEW / "sepia_2x_C.png", "sepia_2x",
            [P_OLD / "sepia_2x_A.png", P_OLD / "sepia_2x_B.png"], [P_NEW / "sepia_2x_C.png", P_NEW / "sepia_2x_D.png"], "sepia_2x", "sepia")
prompts_set("Sepia photo 1.5x (960x1568)", sepia_src, P_OLD / "sepia_1.5x_A.png", "sepia_1.5x",
            [P_OLD / "sepia_1.5x_A.png", P_OLD / "sepia_1.5x_B.png"], [P_OLD / "sepia_1.5x_C.png", P_OLD / "sepia_1.5x_D.png"], "sepia_1.5x", None)
prompts_set("Cup 2x (2096x1440)", cup_src, P_NEW / "cup_2x_C.png", "cup_2x",
            [P_CUP / "cup_2x_A.png", P_CUP / "cup_2x_B.png"], [P_NEW / "cup_2x_C.png", P_NEW / "cup_2x_D.png"], "cup_2x", "cup")
prompts_set("Cup 1.5x (1568x1072)", cup_src, P_CUP / "cup_1.5x_A.png", "cup_1.5x",
            [P_CUP / "cup_1.5x_A.png", P_CUP / "cup_1.5x_B.png"], [P_CUP / "cup_1.5x_C.png", P_CUP / "cup_1.5x_D.png"], "cup_1.5x", None)
L = [item("Original (source picture, 1024 px long side)", "Original", sepia_src, "(the picture that goes into every run)"),
     item("Lanczos 2 MP (no AI)", "Lanczos 2", lanczos(sepia_src, size_of(STAB / "sepia_2mp_1.png"), "stab_2")),
     item("Lanczos 3.1 MP (no AI)", "Lanczos 3.1", lanczos(sepia_src, size_of(STAB / "sepia_3.1mp_1.png"), "stab_31"))]
for mp, tag in (("2", "2.0"), ("2.7", "2.7"), ("3.1", "3.1")):
    for n in (1, 2, 3):
        L.append(item(f"Fibo, prompt C, {tag} MP, run {n} (VRAM freed before; all 9 runs ok)", f"{tag} MP #{n}", STAB / f"sepia_{mp}mp_{n}.png", PROMPTS["C"]))
sets.append({"title": "Stability: sepia at 2.0 / 2.7 / 3.1 MP (3 runs each)", "images": [i for i in L if i]})

HTML = (Path(__file__).resolve().parent / "ab_viewer_template.html").read_text(encoding="utf-8")   # shared with make_round4_viewer.py
(DATA / "vergleich-fibo-runde3.html").write_text(HTML.replace("__SETS__", json.dumps(sets, ensure_ascii=False)), encoding="utf-8")
print("ok", [(s["title"], len(s["images"])) for s in sets])
