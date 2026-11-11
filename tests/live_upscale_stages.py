r"""Manual check (not part of run_all.py): the upscale stages, cut to about one hour (user 9.11.; PLAN.md 2.3, point 1;
docs/tests/upscale-stufen-testplan.md, "Zuschnitt 9.11."). GPU: remind the user first, start only on his word.

Part F (Fibo, may 3x and 4x be freed?): 2 photos x 3x and 4x x {tiles, us_tiles} = 8 runs.
Part Q (Flux 2 and Qwen Image 2.1 at 2x): 3 photos x {today, us, tiles, us_tiles} x 2 models = 24 runs.
Flux 3 is left out (the user calls its Upscale "perfect"; it already runs US + tiles), and so is 1.5x.

    today     the model's Upscale workflow as the plugin sends it (Flux 2: Ultra real LoRA on)
    us        4x-UltraSharpV2 enlarges first; the model draws from that picture (Qwen: it also becomes its reference)
    tiles     the model draws in tiles of about 1280 px + 128 overlap, each tile its own reference, Color Match back
              (as Flux 3 Upscale and Fibo "Tiles"; needs ComfyUI-KJNodes)
    us_tiles  both
Fibo: its own workflow already has both stages (the plugin lets only one be on); Flux 2 and Qwen get them here only, the
plugin's workflows stay unchanged until the user decides. The sources are the 2 MP photos of the sketch rounds, shrunk to
1 MP; prompt and seed (1234) as in the plugin. VRAM is freed before every run; finished files are skipped on a re-run.

    python tests\live_upscale_stages.py run --images <folder> [--part F|Q] [--dry]
    python tests\live_upscale_stages.py viewer [run folder]    (the blind A/B page; the key stays in key.json)
    python tests\live_upscale_stages.py viewer --serve         (the same page with buttons gut / mittel / schlecht per
                                                                picture, keys G M S; saved into the run's bewertung.json;
                                                                127.0.0.1 only, serves only the page and this run)
    python tests\live_upscale_stages.py summary                (the ratings with the key, into ergebnis.md)

Output: data\upscale-stages\<time>\<photo>\<model>_<factor>x_<variant>.png, report.md, key.json;
page data\vergleich-upscale-stufen.html (relative links: it stays in data\).
"""
import argparse
import copy
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from pccomfy import config as cfgmod, models, workflows  # noqa: E402

DATA = cfgmod.CONFIG_DIR
BASE = DATA / "upscale-stages"
SEED = 1234
SOURCE_MP = 1.0
US_MODEL = "4x-UltraSharpV2.safetensors"
FIBO_PHOTOS = ["04_front-view-boy", "10_trees-growing-forest"]
Q_PHOTOS = ["03_father-with-little", "10_trees-growing-forest", "11_view-modern-construction"]
VARIANTS = ["today", "us", "tiles", "us_tiles"]
WF = {"fibo": "fibo2-upscale.json", "flux2": "flux2-klein-upscale.json", "qwen": "qwen-image-21-upscale.json"}
PROMPT = {"fibo": models.QWEN_UPSCALE_DEFAULT, "flux2": models.FLUX2_DEFAULT, "qwen": models.QWEN_UPSCALE_DEFAULT}
FIBO_US, FIBO_TILES = "12", "102"           # the stage nodes of workflows/fibo2-upscale.json


def jobs(part: str = "") -> list:
    """(photo, model, factor, variant) in run order: one model after the other, each loaded once."""
    out = []
    if part in ("", "F"):
        out += [(p, "fibo", f, v) for f in (3, 4) for v in ("tiles", "us_tiles") for p in FIBO_PHOTOS]
    if part in ("", "Q"):
        out += [(p, m, 2, v) for m in ("flux2", "qwen") for v in VARIANTS for p in Q_PHOTOS]
    return out


def _of(g: dict, cls: str) -> str:
    return next(k for k, v in g.items() if v["class_type"] == cls)


def _titled(g: dict, title: str) -> str:
    return next(k for k, v in g.items() if v.get("_meta", {}).get("title", "").split(" ")[0] == title)


