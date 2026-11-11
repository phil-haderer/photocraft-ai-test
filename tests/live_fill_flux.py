"""Manual check (not part of run_all.py): Fill for Flux 3 and Flux 2 (user 9.11.; PLAN.md 2.3, point 2a).

Flux 3 and Flux 2 have no Fill. Their Remove already runs the way Fill runs for Fibo and Qwen: a crop around the selection
(Context 40 %), the selection drawn into it as a red outline, the model's Edit workflow, a soft layer mask back. This round
runs Fill for the two Flux models exactly that way, directly in ComfyUI (no PhotoCraft, nothing in the plugin changes),
with the two Fill sentences the plugin already has:

    fit     bridge.FILL_PROMPT        "... scaled to fit it ..."          (Fibo's wording)
    large   bridge.FILL_PROMPT_LARGE  "... as large as the red outline"   (Qwen's wording)

Qwen Image 2.1 Fill runs alongside as the reference, with its own start values and its own wording (large).
8 cases (4 photos x 2 objects, the user approved the selections on 9.11.), 2 seeds:
Flux 3 and Flux 2 x 2 wordings x 8 x 2 = 64, Qwen 8 x 2 = 16, together 80 pictures (about 30 to 40 minutes).

    python tests\\live_fill_flux.py preview --images <folder>   (the selections and what the model gets; no ComfyUI)
    python tests\\live_fill_flux.py run --images <folder> [--dry]   (--dry: everything but ComfyUI, the crop comes back as it is)
    python tests\\live_fill_flux.py run --images <folder> --round 2   (round 2: approaches A, C, D, E on 12 cases, 216
                                                                       pictures, about 45 min; docs/tests/fill-flux-runde2-plan.md)
    python tests\\live_fill_flux.py run --images <folder> --round 4 [--url http://<ip>:8188]   (round 4: Flux 2, C against C+, 16 pictures)
    python tests\\live_fill_flux.py run ... --models flux2 --seeds 11 --cases 1,3,6,7,9,10,11,12   (a cut round; also
                                                                       --approaches; user 10.11. for PC B's 8 GB card)
    python tests\\live_fill_flux.py merge <folder> <folder> ...   (several runs as one folder, for one blind rating)
    python tests\\live_fill_flux.py rate        (blind, one at a time: G good, S bad, 1 to 8 faults, also on good ones)
    python tests\\live_fill_flux.py summary     (tables, also written to ergebnis.md)

<folder> is the folder with the 2 MP test photos of the sketch rounds (05_full-shot-kid.png, 09_..., 10_..., 11_...).
Output: data\\fill-flux-test\\<time>\\ (bilder, eingabe, key.json, bewertung.json, ergebnis.md). Needs the GPU: before
the run, remind the user not to use ComfyUI or other GPU programs meanwhile.
"""
import argparse
import json
import math
import random
import socket
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFilter  # noqa: E402

from pccomfy import config as cfgmod, fillmask, imaging, models, workflows  # noqa: E402
from pccomfy.bridge import (FILL_PROMPT, FILL_PROMPT_LARGE, Bridge, Request, _shape, has_tag,  # noqa: E402
                            outline_width, prompt_phase_nodes, soft_layer_mask)

BASE = cfgmod.CONFIG_DIR / "fill-flux-test"
GOOD, BAD = "gut", "schlecht"
SEEDS = (11, 12)
CONTEXT = 0.4

# (photo, what goes in, selection shape, x0, y0, x1, y1 as shares of the photo); approved by the user on 9.11.
CASES = [
    ("05_full-shot-kid.png", "a brown dog sitting in the grass", "lasso", 0.53, 0.68, 0.71, 0.98),
    ("05_full-shot-kid.png", "a straw hat lying in the grass", "rect", 0.04, 0.83, 0.16, 0.95),
    ("10_trees-growing-forest.png", "a deer standing between the trees", "lasso", 0.40, 0.55, 0.60, 0.88),
    ("10_trees-growing-forest.png", "a fallen tree trunk lying on the ground", "rect", 0.62, 0.82, 0.95, 0.96),
    ("09_students-working-study.png", "an open laptop", "rect", 0.08, 0.30, 0.25, 0.52),
    ("09_students-working-study.png", "a cup of coffee", "lasso", 0.14, 0.14, 0.21, 0.24),
    ("11_view-modern-construction.png", "a yellow excavator", "rect", 0.68, 0.50, 0.95, 0.90),
    ("11_view-modern-construction.png", "a construction worker in an orange vest", "lasso", 0.02, 0.10, 0.11, 0.42),
]
WORDINGS = {"fit": FILL_PROMPT, "large": FILL_PROMPT_LARGE}

