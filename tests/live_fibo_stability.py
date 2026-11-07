r"""Manual check (not part of run_all.py): is Fibo Upscale stable at 2.0 / 2.7 / 3.1 MP? (GPU, only after asking the user)

Sepia portrait (1024 px long side), prompt C (QWEN_UPSCALE_DEFAULT), seed 1234. Each size is run REPEATS times, ascending; VRAM is freed
(POST /free) before every run. No retries: a failure is recorded and the next run goes on; two failures in a row, or a dead server, stop the test.
Writes data/compare-fibo-stability/<time>/ (results as png, report.md).

    python tests\\live_fibo_stability.py
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from pccomfy import models, workflows  # noqa: E402
from pccomfy.comfy import ComfyError, ComfyUI  # noqa: E402

SRC = ROOT / "data" / "flux3-bbox-test" / "web-refs" / "person_kazakh.jpg"
SIZES = (2.0, 2.7, 3.1)
REPEATS = 3


def main():
    comfy = ComfyUI()
    im = Image.open(SRC).convert("RGB")
    k = 1024 / max(im.size)
    im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
    up = comfy.upload_image(im, "pccomfy-fibo-stability.png")
    out_dir = ROOT / "data" / "compare-fibo-stability" / time.strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ["| target MP | run | size | result | time (s) |", "|---|---|---|---|---|"]
    fails = 0
    stop = False
    for mp in SIZES:
        for n in range(1, REPEATS + 1):
            tpl = workflows.load_template(ROOT / "workflows" / "fibo2-upscale.json")
            p = workflows.GenParams(prompt=models.QWEN_UPSCALE_DEFAULT, seed=1234, width=64, height=64)
            p.extra["megapixels"] = mp
            graph, out = workflows.apply_template(tpl, p, up, None)
            try:
                comfy._json("/free", {"unload_models": True, "free_memory": True})
            except Exception as e:
                print("  /free failed:", str(e)[:80])
            time.sleep(3)
            t0 = time.monotonic()
            try:
                hist = comfy.wait(comfy.queue(graph))
                res = comfy.output_images(hist, out)[0]
                res.save(out_dir / f"sepia_{mp:g}mp_{n}.png")
                rows.append(f"| {mp:g} | {n} | {res.width}x{res.height} | ok | {time.monotonic() - t0:.1f} |")
                fails = 0
            except (ComfyError, OSError) as e:
                rows.append(f"| {mp:g} | {n} | | FAILED: {str(e)[:70].replace('|', '/')} | {time.monotonic() - t0:.1f} |")
                fails += 1
                if fails >= 2:
                    stop = True
            print(rows[-1], flush=True)
            if stop:
                break
        if stop:
            break
    (out_dir / "report.md").write_text("\n".join(["# Fibo Upscale stability", "", *rows, "", "Prompt C, seed 1234, VRAM freed before each run.", ""]), encoding="utf-8")
    print(f"\nResults: {out_dir}")


if __name__ == "__main__":
    main()