def add_tiles(g: dict, scaled: str, src: str, out: str, decode: str) -> dict:
    """Tiles as in Flux 3 Upscale: equal tiles of about 1280 px + 128 overlap from the scaled picture, merged and colour-matched
    back to the source. Returns the ids the caller wires in: {"tiles", "tile_w", "tile_h"}."""
    flux3 = workflows.load_template(ROOT / "workflows" / "flux3-klein-upscale.json")
    g["180"] = {"class_type": "GetImageSize", "inputs": {"image": [scaled, 0]}}
    for nid, axis in (("170", 0), ("171", 1)):
        n = copy.deepcopy(flux3[nid])
        n["inputs"]["values.a"] = ["180", axis]
        g[nid] = n
    g["100"] = {"class_type": "SplitImageToTileList", "inputs": {"image": [scaled, 0], "tile_width": ["170", 1], "tile_height": ["171", 1], "overlap": 128}}
    g["101"] = {"class_type": "ImageMergeTileList", "inputs": {"image_list": [decode, 0], "final_width": ["180", 0], "final_height": ["180", 1], "overlap": 128}}
    g["102"] = {"class_type": "ImageScale", "inputs": {"image": [src, 0], "upscale_method": "lanczos", "width": ["180", 0], "height": ["180", 1], "crop": "disabled"}}
    g["103"] = {"class_type": "ColorMatch", "inputs": {"image_ref": ["102", 0], "image_target": ["101", 0], "method": "mkl", "strength": 1.0, "multithread": True}}
    g[out]["inputs"]["images"] = ["103", 0]
    return {"tiles": "100", "tile_w": ["170", 1], "tile_h": ["171", 1]}


def build(model: str, variant: str, image_name: str, mp: float) -> tuple[dict, str]:
    us, tiles = variant in ("us", "us_tiles"), variant in ("tiles", "us_tiles")
    tpl = workflows.load_template(ROOT / "workflows" / WF[model])
    st = models.BY_KEY[model].modes["upscale"].settings
    if not st.get("turbo", True):
        tpl = workflows.bypass_lora(tpl)
    if model == "flux2":                      # the plugin's graph has had the stage "Tiles" since 10.11.: this round ran without it
        tpl = workflows.bypass_stage(tpl)
    if model == "fibo":
        if variant == "today":
            raise ValueError("Fibo runs only tiles and us_tiles here")
        off = [] if us else [FIBO_US]          # the stored workflow has both stages; tiles alone = UltraSharp off
        tpl = workflows.bypass_stage(tpl, off) if off else tpl
    p = workflows.GenParams(prompt=PROMPT[model], seed=SEED, width=64, height=64)
    p.extra["megapixels"] = mp
    g, out = workflows.apply_template(tpl, p, image_name, None)
    if model == "fibo":
        return g, out
    src, scaled = _titled(g, "pc:image"), _titled(g, "pc:upscale")
    if us:
        g["90"] = {"class_type": "UpscaleModelLoader", "inputs": {"model_name": US_MODEL}}
        g["91"] = {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["90", 0], "image": [src, 0]}}
        g[scaled]["inputs"]["image"] = ["91", 0]
        if model == "qwen":                   # Qwen reads the small source as its reference: with US it reads the big picture
            g[_of(g, "TextEncodeQwenImage21")]["inputs"]["images.image_1"] = [scaled, 0]
    if tiles:
        t = add_tiles(g, scaled, src, out, _of(g, "VAEDecode"))
        if model == "flux2":
            g[_of(g, "VAEEncode")]["inputs"]["pixels"] = [t["tiles"], 0]
            for cls in ("EmptyFlux2LatentImage", "Flux2Scheduler"):
                g[_of(g, cls)]["inputs"].update(width=t["tile_w"], height=t["tile_h"])
        else:
            g[_of(g, "TextEncodeQwenImage21")]["inputs"]["images.image_1"] = [t["tiles"], 0]
            g[_of(g, "EmptyLatentImage")]["inputs"].update(width=t["tile_w"], height=t["tile_h"])
    return g, out