# Round 2 (user 9.11., "wie vorgeschlagen", docs/tests/fill-flux-runde2-plan.md): new prompt approaches against round 1's
# faults (red line left, large objects too small, the object takes the selection's shape, doubled parts), on the 8 cases
# of round 1 plus 4 large objects (approved by the user on 9.11.)
CASES2 = CASES + [
    ("11_view-modern-construction.png", "a red pickup truck", "rect", 0.62, 0.30, 0.97, 0.58),
    ("02_environmental-pollution-industry.png", "a hot air balloon", "lasso", 0.74, 0.03, 0.96, 0.40),
    ("10_trees-growing-forest.png", "a hiker walking on the forest floor", "lasso", 0.32, 0.40, 0.44, 0.94),
    ("06_happy-family-park.png", "a large old oak tree", "rect", 0.02, 0.00, 0.27, 0.34),
]
# A   round 1's better sentence ("large"), as the reference
# C   round 1's "large" sentence plus "its natural shape, not the outline's" (user 10.11.: C alone instead of BC,
#     an image model hardly turns "60 % of the height" into size)
# D   the "large" sentence goes to BFL's prompt upsampler, which sees the marked crop (the Sketch workflows of the plugin)
# E   a see-through red area instead of the outline, "replace the red area" (like "Scribble on photo", 16/16 there)
SHAPE_PROMPT = ("{text}. Make it as large as the red {shape}, filling it from edge to edge, and blend it into the scene "
                "(light, shadows, perspective). Give it its natural shape: the red {shape} only marks the area, it is not the "
                "shape of the object. Do not change anything outside the red {shape}. Also remove the red {shape} itself.")
AREA_PROMPT = ("{text}. Replace the red area with it, as large as the red area and filling it from edge to edge, with its "
               "natural shape, blended into the scene (light, shadows, perspective). Do not change anything outside the "
               "red area. No red may remain.")
APPROACHES = ("A", "C", "D", "E")
RUNS2 = [(m, ap) for m in ("flux3", "flux2") for ap in APPROACHES] + [("qwen", "A")]
# Round 3 (user 10.11.): Flux 3 failed on large objects with A and C (the pickup came back empty, the line removed, as
# in Remove); E and D never ran (round 2 was cut). "+" puts a verb in front of the subject: "Add a red pickup truck."
# instead of "a red pickup truck." (idea of the user). On the hard cases: --cases 4,5,7,9,12
RUNS3 = [("flux3", ap) for ap in ("A", "A+", "E", "E+")]
ADD_VERB = "Add "
# Round 4 (user 11.11.): "Add" for Flux 2 too, C against C+, on the 8 cases and the seed Flux 2 had in round 2 (so C is
# comparable with round 2): --round 4 = 8 cases x 1 seed x 2 approaches = 16 pictures
RUNS4 = [("flux2", ap) for ap in ("C", "C+")]
ROUND4_CASES = (0, 2, 5, 6, 8, 9, 10, 11)            # cases 1, 3, 6, 7, 9, 10, 11, 12 (counted from 1 in the rating)
ROUND4_SEEDS = (11,)


def base(approach: str) -> str:
    """The approach without the "+" of the verb variant (A+ is A with "Add ...")."""
    return (approach or "").rstrip("+")
SKETCH_WF = {"flux3": "flux3-klein-sketch.json", "flux2": "flux2-klein-sketch.json"}
AREA_ALPHA = 0.55                     # how much red covers the selection in approach E
# Flux: the settings of its Remove (Edit workflow, base size of its Edit, Context 40 %, Edge feather 10 %);
# Qwen: its Fill start values as they are
FLUX_FILL = {"flux3": dict(models.BY_KEY["flux3"].modes["remove"].settings),
             "flux2": dict(models.BY_KEY["flux2"].modes["remove"].settings)}
