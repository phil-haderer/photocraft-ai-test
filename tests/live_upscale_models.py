"""Manual check (not part of run_all.py): which plain upscale models (no redrawing) suit 2x in the plugin?

Like the user's TOOL Upscale workflow (UpscaleModelLoader + ImageUpscaleWithModel), then a Lanczos scale to exactly 2x, for a few
models of ComfyUI's upscale_models folder, on two real photos shrunk to a longer side of 1024 px. Writes
data/compare-upscale-models/<time>/:
    <picture>_<model>.png      the result at 2x
    <picture>_sheet.jpg        Lanczos | models...: the whole picture small (row 1) and a centre detail at 100 % (row 2)
    report.md                  time per run

    python tests\\live_upscale_models.py            needs ComfyUI running; uses the GPU (10 short runs)
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from pccomfy.comfy import ComfyUI  # noqa: E402

REFS = ROOT / "data" / "flux3-bbox-test" / "web-refs"
PICTURES = {"sepia": REFS / "person_kazakh.jpg", "cup": REFS / "thing_cup.jpg"}
LONG = 1024
MODELS = ["RealESRGAN_x2plus.pth", "2xNomosUni_esrgan_multijpg.safetensors", "4x-UltraSharpV2.safetensors", "4xLSDIR.pth",
          "4x_NMKD-Siax_200k.pth"]


def build(image_name: str, model: str, size: tuple[int, int]) -> tuple[dict, str]:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model}},
        "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "ImageScale", "inputs": {"image": ["3", 0], "upscale_method": "lanczos", "width": size[0], "height": size[1], "crop": "disabled"}},
        "5": {"class_type": "PreviewImage", "inputs": {"images": ["4", 0]}},
    }, "5"


def main():
    comfy = ComfyUI()
    known = comfy._choices("UpscaleModelLoader", "model_name")
    missing = [m for m in MODELS if m not in known]
    if missing:
        raise SystemExit(f"ComfyUI does not list: {missing}")
    out_dir = ROOT / "data" / "compare-upscale-models" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ["| picture | model | size | time (s) |", "|---|---|---|---|"]
    for name, path in PICTURES.items():
        im = Image.open(path).convert("RGB")
        k = LONG / max(im.size)
        im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        size = (im.width * 2, im.height * 2)
        up = comfy.upload_image(im, f"pccomfy-upscale-models-{name}.png")
        ims = {"Lanczos": im.resize(size, Image.LANCZOS)}
        for model in MODELS:
            graph, out = build(up, model, size)
            t0 = time.monotonic()
            res = comfy.output_images(comfy.wait(comfy.queue(graph)), out)[0]
            secs = time.monotonic() - t0
            res.save(out_dir / f"{name}_{model.split('.')[0]}.png")
            ims[model.split(".")[0]] = res
            rows.append(f"| {name} | {model} | {res.width}x{res.height} | {secs:.1f} |")
            print(rows[-1], flush=True)
        tw = 300
        th = round(size[1] * tw / size[0])
        x0, y0 = size[0] // 2 - 150, size[1] // 3 - 150
        sheet = Image.new("RGB", (len(ims) * (tw + 6), th + 306), "white")
        for i, r in enumerate(ims.values()):
            sheet.paste(r.convert("RGB").resize((tw, th), Image.LANCZOS), (i * (tw + 6), 0))
            sheet.paste(r.convert("RGB").crop((x0, y0, x0 + 300, y0 + 300)), (i * (tw + 6), th + 6))
        sheet.save(out_dir / f"{name}_sheet.jpg", quality=92)
    (out_dir / "report.md").write_text("\n".join(["# Plain upscale models at 2x", "", *rows, "", "Order in the sheets: Lanczos, " + ", ".join(m.split(".")[0] for m in MODELS), ""]), encoding="utf-8")
    print(f"\nResults: {out_dir}")


if __name__ == "__main__":
    main()