def links_ok(g: dict) -> list:
    """Every link points at a node of the graph (a dry check without ComfyUI)."""
    return [f"{k}.{i} -> {v[0]}" for k, n in g.items() for i, v in n["inputs"].items()
            if isinstance(v, list) and len(v) == 2 and isinstance(v[1], int) and str(v[0]) not in g]


def shrink(im: Image.Image, mp: float) -> Image.Image:
    k = (mp * 1e6 / (im.width * im.height)) ** 0.5
    return im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)


def run_one(comfy, graph: dict, out: str) -> Image.Image:
    from pccomfy.comfy import ComfyError
    for attempt in (1, 2):
        try:
            comfy._json("/free", {"unload_models": True, "free_memory": True})
        except Exception as e:
            print("  /free failed:", str(e)[:80])
        time.sleep(3)
        try:
            return comfy.output_images(comfy.wait(comfy.queue(graph)), out)[0]
        except ComfyError as e:
            print(f"    attempt {attempt} failed ({str(e)[:120]})", flush=True)
            if attempt == 2:
                raise
            time.sleep(15)


def cmd_run(a):
    folder = Path(a.images)
    todo = jobs(a.part or "")
    need = sorted({p for p, *_ in todo})
    missing = [n for n in need if not (folder / f"{n}.png").exists()]
    if missing:
        sys.exit(f"Missing in {folder}: {', '.join(missing)}")
    if a.dry:
        for _, m, f, v in todo:
            g, _ = build(m, v, "x.png", SOURCE_MP * f * f)
            bad = links_ok(g)
            if bad:
                sys.exit(f"{m} {v}: broken links {bad}")
        print(f"ok: {len(todo)} graphs built, all links point at nodes")
        return
    from pccomfy.comfy import ComfyError, ComfyUI
    comfy = ComfyUI(cfgmod.load()["comfyui"]["url"])
    if US_MODEL not in comfy._choices("UpscaleModelLoader", "model_name"):
        sys.exit(f"ComfyUI does not list {US_MODEL}")
    root = Path(a.out) if a.out else BASE / time.strftime("%Y%m%d-%H%M%S")
    rows = ["| photo | model | factor | variant | size | time (s) |", "|---|---|---|---|---|---|"]
    uploaded, t_start = {}, time.time()
    for n, (photo, m, f, v) in enumerate(todo, 1):
        d = root / photo
        d.mkdir(parents=True, exist_ok=True)
        if photo not in uploaded:
            im = shrink(Image.open(folder / f"{photo}.png").convert("RGB"), SOURCE_MP)
            im.save(d / "source.png")
            uploaded[photo] = (comfy.upload_image(im, f"pccomfy-stages-{photo}.png"), im)
        name, im = uploaded[photo]
        dest = d / f"{m}_{f}x_{v}.png"
        if dest.exists():
            continue
        # ComfyUI's ImageScaleToTotalPixels takes at most 16 MP (9.11.: 4x of the 1 MP source asked 16.01 and was rejected)
        g, out = build(m, v, name, min(16.0, im.width * im.height * f * f / 1e6))
        t0 = time.time()
        try:
            res = run_one(comfy, g, out)
        except (ComfyError, OSError) as e:
            rows.append(f"| {photo} | {m} | {f}x | {v} | FAILED: {str(e)[:60].replace('|', '/')} | {time.time() - t0:.0f} |")
            print(rows[-1], flush=True)
            if isinstance(e, OSError):
                sys.exit("ComfyUI not reachable: stopping (run again with --out to skip the finished ones)")
            continue
        res.save(dest)
        rows.append(f"| {photo} | {m} | {f}x | {v} | {res.width}x{res.height} | {time.time() - t0:.0f} |")
        left = (time.time() - t_start) / n * (len(todo) - n)
        print(f"{n}/{len(todo)} {m} {f}x {v} {photo}: {time.time() - t0:.0f} s (about {left / 60:.0f} min left)", flush=True)
    (root / "report.md").write_text("\n".join([f"# Upscale stages {root.name}", "", *rows, ""]), encoding="utf-8")
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min: {root}\nNext: python tests\\live_upscale_stages.py viewer", flush=True)


