r"""One picture on a ComfyUI that runs on another PC (manual check, not part of the runner; needs a ComfyUI that answers).

Text to image, portrait 3:4 at 0.5 MP, the window's start values, one seed. The graph is built by the real window code (as in
live_t2i_size_test.py), queued over HTTP, and the picture is fetched with /view and saved on THIS PC. Nothing is changed on the
other PC: the run only queues one job (its result is a preview in ComfyUI's temp folder, gone at the next ComfyUI start).

The address is read like in the other live scripts: from config.toml of PCCOMFY_HOME, or with --url. Use an own home so the
normal settings stay as they are:

    mkdir data\pcc-remote            (git-ignored)
    write data\pcc-remote\config.toml:  [comfyui]  url = "http://<ip of the other PC>:8188"
    set PCCOMFY_HOME=data\pcc-remote
    python tests\live_remote_one.py [--model flux2] [--seed 101]

Output: <PCCOMFY_HOME>/one-picture/bilder/<model>_standard_portrait_0.5MP_s<seed>.png and records.json (model, seed, steps, cfg,
seconds, size, address, time) next to it, so the picture can be put into an evaluation later. Tested with Flux 2 (5.11.2026,
a 16 GB NVIDIA card on another PC, 11.6 s with the first model load)."""
import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402

import live_t2i_size_test as t  # noqa: E402  (the app, the standard request, sizes and prompts of the Text to image round)
from pccomfy import config as cfgmod, inventory, workflows  # noqa: E402
from pccomfy.bridge import Bridge  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", help="the ComfyUI address (default: config.toml of PCCOMFY_HOME)")
    ap.add_argument("--model", default="flux2", choices=t.MODELS)
    ap.add_argument("--seed", type=int, default=101)
    a = ap.parse_args()
    url = a.url or cfgmod.load()["comfyui"]["url"]
    print("ComfyUI:", url, flush=True)
    comfy = ComfyUI(url)
    out = cfgmod.CONFIG_DIR / "one-picture"
    (out / "bilder").mkdir(parents=True, exist_ok=True)
    b = Bridge(t.base._NoPhotoCraft(), comfy, out / "xch")
    app = t.base.make_app(url)
    try:
        inv = inventory.fetch(comfy, cfgmod.model_map())
        if inv.tab_status(a.model).state != "ready":
            sys.exit(f"{a.model}: not all its files are on that ComfyUI")
        name, req, label, lora = t.variants(app, a.model)[0]
        gw, gh = t.SIZES["0.5MP"]["portrait"]
        p = replace(req.params, prompt=t.PROMPTS["portrait"], seed=a.seed, width=gw, height=gh)
        tpl = workflows.load_template(req.workflow)
        needs_image = any(isinstance(nd, dict) and nd.get("_meta", {}).get("title") == "pc:image" for nd in tpl.values())
        image_name = comfy.upload_image(Image.new("RGB", (gw, gh), "white"), "pcc-remote-one.png") if needs_image else None
        graph, out_node = b._graph(req, p, image_name, None, req.workflow)
        t0 = time.time()
        hist = b._wait(comfy.queue(graph), graph, str(req.workflow), 0, 1, "", lambda *x, **k: None)
        im = comfy.output_images(hist, out_node)[0].convert("RGB")
        secs = round(time.time() - t0, 1)
        fn = f"{a.model}_{name}_portrait_0.5MP_s{a.seed}.png"
        im.save(out / "bilder" / fn)
        rec = {"file": fn, "model_key": a.model, "model": label, "variant": name, "prompt": "portrait", "size": "0.5MP", "seed": a.seed,
               "steps": req.params.steps, "cfg": req.params.cfg, "lora": lora, "asked": [gw, gh], "seconds": secs, "got": list(im.size),
               "comfyui": url, "run": time.strftime("%Y-%m-%d %H:%M:%S")}
        recs = json.load(open(out / "records.json", encoding="utf-8")) if (out / "records.json").exists() else []
        recs = [r for r in recs if r["file"] != fn] + [rec]
        json.dump(recs, open(out / "records.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"DONE: {fn} {im.size[0]}x{im.size[1]} in {secs} s -> {out / 'bilder' / fn}", flush=True)
    finally:
        app.root.destroy()


if __name__ == "__main__":
    main()