RUNS = [("flux3", "fit"), ("flux3", "large"), ("flux2", "fit"), ("flux2", "large"), ("qwen", "large")]

FAULTS = (
    ("1", "line", "Rote Linie sichtbar"),
    ("2", "cut", "Abgeschnitten (Objekt oder Schatten an der Maskenkante)"),
    ("3", "edge", "Kante sichtbar (Rand, Schleier, Farb- oder Helligkeitssprung)"),
    ("4", "ghost", "Doppelt / Geist"),
    ("5", "soft", "Unscharf (weicher als das Foto)"),
    ("6", "fit", "Passt nicht (Größe, Licht, Perspektive)"),
    ("7", "wrong", "Objekt falsch oder fehlt"),
    ("8", "around", "Umgebung verändert (außerhalb der Auswahl)"),
)


def selection(size: tuple, shape: str, box: tuple) -> Image.Image:
    """The selection: a rectangle, or a lasso (an ellipse with a little wobble, as drawn by hand)."""
    W, H = size
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = box[0] * W, box[1] * H, box[2] * W, box[3] * H
    if shape == "rect":
        d.rectangle([x0, y0, x1, y1], fill=255)
    else:
        cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
        pts = [(cx + rx * (1 + 0.06 * math.sin(5 * t)) * math.cos(t), cy + ry * (1 + 0.06 * math.sin(5 * t)) * math.sin(t))
               for t in (i * 2 * math.pi / 72 for i in range(72))]
        d.polygon(pts, fill=255)
    return m


def settings(model: str) -> dict:
    return FLUX_FILL[model] if model in FLUX_FILL else dict(models.BY_KEY[model].modes["inpaint"].settings)


def workflow(model: str, approach: str = "") -> str:
    if base(approach) == "D":                                # the Sketch workflow: Edit + BFL's prompt upsampler
        return str(ROOT / "workflows" / SKETCH_WF[model])
    mode = "remove" if model in FLUX_FILL else "inpaint"      # Flux: the Edit workflow its Remove uses
    return str(ROOT / "workflows" / models.BY_KEY[model].modes[mode].workflow)


def cases(rnd: int = 1) -> list:
    return CASES2 if rnd >= 2 else CASES


def jobs(rnd: int = 1, only_models=None, only_approaches=None, only_seeds=None, only_cases=None) -> list:
    """Every run: (case number, model, wording or approach, seed); one model after the other, so each is loaded once.
    The only_* filters cut the round (user 10.11.: on PC B's 8 GB card the full round 2 takes about two hours);
    only_cases counts from 1 like the case numbers in the rating."""
    return [(c, m, w, s) for m, w in {1: RUNS, 2: RUNS2, 3: RUNS3, 4: RUNS4}[rnd]
            for c in (ROUND4_CASES if rnd == 4 else range(len(cases(rnd)))) for s in (ROUND4_SEEDS if rnd == 4 else SEEDS)
            if (not only_models or m in only_models) and (not only_approaches or w in only_approaches)
            and (not only_seeds or s in only_seeds) and (not only_cases or c + 1 in only_cases)]


def shuffled(items: dict) -> list:
    order = list(items)
    random.Random(9).shuffle(order)
    return order


