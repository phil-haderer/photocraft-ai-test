"""Manual check (not part of run_all.py): which prompt makes Fibo Upscale (1.5x and 2x) best?

Runs the plugin's own graph workflows/fibo2-upscale.json (through the same node settings the bridge sets) on two real photos,
each shrunk to a longer side of 1024 px, with four prompts at 1.5x and 2x. Writes data/compare-fibo-prompts/<time>/:
    <picture>_<factor>_<prompt>.png     the result
    <picture>_<factor>_sheet.jpg        Lanczos | A | B | C | D, each cut to the same centre detail (100 %) and the whole picture small
    report.md                           time per run

    python tests\\live_fibo_prompts.py            needs ComfyUI running; uses the GPU (16 runs)
    python tests\\live_fibo_prompts.py --dry      only builds the graphs
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from pccomfy import models, workflows  # noqa: E402
from pccomfy.comfy import ComfyError, ComfyUI  # noqa: E402

REFS = ROOT / "data" / "flux3-bbox-test" / "web-refs"
PICTURES = {"sepia": REFS / "person_kazakh.jpg", "cup": REFS / "thing_cup.jpg"}
LONG = 1024
FACTORS = (1.5, 2.0)
SEED = 1234
PROMPTS = {
    "A": models.FIBO_UPSCALE_DEFAULT,
    "B": "Upscale this image to higher resolution. Preserve every detail, the composition, colors and lighting exactly; add fine natural texture and clean edges.",
    "C": models.QWEN_UPSCALE_DEFAULT,
    "D": "in <image_1>, increase the resolution and sharpness, remove noise and compression artifacts. preserve the style, colors and all details.",
}


def build(image_name: str, prompt: str, mp: float) -> tuple[dict, str]:
    tpl = workflows.load_template(ROOT / "workflows" / "fibo2-upscale.json")
    p = workflows.GenParams(prompt=prompt, seed=SEED, width=64, height=64)
    p.extra["megapixels"] = mp
    return workflows.apply_template(tpl, p, image_name, None)


def detail_sheet(src: Image.Image, results: dict[str, Image.Image], size: tuple[int, int]) -> Image.Image:
    """Row 1: the whole picture small; row 2: a centre detail at 100 % (Lanczos first, then A to D)."""
    names = ["Lanczos"] + list(results)
    ims = [src.resize(size, Image.LANCZOS)] + [results[n] for n in results]
    tw = 300
    th = round(size[1] * tw / size[0])
    cw = ch = 300
    x0, y0 = size[0] // 2 - cw // 2, size[1] // 3 - ch // 2
    sheet = Image.new("RGB", (len(ims) * (tw + 6), th + ch + 12), "white")
    for i, im in enumerate(ims):
        sheet.paste(im.convert("RGB").resize((tw, th), Image.LANCZOS), (i * (tw + 6), 0))
        sheet.paste(im.convert("RGB").crop((x0, y0, x0 + cw, y0 + ch)), (i * (tw + 6), th + 6))
    return sheet


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--pictures", default="", help="comma list of sepia,cup (default: both)")
    ap.add_argument("--factors", default="", help="comma list, e.g. 2 (default: 1.5,2)")
    ap.add_argument("--prompts", default="", help="comma list of A,B,C,D (default: all)")
    args = ap.parse_args()
    global FACTORS, PROMPTS, PICTURES
    if args.factors:
        FACTORS = tuple(float(x) for x in args.factors.split(","))
    if args.prompts:
        PROMPTS = {k: v for k, v in PROMPTS.items() if k in args.prompts.split(",")}
    if args.pictures:
        PICTURES = {k: v for k, v in PICTURES.items() if k in args.pictures.split(",")}
    comfy = ComfyUI()
    pics = {}
    for name, path in PICTURES.items():
        im = Image.open(path).convert("RGB")
        k = LONG / max(im.size)
        pics[name] = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    for name, im in pics.items():
        for f in FACTORS:
            for pr in PROMPTS.values():
                build("x.png", pr, im.width * im.height * f * f / 1e6)
    if args.dry:
        print(f"ok: {len(pics) * len(FACTORS) * len(PROMPTS)} graphs built")
        return
    out_dir = ROOT / "data" / "compare-fibo-prompts" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ["| picture | factor | prompt | size | time (s) |", "|---|---|---|---|---|"]
    first = True
    for name, im in pics.items():
        up = comfy.upload_image(im, f"pccomfy-fibo-prompts-{name}.png")
        im.save(out_dir / f"{name}_source.png")
        for f in FACTORS:
            results = {}
            for key, pr in PROMPTS.items():
                graph, out = build(up, pr, im.width * im.height * f * f / 1e6)
                t0 = time.monotonic()
                for attempt in (1, 2, 3):       # the GPU is shared with other programs: a memory fault is tried again after a pause
                    try:
                        hist = comfy.wait(comfy.queue(graph))
                        break
                    except ComfyError as e:
                        print(f"  {name} {f:g}x {key}: attempt {attempt} failed ({str(e)[:80]})", flush=True)
                        if attempt == 3:
                            raise
                        time.sleep(20)
                secs = time.monotonic() - t0
                res = comfy.output_images(hist, out)[0]
                res.save(out_dir / f"{name}_{f:g}x_{key}.png")
                results[key] = res
                rows.append(f"| {name} | {f:g}x | {key} | {res.width}x{res.height} | {secs:.1f}{' *' if first else ''} |")
                first = False
                print(rows[-1], flush=True)
            size = next(iter(results.values())).size
            detail_sheet(im, results, size).save(out_dir / f"{name}_{f:g}x_sheet.jpg", quality=92)
    (out_dir / "report.md").write_text("\n".join(["# Fibo Upscale: four prompts", "", *rows, "", "* = first run (includes loading). Seed 1234, 8 steps.", "",
                                                  *[f"- {k}: {v}" for k, v in PROMPTS.items()], ""]), encoding="utf-8")
    print(f"\nResults: {out_dir}")


if __name__ == "__main__":
    main()
