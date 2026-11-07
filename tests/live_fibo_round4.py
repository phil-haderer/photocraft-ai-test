r"""Manual check (not part of run_all.py): Fibo Upscale with tiles, with an UltraSharpV2 pre-stage, and UltraSharpV2 alone. (GPU, only after asking the user)

Round of 7.11.2026 (user's request). Five pictures (two portraits from testpics5, three from testpics4original), each shrunk to a 1 MP and a 2 MP source;
factors 1.5x and 2x (3x with --factors 1.5,2,3). Methods (all with Prompt C = QWEN_UPSCALE_DEFAULT, seed 1234, Fibo Edit Turbo, 8 steps):
    fibo      Fibo alone, whole picture in one pass (baseline). Capped at CAP_MP: above that the result is smaller than asked for.
    us_fibo   4x-UltraSharpV2 first, then Fibo in one pass (same cap).
    tiled     Fibo in tiles like workflows/flux3-klein-upscale.json (tiles of about 1280 px + 128 overlap, each tile is its own reference,
              merge, Color Match back to the original); no cap.
    us_only   4x-UltraSharpV2 and a Lanczos scale to the target size; no cap.
A result above the cap is computed once per (picture, source) and reused for the other factors above the cap (it would be the same picture).
Existing result files are skipped, so a run can be repeated after a crash. Writes data/compare-fibo-round4/<folder>/<picture>_<src>mp/<method>_<factor>x.png.

    python tests\live_fibo_round4.py --dry                 only builds the graphs
    python tests\live_fibo_round4.py --smoke               one small tiled run (checks that the tile graph works)
    python tests\live_fibo_round4.py [--factors 1.5,2,3] [--methods fibo,us_fibo,tiled,us_only] [--pictures 0,1,2,3] [--out <folder name>]
"""
import argparse
import copy
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from pccomfy import models, workflows  # noqa: E402
from pccomfy.comfy import ComfyError, ComfyUI  # noqa: E402

P5 = Path("D:/testpics/testpics5 persons")
P4 = Path("D:/testpics/testpics4/original")                    # full-size originals; the script shrinks them to 1 MP and 2 MP itself
PICTURES = [("craig", P5 / "craig-mckay-jmURdhtm7Ng-unsplash.jpg"),          # bald, big beard, black and white
            ("philip", P5 / "philip-martin-5aGUyCW_PJw-unsplash.jpg"),        # whole body, small face, city view
            ("rocks", P4 / "pexels_2407126.jpeg"),                             # rock wall, plants, sunset sky (landscape, portrait format)
            ("chocolate", P4 / "pexels_352803.jpeg"),                          # chocolate box, ornament, berries (food, fine texture)
            ("flowers", P4 / "pexels_297408.jpeg")]                            # purple flowers, water drops, dark background
SOURCES_MP = (1.0, 2.0)
CAP_MP = 3.0
SEED = 1234
US_MODEL = "4x-UltraSharpV2.safetensors"
PROMPT = models.QWEN_UPSCALE_DEFAULT


def _by_class(graph: dict, cls: str) -> str:
    return next(k for k, v in graph.items() if v["class_type"] == cls)


def fibo_graph(image_name: str, mp: float, us: bool = False, tiled: bool = False) -> tuple[dict, str]:
    tpl = workflows.load_template(ROOT / "workflows" / "fibo2-upscale.json")
    p = workflows.GenParams(prompt=PROMPT, seed=SEED, width=64, height=64)
    p.extra["megapixels"] = mp
    g, out = workflows.apply_template(tpl, p, image_name, None)
    src, scale, size, enc = (_by_class(g, c) for c in ("LoadImage", "ImageScaleToTotalPixels", "GetImageSize", "TextEncodeFibo2"))
    if us:
        g["90"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": US_MODEL}}
        g["91"] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["90", 0], "image": [src, 0]}}
        g["92"] = {"class_type": "ImageScaleToTotalPixels", "inputs": dict(g[scale]["inputs"], image=["91", 0])}
        g[size]["inputs"]["image"] = ["92", 0]
        g[enc]["inputs"]["images.image_1"] = ["92", 0]
    if tiled:
        flux = json.load(open(ROOT / "workflows" / "flux3-klein-upscale.json", encoding="utf-8"))
        g[scale]["inputs"]["resolution_steps"] = 32
        for nid, axis in (("170", 0), ("171", 1)):            # tile width / height: equal tiles about 1280 px apart + 128 overlap
            n = copy.deepcopy(flux[nid])
            n["inputs"]["values.a"] = [size, axis]
            g[nid] = n
        g["100"] = {"class_type": "SplitImageToTileList", "inputs": {"image": [scale, 0], "tile_width": ["170", 1], "tile_height": ["171", 1], "overlap": 128}}
        g[enc]["inputs"]["images.image_1"] = ["100", 0]
        g[enc]["inputs"]["width"] = ["170", 1]
        g[enc]["inputs"]["height"] = ["171", 1]
        dec = _by_class(g, "VAEDecode")
        g["101"] = {"class_type": "ImageMergeTileList", "inputs": {"image_list": [dec, 0], "final_width": [size, 0], "final_height": [size, 1], "overlap": 128}}
        g["102"] = {"class_type": "ImageScale", "inputs": {"image": [src, 0], "upscale_method": "lanczos", "width": [size, 0], "height": [size, 1], "crop": "disabled"}}
        g["103"] = {"class_type": "ColorMatch", "inputs": {"image_ref": ["102", 0], "image_target": ["101", 0], "method": "mkl", "strength": 1.0, "multithread": True}}
        g[out]["inputs"]["images"] = ["103", 0]
    return g, out