def merge(folders: list, out: Path) -> dict:
    """Several runs of one round (a cut run plus an aborted one) as one folder: pictures renumbered, one blind order.
    The case numbers stay, so the inputs (eingabe) of the first folder serve all."""
    for d in ("bilder", "eingabe", "gesendet"):
        (out / d).mkdir(parents=True)
    items = {}
    for k, f in enumerate(folders):
        f = Path(f)
        for fid, it in json.load(open(f / "key.json", encoding="utf-8"))["items"].items():
            if not (f / "bilder" / f"{fid}.png").exists():
                continue
            nid = f"{len(items) + 1:03d}"
            (out / "bilder" / f"{nid}.png").write_bytes((f / "bilder" / f"{fid}.png").read_bytes())
            items[nid] = dict(it, source=f"{f.name}/{fid}")
        for d in ("eingabe", "gesendet"):
            for p in (f / d).iterdir():
                if not (out / d / p.name).exists():
                    (out / d / p.name).write_bytes(p.read_bytes())
    key = {"items": items, "order": shuffled(items), "merged": [Path(f).name for f in folders]}
    json.dump(key, open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return key


def prompt_of(case: int, wording: str, mask: Image.Image, region: imaging.Box, rnd: int = 1) -> str:
    text, sel = cases(rnd)[case][1], mask.crop(region.pil())
    if wording.endswith("+"):                              # the verb variant: "Add a red pickup truck. ..."
        text, wording = ADD_VERB + text, wording[:-1]
    if wording == "C":
        return SHAPE_PROMPT.format(text=text, shape=_shape(sel))
    if wording == "E":
        return AREA_PROMPT.format(text=text)
    return WORDINGS["large" if wording in ("A", "D") else wording].format(text=text, shape=_shape(sel))


def mark_area(crop: Image.Image, sel: Image.Image) -> Image.Image:
    """Approach E: the selection covered with see-through red."""
    red = Image.new("RGB", crop.size, (255, 0, 0))
    a = sel.convert("L").point(lambda v: round(255 * AREA_ALPHA) if v > 127 else 0)
    return Image.composite(red, crop.convert("RGB"), a)


def prepare(photo: Image.Image, case: int, model: str, rnd: int = 1, approach: str = ""):
    """The crop as the bridge sends it: region, generation size, the crop with the red outline (or area), the selection."""
    _, _, shape, *box = cases(rnd)[case]
    st = settings(model)
    tpl = workflows.load_template(workflow(model, approach))
    mask = selection(photo.size, shape, box)
    region = imaging.grow_box(imaging.mask_bbox(mask), photo.size, st.get("context", CONTEXT))
    gw, gh = imaging.gen_size(region.w, region.h, st.get("base_res", 1024), multiple=workflows.size_multiple(tpl))
    crop = imaging.to_rgb(photo.crop(region.pil())).resize((gw, gh), Image.LANCZOS)
    sel = mask.crop(region.pil()).resize((gw, gh), Image.NEAREST)
    marked = mark_area(crop, sel) if base(approach) == "E" else imaging.mark_outline(crop, sel, outline_width(gw, gh))
    return mask, region, (gw, gh), crop, marked


def request(model: str, approach: str = "") -> Request:
    st = settings(model)
    return Request(mode="inpaint", workflow=workflow(model, approach), enhance=(base(approach) == "D") or st.get("enhance", True),
                   turbo=st.get("turbo", True), base_res=st.get("base_res", 1024), context=st.get("context", CONTEXT),
                   feather_pct=st.get("feather_pct", 2.0), mask_grow=st.get("mask_grow", 8), mask_blur=st.get("mask_blur", 8))


def put_back(photo: Image.Image, result: Image.Image, mask: Image.Image, region: imaging.Box, model: str,
             approach: str = "") -> Image.Image:
    """The picture as PhotoCraft shows it after the run: the result over the photo through the plugin's soft layer mask."""
    m = soft_layer_mask(request(model, approach), [workflow(model, approach)], mask, region, imaging.mask_bbox(mask))
    return fillmask.composite(photo, result, region, m, 100)


class _NoPhotoCraft:
    pass


def comfy_or_exit(url: str = ""):
    url = url or cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    try:
        socket.create_connection((host, port), timeout=2).close()
    except OSError:
        sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    from pccomfy.comfy import ComfyUI
    return ComfyUI(url)


def photos(folder: Path, rnd: int = 1) -> dict:
    need = sorted({c[0] for c in cases(rnd)})
    missing = [n for n in need if not (folder / n).exists()]
    if missing:
        sys.exit(f"Missing in {folder}: {', '.join(missing)}")
    return {n: Image.open(folder / n).convert("RGB") for n in need}


def view_box(region, size, grow=0.25):
    x, y, w, h = region
    dx, dy = round(w * grow), round(h * grow)
    return max(0, x - dx), max(0, y - dy), min(size[0], x + w + dx), min(size[1], y + h + dy)


def cmd_preview(a):
    pics = photos(Path(a.images))
    out = BASE / "vorschau"
    out.mkdir(parents=True, exist_ok=True)
    for i, (name, subject, shape, *_) in enumerate(CASES):
        mask, region, (gw, gh), _, marked = prepare(pics[name], i, "flux3")
        left = imaging.mark_outline(pics[name], mask, 5)
        ImageDraw.Draw(left).rectangle([region.x, region.y, region.x + region.w - 1, region.y + region.h - 1], outline=(0, 120, 255), width=6)
        left.thumbnail((900, 900))
        marked.thumbnail((600, 600))
        sheet = Image.new("RGB", (left.width + marked.width + 30, max(left.height, marked.height) + 40), "white")
        sheet.paste(left, (0, 40))
        sheet.paste(marked, (left.width + 30, 40))
        ImageDraw.Draw(sheet).text((6, 8), f"{i + 1}. \"{subject}\" ({shape}; Flux 3 {gw}x{gh})", fill="black")
        sheet.save(out / f"{i + 1:02d}.png")
    print(f"{len(CASES)} previews in {out}")


def cmd_run(a):
    rnd = a.round
    pics = photos(Path(a.images), rnd)
    b = None if a.dry else Bridge(_NoPhotoCraft(), comfy_or_exit(a.url), BASE / "xch")
    todo = jobs(rnd, _list(a.models), _list(a.approaches), [int(s) for s in _list(a.seeds)], [int(c) for c in _list(a.cases)])
    if not todo:
        sys.exit("The filters leave no picture to make.")
    cut = a.models or a.approaches or a.seeds or a.cases
    out = BASE / (time.strftime("%Y%m%d-%H%M%S") + (f"-r{rnd}" if rnd >= 2 else "") + ("-teil" if cut else "") + ("-dry" if a.dry else ""))
    for d in ("bilder", "eingabe", "gesendet"):
        (out / d).mkdir(parents=True)
    for i, (name, _, shape, *box) in enumerate(cases(rnd)):     # the input for the rating: the photo with the selection
        im = imaging.mark_outline(pics[name], selection(pics[name].size, shape, box), 3, (242, 140, 40))
        im.save(out / "eingabe" / f"{i + 1:02d}.png")
    items, t_start = {}, time.time()
    for n, (case, model, wording, seed) in enumerate(todo, 1):
        name = cases(rnd)[case][0]
        approach = wording if rnd >= 2 else ""
        mask, region, (gw, gh), crop, marked = prepare(pics[name], case, model, rnd, approach)
        prompt = prompt_of(case, wording, mask, region, rnd)
        if seed == SEEDS[0]:                                        # what the model got, to look at afterwards
            marked.save(out / "gesendet" / f"{case + 1:02d}-{model}-{wording}.jpg", quality=85)
        t0 = time.time()
        if b is None:
            rgb = crop
        else:
            tag = f"fillflux-{model}-{time.time_ns() % 10**9}"
            iname = b.comfy.upload_image(marked, f"{tag}-image.png")
            wf = workflow(model, approach)
            tpl = workflows.load_template(wf)
            mname = None
            req = request(model, approach)
            if has_tag(tpl, "mask"):           # Qwen's workflow takes the mask too; the Flux Edit ones have none
                m = imaging.prepare_mask(mask.crop(region.pil()), req.mask_grow, req.mask_blur).resize((gw, gh), Image.BILINEAR)
                mname = b.comfy.upload_image(m.convert("RGB"), f"{tag}-mask.png")
            p = workflows.GenParams(prompt=prompt, seed=seed, width=gw, height=gh)
            graph, out_node = b._graph(req, p, iname, mname, wf, force_plain=not (req.enhance and prompt_phase_nodes(tpl)))
            hist = b._wait(b.comfy.queue(graph), graph, wf, 0, 1, "", lambda *x, **k: None)
            rgb = b.comfy.output_images(hist, out_node)[0].convert("RGB")
            if models.BY_KEY[model].seam == "on":
                rgb = imaging.seam_correct(rgb, crop, mask.crop(region.pil()).resize(rgb.size, Image.BILINEAR))
        fid = f"{n:03d}"
        put_back(pics[name], rgb, mask, region, model, approach).save(out / "bilder" / f"{fid}.png")
        items[fid] = {"case": case + 1, "photo": name, "subject": cases(rnd)[case][1], "shape": cases(rnd)[case][2], "model": model,
                      "wording": wording, "seed": seed, "prompt": prompt, "size": [gw, gh],
                      "region": [region.x, region.y, region.w, region.h], "secs": round(time.time() - t0, 1)}
        left = (time.time() - t_start) / n * (len(todo) - n)
        print(f"{n}/{len(todo)} {model} {wording} case {case + 1} seed {seed}: {time.time() - t0:.0f} s"
              f"  (about {left / 60:.0f} min left)", flush=True)
        json.dump({"items": items}, open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump({"items": items, "order": shuffled(items)}, open(out / "key.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min: {len(items)} pictures in {out}\n"
          f"Next: python tests\\live_fill_flux.py rate", flush=True)


def latest(folder):
    if folder:
        return Path(folder)
    runs = sorted(p for p in BASE.iterdir() if (p / "key.json").exists() and not p.name.endswith("-dry")) if BASE.exists() else []
    if not runs:
        sys.exit(f"No test round in {BASE}")
    return runs[-1]


def cmd_rate(a):
    """One result at a time beside its input (the photo with the selection); model, wording and seed stay hidden."""
    import tkinter as tk
    from PIL import ImageTk
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    items = key["items"]
    order = key.get("order") or shuffled(items)          # an aborted run has no order yet
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    root = tk.Tk()
    root.title("Fill Flux bewerten (blind)")
    root.configure(bg="#282828")
    st = {"i": next((k for k, f in enumerate(order) if not data.get(f, {}).get("wahl")), 0), "loading": False, "whole": False}
    faults = {code: tk.BooleanVar() for _, code, _ in FAULTS}
    choice, note = tk.StringVar(), tk.StringVar()
    top = tk.Label(root, bg="#282828", fg="#e6e6e6", font=("Segoe UI", 12, "bold"))
    top.pack(pady=(8, 4))
    row = tk.Frame(root, bg="#282828")
    row.pack()
    pics = [tk.Label(row, bg="#282828") for _ in range(2)]
    for p in pics:
        p.pack(side="left", padx=6)
    side = tk.Frame(root, bg="#282828")
    side.pack(pady=6)
    kw = dict(bg="#282828", selectcolor="#535353", activebackground="#282828", activeforeground="#ffffff",
              font=("Segoe UI", 11), command=lambda: save())
    tk.Radiobutton(side, text="gut (G)", variable=choice, value=GOOD, fg="#7bd389", **kw).pack(side="left", padx=12)
    tk.Radiobutton(side, text="schlecht (S)", variable=choice, value=BAD, fg="#f07b7b", **kw).pack(side="left", padx=12)
    tk.Button(side, text="Ganzes Bild (V)", command=lambda: whole()).pack(side="left", padx=12)
    ff = tk.Frame(root, bg="#282828")
    ff.pack(pady=2)
    tk.Label(ff, text="Fehler ankreuzen (Tasten 1–8, auch bei „gut“):", bg="#282828", fg="#cfcfcf",
             font=("Segoe UI", 10)).grid(row=0, column=0, columnspan=4, sticky="w")
    for k, (digit, code, text) in enumerate(FAULTS):
        tk.Checkbutton(ff, text=f"{digit}  {text}", variable=faults[code], bg="#282828", fg="#f0c674", selectcolor="#535353",
                       activebackground="#282828", activeforeground="#ffffff", font=("Segoe UI", 10),
                       command=lambda: save()).grid(row=1 + k // 4, column=k % 4, sticky="w", padx=8)
    nf = tk.Frame(root, bg="#282828")
    nf.pack(pady=4)
    tk.Label(nf, text="Notiz:", bg="#282828", fg="#cfcfcf").pack(side="left")
    ent = tk.Entry(nf, textvariable=note, bg="#535353", fg="#ffffff", insertbackground="#ffffff", width=90)
    ent.pack(side="left", padx=6)
    nav = tk.Frame(root, bg="#282828")
    nav.pack(pady=4)
    tk.Button(nav, text="← Zurück", command=lambda: go(-1)).pack(side="left")
    tk.Button(nav, text="Weiter →", command=lambda: go(1)).pack(side="left", padx=8)
    status = tk.Label(nav, bg="#282828", fg="#9a9a9a")
    status.pack(side="left", padx=16)

    def count():
        status.configure(text=f"bewertet: {sum(1 for f in order if data.get(f, {}).get('wahl'))}/{len(order)}  ·  gespeichert in {fout}")

    def show():
        fid = order[st["i"]]
        it = items[fid]
        top.configure(text=f"Bild {st['i'] + 1}/{len(order)}  ·  „{it['subject']}“   (links Eingabe mit Auswahl, rechts Ergebnis)")
        side_px = min((root.winfo_screenwidth() - 60) // 2, root.winfo_screenheight() - 330)
        st["photos"] = []
        for lbl, path in zip(pics, (out / "eingabe" / f"{it['case']:02d}.png", out / "bilder" / f"{fid}.png")):
            im = Image.open(path).convert("RGB")
            if not st["whole"]:
                im = im.crop(view_box(it["region"], im.size))
            im.thumbnail((side_px, side_px))
            ph = ImageTk.PhotoImage(im)
            st["photos"].append(ph)
            lbl.configure(image=ph)
        st["loading"] = True
        rec = data.get(fid, {})
        choice.set(rec.get("wahl", ""))
        note.set(rec.get("notiz", ""))
        for code, var in faults.items():
            var.set(code in rec.get("fehler", []))
        st["loading"] = False
        count()

    def save():
        if st["loading"]:
            return
        fid = order[st["i"]]
        data[fid] = {"wahl": choice.get(), "notiz": note.get().strip(), "fehler": [c for _, c, _ in FAULTS if faults[c].get()]}
        fout.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        count()

    def go(step):
        st["i"] = max(0, min(len(order) - 1, st["i"] + step))
        show()

    def whole():
        st["whole"] = not st["whole"]
        show()

    def key_press(e):
        if root.focus_get() is ent:
            return
        if e.char.lower() in ("g", "s"):
            choice.set(GOOD if e.char.lower() == "g" else BAD)
            save()
            root.after(250, lambda: go(1))
        elif e.keysym in ("Right", "Left"):
            go(1 if e.keysym == "Right" else -1)
        elif e.char.lower() == "v":
            whole()
        elif e.char in {d for d, _, _ in FAULTS}:
            var = faults[next(c for d, c, _ in FAULTS if d == e.char)]
            var.set(not var.get())
            save()

    note.trace_add("write", lambda *x: save())
    root.bind("<Key>", key_press)
    root.bind("<Button-1>", lambda e: root.focus_set() if e.widget in pics else None)
    root.state("zoomed")
    show()
    root.mainloop()


def summarize(key: dict, data: dict) -> str:
    """Per group: good, good without any fault ticked (user 9.11.: he often rates a picture good despite a tick), faults."""
    items = key["items"]

    def table(title, key_of):
        lines = ["", title, "", "| Gruppe | gut | fehlerfrei gut | gut trotz Fehler | " + " | ".join(t.split(" (")[0] for _, _, t in FAULTS) + " |",
                 "|---|---|---|---|" + "---|" * len(FAULTS)]
        groups: dict = {}
        for fid, it in items.items():
            r = data.get(fid, {})
            if not r.get("wahl"):
                continue
            g = groups.setdefault(key_of(it), {"n": 0, "gut": 0, "clean": 0, **{c: 0 for _, c, _ in FAULTS}})
            g["n"] += 1
            good = r["wahl"] == GOOD
            g["gut"] += good
            g["clean"] += good and not r.get("fehler")
            for c in r.get("fehler", []):
                g[c] = g.get(c, 0) + 1
        for name in sorted(groups):
            g = groups[name]
            lines.append(f"| {name} | {g['gut']}/{g['n']} | {g['clean']}/{g['n']} | {g['gut'] - g['clean']} | "
                         + " | ".join(str(g[c]) for _, c, _ in FAULTS) + " |")
        return lines

    rated = sum(1 for f in items if data.get(f, {}).get("wahl"))
    lines = ["# Fill für Flux 3 und Flux 2", "", f"Bewertet: {rated} von {len(items)} Bildern (blind)."]
    lines += table("Je Modell und Satz (fit = „scaled to fit“, large = „as large as the red outline“; Runde 2: A = large, "
                   "C = natürliche Form, D = BFL-Upsampler, E = rote Fläche; + = mit „Add …“ davor):", lambda it: f"{it['model']} · {it['wording']}")
    lines += table("Je Modell:", lambda it: it["model"])
    lines += table("Je Fall und Modell:", lambda it: f"{it['case']} {it['subject']} · {it['model']}")
    secs = {}
    for it in items.values():
        secs.setdefault(it["model"], []).append(it["secs"])
    lines += ["", "Zeit je Bild: " + "; ".join(f"{m} {sum(v) / len(v):.0f} s" for m, v in secs.items())]
    notes = [(items[f], r["notiz"]) for f, r in data.items() if r.get("notiz") and f in items]
    if notes:
        lines += ["", "Notizen:"] + [f"- {it['model']} {it['wording']}, Fall {it['case']} ({it['subject']}), Seed {it['seed']}: {t}"
                                     for it, t in notes]
    return "\n".join(lines) + "\n"


def cmd_summary(a):
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    data = json.loads((out / "bewertung.json").read_text(encoding="utf-8")) if (out / "bewertung.json").exists() else {}
    text = summarize(key, data)
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def _list(text: str) -> list:
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def cmd_merge(a):
    folders = [Path(f) if Path(f).is_absolute() else BASE / f for f in a.folders]
    missing = [str(f) for f in folders if not (f / "key.json").exists()]
    if missing:
        sys.exit(f"No key.json in {', '.join(missing)}")
    out = BASE / (time.strftime("%Y%m%d-%H%M%S") + "-zusammen")
    key = merge(folders, out)
    print(f"{len(key['items'])} pictures in {out}\nNext: python tests\\live_fill_flux.py rate")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("preview", "run"):
        s = sub.add_parser(name)
        s.add_argument("--images", required=True, help="the folder with the 2 MP test photos")
        if name == "run":
            s.add_argument("--dry", action="store_true", help="everything but ComfyUI: the crop comes back unchanged")
            s.add_argument("--round", type=int, default=1, choices=(1, 2, 3, 4), help="4: Flux 2 with C and C+ on 8 cases, 16 pictures; 2: the new prompt approaches A, C, D, E; 3: Flux 3 with A, A+, E, E+ (+ = \"Add ...\")")
            s.add_argument("--url", default="", help="the ComfyUI address (default: config.toml of PCCOMFY_HOME), e.g. http://<ip of PC C>:8188")
            s.add_argument("--models", default="", help="only these models, e.g. flux2 or flux3,flux2")
            s.add_argument("--approaches", default="", help="only these approaches or wordings, e.g. A,C,D,E")
            s.add_argument("--seeds", default="", help="only these seeds, e.g. 11")
            s.add_argument("--cases", default="", help="only these cases (from 1), e.g. 1,3,6,7,9,10,11,12")
    for name in ("rate", "summary"):
        s = sub.add_parser(name)
        s.add_argument("folder", nargs="?", help="the round's folder (default: the newest)")
    s = sub.add_parser("merge", help="several runs of one round as one folder, for one blind rating")
    s.add_argument("folders", nargs="+", help="the run folders (names in data\\fill-flux-test or full paths)")
    a = ap.parse_args()
    {"preview": cmd_preview, "run": cmd_run, "rate": cmd_rate, "summary": cmd_summary, "merge": cmd_merge}[a.cmd](a)


if __name__ == "__main__":
    main()
