"""Manual check (not part of run_all.py): Fibo 2 Edit Turbo as an upscaler, after the user's workflow Fibo2_turbo_edit_2K-ROPE.json.

The workflow draws the picture anew at a larger size: TextEncodeFibo2 gets the target width and height, and the core node
ScaleROPE (experimental) stretches Fibo's rotary position embedding so that it can work above its trained size (the user's file:
scale_x 0.85, scale_y 0.8, 8 steps, euler/simple). This script runs that graph (API format, built here) on the test picture
for a few factors and ROPE settings and writes, next to a plain Lanczos enlargement as the reference:
    data/compare-fibo-upscale/<time>/<case>.png          the result
    data/compare-fibo-upscale/<time>/<case>_sheet.png    Lanczos | result | difference (x4 brighter), at the result's size
    data/compare-fibo-upscale/<time>/report.md           time per run and the result's size

    python tests\\live_fibo_upscale.py --cases f2          needs ComfyUI running; uses the GPU (3 runs: factor 2, three ROPE settings)
    python tests\\live_fibo_upscale.py --cases f4          2 runs at factor 4
    python tests\\live_fibo_upscale.py --dry               only builds the graphs and checks the files are known to ComfyUI
Nothing in the plugin changes.
"""
import argparse
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageChops  # noqa: E402

from pccomfy import models  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

UNET = "fibo2_edit_turbo_int8_convrot.safetensors"
CLIP = "qwen3vl_4b_int8_convrot.safetensors"        # the plugin's Fibo text encoder (the user's file uses the bf16 one)
VAE = "flux2-vae.safetensors"
SCENE = ROOT / "data" / "test_scene.png"
PROMPT = models.FLUX2_DEFAULT                        # what Fibo Refine sends today
SEED = 1234
STEPS = 8                                            # the user's workflow (our Edit graph uses 4)

# (name, factor, rope (scale_x, scale_y) or None)
CASES = {
    "f2": [("f2_norope", 2, None), ("f2_rope085-08", 2, (0.85, 0.8)), ("f2_rope05", 2, (0.5, 0.5))],
    "f4": [("f4_norope", 4, None), ("f4_rope085-08", 4, (0.85, 0.8)), ("f4_rope025", 4, (0.25, 0.25))],
}


def size_for(w: int, h: int, factor: float) -> tuple[int, int]:
    """The result's size: each side times the factor, rounded to a multiple of 8 (as the user's math nodes do)."""
    return round(w * factor / 8) * 8, round(h * factor / 8) * 8


def build(image_name: str, size: tuple[int, int], rope, steps: int = STEPS) -> tuple[dict, str]:
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": UNET, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": CLIP, "type": "fibo2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "6": {"class_type": "TextEncodeFibo2", "inputs": {
            "clip": ["2", 0], "prompt": PROMPT, "negative_prompt": "", "vae": ["3", 0], "images.image_1": ["4", 0],
            "width": size[0], "height": size[1], "batch_size": 1}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "PreviewImage", "inputs": {"images": ["8", 0]}},
    }
    model = ["1", 0]
    if rope:
        g["5"] = {"class_type": "ScaleROPE", "inputs": {"model": ["1", 0], "scale_x": rope[0], "shift_x": 0, "scale_y": rope[1],
                                                         "shift_y": 0, "scale_t": 1, "shift_t": 0}}
        model = ["5", 0]
    g["7"] = {"class_type": "KSampler", "inputs": {
        "model": model, "positive": ["6", 0], "negative": ["6", 1], "latent_image": ["6", 2], "seed": SEED, "steps": steps,
        "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1}}
    return g, "9"


def sheet(ref: Image.Image, res: Image.Image) -> Image.Image:
    ref = ref.convert("RGB").resize(res.size, Image.LANCZOS)
    d = ImageChops.difference(ref, res.convert("RGB")).point(lambda v: min(255, v * 4))
    out = Image.new("RGB", (res.width * 3 + 20, res.height), "white")
    for i, im in enumerate((ref, res.convert("RGB"), d)):
        out.paste(im, (i * (res.width + 10), 0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="f2", choices=sorted(CASES))
    ap.add_argument("--dry", action="store_true", help="build the graphs only, run nothing")
    ap.add_argument("--scene", default=str(SCENE), help="the picture (the default is a flat drawing: use a real photo)")
    ap.add_argument("--long", type=int, default=0, help="first shrink the picture so that its longer side is this many pixels (a small source)")
    args = ap.parse_args()
    comfy = ComfyUI()
    for node, field, name in (("UNETLoader", "unet_name", UNET), ("CLIPLoader", "clip_name", CLIP), ("VAELoader", "vae_name", VAE)):
        if name not in comfy._choices(node, field):
            raise SystemExit(f"ComfyUI does not list {name}")
    scene = Image.open(args.scene).convert("RGB")
    if args.long and max(scene.size) > args.long:
        k = args.long / max(scene.size)
        scene = scene.resize((round(scene.width * k), round(scene.height * k)), Image.LANCZOS)
    cases = CASES[args.cases]
    for name, factor, rope in cases:
        build("x.png", size_for(*scene.size, factor), rope)
    if args.dry:
        print(f"ok: files known, {len(cases)} graphs built, picture {scene.size}")
        return
    image_name = comfy.upload_image(scene, "pccomfy-fibo-upscale-scene.png")
    out_dir = ROOT / "data" / "compare-fibo-upscale" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ["| case | factor | ROPE x,y | result size | time (s) |", "|---|---|---|---|---|"]
    for k, (name, factor, rope) in enumerate(cases):
        size = size_for(*scene.size, factor)
        graph, out = build(image_name, size, rope)
        t0 = time.monotonic()
        hist = comfy.wait(comfy.queue(graph))
        secs = time.monotonic() - t0
        im = comfy.output_images(hist, out)[0]
        scene.save(out_dir / "source.png")
        im.save(out_dir / f"{name}.png")
        sheet(scene, im).save(out_dir / f"{name}_sheet.png")
        rows.append(f"| {name} | {factor}x | {rope or 'none'} | {im.width}x{im.height} | {secs:.1f}{' *' if k == 0 else ''} |")
        print(rows[-1])
    (out_dir / "report.md").write_text("\n".join(["# Fibo 2 Edit Turbo as upscaler", "", *rows, "",
                                                  "* = first run (includes loading the model). Prompt: FLUX2_DEFAULT, seed 1234, 8 steps.", ""]), encoding="utf-8")
    print(f"\nResults: {out_dir}")


if __name__ == "__main__":
    main()