def us_only_graph(image_name: str, mp: float) -> tuple[dict, str]:
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": US_MODEL}},
        "3": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["3", 0], "upscale_method": "lanczos", "megapixels": mp, "resolution_steps": 32}},
        "5": {"class_type": "PreviewImage", "inputs": {"images": ["4", 0]}},
    }, "5"


def build(method: str, image_name: str, mp: float):
    if method == "fibo":
        return fibo_graph(image_name, mp)
    if method == "us_fibo":
        return fibo_graph(image_name, mp, us=True)
    if method == "tiled":
        return fibo_graph(image_name, mp, tiled=True)
    return us_only_graph(image_name, mp)


def shrink(im: Image.Image, mp: float) -> Image.Image:
    k = (mp * 1e6 / (im.width * im.height)) ** 0.5
    return im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)


def run_one(comfy: ComfyUI, graph: dict, out: str) -> Image.Image:
    for attempt in (1, 2, 3):
        try:
            comfy._json("/free", {"unload_models": True, "free_memory": True})
        except Exception as e:
            print("  /free failed:", str(e)[:80])
        time.sleep(3)
        try:
            return comfy.output_images(comfy.wait(comfy.queue(graph)), out)[0]
        except ComfyError as e:
            print(f"    attempt {attempt} failed ({str(e)[:90]})", flush=True)
            if attempt == 3:
                raise
            time.sleep(20)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--factors", default="1.5,2")
    ap.add_argument("--methods", default="fibo,us_fibo,tiled,us_only")
    ap.add_argument("--pictures", default="0,1,2,3,4")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    factors = [float(x) for x in a.factors.split(",")]
    methods = a.methods.split(",")
    pics = [PICTURES[int(i)] for i in a.pictures.split(",")]
    if a.dry:
        for m in methods:
            build(m, "x.png", 2.0)
        print(f"ok: {len(methods)} graph kinds built")
        return
    comfy = ComfyUI()
    known = comfy._choices("UpscaleModelLoader", "model_name")
    if US_MODEL not in known:
        raise SystemExit(f"ComfyUI does not list {US_MODEL}")
    root = ROOT / "data" / "compare-fibo-round4" / (a.out or ("smoke" if a.smoke else time.strftime("%Y%m%d-%H%M%S")))
    rows = ["| picture | source | factor | method | size | time (s) |", "|---|---|---|---|---|---|"]
    if a.smoke:
        pics, factors, methods, srcs = pics[:1], [1.5], ["tiled"], (1.0,)
    else:
        srcs = SOURCES_MP
    for pic in pics:
        short, path = pic
        full = Image.open(path).convert("RGB")
        for smp in srcs:
            im = shrink(full, smp)
            d = root / f"{short}_{smp:g}mp"
            d.mkdir(parents=True, exist_ok=True)
            im.save(d / "source.png")
            up = comfy.upload_image(im, f"pccomfy-round4-{short}-{smp:g}.png")
            done_capped = {}
            for f in factors:
                target = im.width * im.height * f * f / 1e6
                for m in methods:
                    capped = m in ("fibo", "us_fibo") and target > CAP_MP
                    mp = CAP_MP if capped else target
                    dest = d / f"{m}_{f:g}x.png"
                    if capped and (m, mp) in done_capped:       # same picture as an earlier factor: copy the name only
                        (d / f"{m}_{f:g}x.txt").write_text(f"same as {done_capped[(m, mp)]} (cap {CAP_MP:g} MP)", encoding="utf-8")
                        continue
                    if dest.exists():
                        continue
                    graph, out = build(m, up, mp)
                    t0 = time.monotonic()
                    try:
                        res = run_one(comfy, graph, out)
                    except (ComfyError, OSError) as e:
                        rows.append(f"| {short} | {smp:g} | {f:g}x | {m} | FAILED: {str(e)[:60].replace('|', '/')} | {time.monotonic() - t0:.1f} |")
                        print(rows[-1], flush=True)
                        if isinstance(e, OSError):
                            raise SystemExit("ComfyUI not reachable: stopping (restart it, then run again: finished results are skipped)")
                        continue
                    res.save(dest)
                    if capped:
                        done_capped[(m, mp)] = dest.name
                    rows.append(f"| {short} | {smp:g} | {f:g}x | {m}{' (cap ' + format(CAP_MP, 'g') + ' MP)' if capped else ''} | {res.width}x{res.height} | {time.monotonic() - t0:.1f} |")
                    print(rows[-1], flush=True)
    (root / "report.md").write_text("\n".join(["# Fibo round 4", "", *rows, "", f"Prompt C, seed {SEED}, VRAM freed before each run, cap {CAP_MP:g} MP for fibo / us_fibo.", ""]), encoding="utf-8")
    print(f"\nResults: {root}")


if __name__ == "__main__":
    main()
