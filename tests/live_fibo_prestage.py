r"""Manual check (not part of run_all.py): does a plain upscale model BEFORE Fibo keep Fibo closer to the picture? (GPU, only after asking the user)

Variant A of docs/fibo-upscale-modell-kombination-plan.md, built here in the test only (the plugin is unchanged): the picture first goes through
UpscaleModelLoader + ImageUpscaleWithModel, then to the Fibo target size (ImageScaleToTotalPixels, same MP as Fibo alone), and that picture is the
reference image of TextEncodeFibo2. Prompt C, seed 1234, 1.5x and 2x, sepia portrait and cup (1024 px long side), 2xNomosUni and 4xLSDIR.
Fibo alone (the baseline) is not run again: see data/compare-fibo-prompts/ (same prompt C, seed, megapixels).
Writes data/compare-fibo-prestage/<time>/<picture>_<factor>x_<model>.png and report.md.

    python tests\live_fibo_prestage.py
"""
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
FACTORS = (1.5, 2.0)
MODELS = {"nomos": "2xNomosUni_esrgan_multijpg.safetensors", "lsdir": "4xLSDIR.pth"}


def build(image_name: str, model: str, mp: float) -> tuple[dict, str]:
    tpl = workflows.load_template(ROOT / "workflows" / "fibo2-upscale.json")
    p = workflows.GenParams(prompt=models.QWEN_UPSCALE_DEFAULT, seed=1234, width=64, height=64)
    p.extra["megapixels"] = mp
    graph, out = workflows.apply_template(tpl, p, image_name, None)
    src = next(k for k, v in graph.items() if v["class_type"] == "LoadImage")
    scale = next(k for k, v in graph.items() if v["class_type"] == "ImageScaleToTotalPixels")
    size = next(k for k, v in graph.items() if v["class_type"] == "GetImageSize")
    enc = next(k for k, v in graph.items() if v["class_type"] == "TextEncodeFibo2")
    graph["90"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}}
    graph["91"] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["90", 0], "image": [src, 0]}}
    graph["92"] = {"class_type": "ImageScaleToTotalPixels", "inputs": dict(graph[scale]["inputs"], image=["91", 0])}
    graph[size]["inputs"]["image"] = ["92", 0]
    graph[enc]["inputs"]["images.image_1"] = ["92", 0]
    return graph, out


def main():
    comfy = ComfyUI()
    known = comfy._choices("UpscaleModelLoader", "model_name")
    missing = [m for m in MODELS.values() if m not in known]
    if missing:
        raise SystemExit(f"ComfyUI does not list: {missing}")
    out_dir = ROOT / "data" / "compare-fibo-prestage" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ["| picture | factor | pre-stage | size | time (s) |", "|---|---|---|---|---|"]
    for name, path in PICTURES.items():
        im = Image.open(path).convert("RGB")
        k = 1024 / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        up = comfy.upload_image(im, f"pccomfy-fibo-prestage-{name}.png")
        for f in FACTORS:
            for key, model in MODELS.items():
                graph, out = build(up, model, im.width * im.height * f * f / 1e6)
                try:
                    comfy._json("/free", {"unload_models": True, "free_memory": True})
                except Exception as e:
                    print("  /free failed:", str(e)[:80])
                time.sleep(3)
                t0 = time.monotonic()
                try:
                    res = comfy.output_images(comfy.wait(comfy.queue(graph)), out)[0]
                except (ComfyError, OSError) as e:
                    rows.append(f"| {name} | {f:g}x | {key} | FAILED: {str(e)[:60].replace('|', '/')} | {time.monotonic() - t0:.1f} |")
                    print(rows[-1], flush=True)
                    continue
                res.save(out_dir / f"{name}_{f:g}x_{key}.png")
                rows.append(f"| {name} | {f:g}x | {key} | {res.width}x{res.height} | {time.monotonic() - t0:.1f} |")
                print(rows[-1], flush=True)
    (out_dir / "report.md").write_text("\n".join(["# Fibo Upscale with a model pre-stage", "", *rows, "", "Prompt C, seed 1234, VRAM freed before each run.", ""]), encoding="utf-8")
    print(f"\nResults: {out_dir}")


if __name__ == "__main__":
    main()