def latest(folder):
    if folder:
        return Path(folder)
    runs = sorted(p for p in BASE.iterdir() if (p / "report.md").exists()) if BASE.exists() else []
    if not runs:
        sys.exit(f"No finished run in {BASE}")
    return runs[-1]


def viewer_sets(run: Path, rng: random.Random) -> tuple[list, dict]:
    """One set per photo, model and factor: the source, Lanczos (no AI) and the variants under blind letters."""
    sets, key = [], {}
    for photo_dir in sorted(p for p in run.iterdir() if (p / "source.png").exists()):
        src = photo_dir / "source.png"
        groups = {}
        for f in sorted(photo_dir.glob("*_*x_*.png")):
            m, fac, v = f.stem.split("_", 2)
            groups.setdefault((m, fac), []).append((v, f))
        for (m, fac), items in sorted(groups.items()):
            rng.shuffle(items)
            letters = "ABCD"
            title = f"{photo_dir.name[3:]}, {m}, {fac}"
            key[title] = {letters[i]: v for i, (v, _) in enumerate(items)}
            size = Image.open(items[0][1]).size
            lz = photo_dir / f"lanczos_{m}_{fac}.png"
            if not lz.exists():
                Image.open(src).convert("RGB").resize(size, Image.LANCZOS).save(lz)
            imgs = [("Original 1 MP", src), (f"Lanczos {fac} (no AI)", lz)] + [(f"Variante {letters[i]}", f) for i, (_, f) in enumerate(items)]
            rateable = {f for _, f in items}
            imgs = [(label, f, f"{photo_dir.name}/{f.stem}" if f in rateable else "") for label, f in imgs]
            sets.append({"title": title, "images": imgs})
    return sets, key


PAGE = "vergleich-upscale-stufen.html"
PORT = 8766
GRADES = ("gut", "mittel", "schlecht")


def build_page(run: Path, rate: bool) -> Path:
    sets, key = viewer_sets(run, random.Random(5))
    out = DATA / "vergleich-upscale-stufen"
    (out / "thumbs").mkdir(parents=True, exist_ok=True)

    def rel(p: Path) -> str:
        return os.path.relpath(p, DATA).replace("\\", "/")

    page = []
    for s in sets:
        imgs = []
        for label, path, rid in s["images"]:
            th = out / "thumbs" / (rel(path).replace("/", "_").replace(".png", ".jpg"))
            if not th.exists():
                im = Image.open(path).convert("RGB")
                im.thumbnail((120, 90), Image.LANCZOS)
                im.save(th, quality=85)
            w, h = Image.open(path).size
            imgs.append({"label": f"{label} ({w}x{h})", "short": label, "src": rel(path), "thumb": rel(th), "prompt": "(blind)", "id": rid})
        page.append({"title": s["title"], "images": imgs})
    (run / "key.json").write_text(json.dumps(key, indent=1, ensure_ascii=False), encoding="utf-8")
    html = (ROOT / "tools" / "ab_viewer_template.html").read_text(encoding="utf-8").replace("__SETS__", json.dumps(page, ensure_ascii=False))
    if rate:
        conf = json.dumps({"url": "/rate", "ratings_url": "/ratings"})
        html = html.replace("<script>\nconst SETS", f"<script>window.RATE_CONF = {conf};</script>\n<script>\nconst SETS", 1)
    target = DATA / PAGE
    target.write_text(html, encoding="utf-8")
    print(f"ok: {len(page)} sets in {target}; the key is in {run / 'key.json'}")
    return target


def save_rating(run: Path, rid: str, wahl: str) -> dict:
    """One rating into the run's bewertung.json; the id must be a result picture of the run (photo/stem)."""
    if wahl not in GRADES:
        raise ValueError("unknown rating")
    photo, _, stem = str(rid).partition("/")
    if not photo or "/" in stem or ".." in rid or not (run / photo / f"{stem}.png").is_file() or stem.startswith(("source", "lanczos")):
        raise ValueError("unknown picture")
    f = run / "bewertung.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    data[rid] = wahl
    f.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    return data


def cmd_viewer(a):
    run = latest(a.folder)
    target = build_page(run, a.serve)
    if not a.serve:
        return
    import functools
    import http.server
    import webbrowser
    allowed = (PAGE, "vergleich-upscale-stufen/", os.path.relpath(run, DATA).replace("\\", "/") + "/")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0].lstrip("/")
            if path == "ratings":
                f = run / "bewertung.json"
                self._send(200, f.read_bytes() if f.exists() else b"{}")
            elif path.startswith(allowed) and ".." not in path:      # only the page, its thumbnails and this run's pictures
                super().do_GET()
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path != "/rate":
                self.send_error(404)
                return
            try:
                n = int(self.headers.get("Content-Length") or 0)
                if n > 2000:
                    raise ValueError("request too large")
                body = json.loads(self.rfile.read(n).decode("utf-8"))
                save_rating(run, body.get("id", ""), body.get("wahl", ""))
            except (ValueError, AttributeError) as e:
                self._send(400, str(e).encode("utf-8"), "text/plain; charset=utf-8")
                return
            self._send(200, b'{"ok": true}')

        def log_message(self, fmt, *args):
            pass

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), functools.partial(Handler, directory=str(DATA)))
    url = f"http://127.0.0.1:{a.port}/{target.name}"
    print(f"Rating page: {url}  (saved into {run / 'bewertung.json'}; Ctrl+C or closing this window ends it)", flush=True)
    if not a.no_open:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


def summarize(run: Path) -> str:
    """The ratings with the key: per model and factor, each variant's gut / mittel / schlecht, then per photo."""
    f = run / "bewertung.json"
    data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    rows: dict = {}
    for rid, wahl in data.items():
        photo, _, stem = rid.partition("/")
        m, fac, v = stem.split("_", 2)
        rows.setdefault((m, fac, v), {g: [] for g in GRADES})[wahl].append(photo[3:])
    total = sum(1 for _, m, f_, v in jobs())
    lines = [f"# Upscale-Stufen {run.name}", "", f"Bewertet: {len(data)} von {total} Bildern (blind, gut / mittel / schlecht).", "",
             "| Modell | Faktor | Variante | gut | mittel | schlecht | gut bei |", "|---|---|---|---|---|---|---|"]
    for (m, fac, v) in sorted(rows, key=lambda k: (["fibo", "flux2", "qwen"].index(k[0]), k[1], VARIANTS.index(k[2]))):
        r = rows[(m, fac, v)]
        lines.append(f"| {m} | {fac} | {v} | {len(r['gut'])} | {len(r['mittel'])} | {len(r['schlecht'])} | {', '.join(r['gut'])} |")
    return "\n".join(lines) + "\n"


def cmd_summary(a):
    run = latest(a.folder)
    text = summarize(run)
    (run / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--images", required=True, help="the folder with the 2 MP test photos")
    r.add_argument("--part", choices=("F", "Q"), help="only part F (Fibo 3x/4x) or Q (Flux 2 and Qwen at 2x)")
    r.add_argument("--dry", action="store_true", help="only build the graphs and check their links")
    r.add_argument("--out", help="an earlier run folder to continue (finished files are skipped)")
    v = sub.add_parser("viewer")
    v.add_argument("folder", nargs="?")
    v.add_argument("--serve", action="store_true", help="open the page with rating buttons (gut / mittel / schlecht), saved per run")
    v.add_argument("--port", type=int, default=PORT)
    v.add_argument("--no-open", action="store_true", help="do not open the browser")
    s = sub.add_parser("summary")
    s.add_argument("folder", nargs="?")
    a = ap.parse_args()
    {"run": cmd_run, "viewer": cmd_viewer, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
