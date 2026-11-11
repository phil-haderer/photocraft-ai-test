"""Manual check (not part of run_all.py): plan B step 2, the style pilot (docs/plan-edit-sketch-stile.md; test plan
docs/tests/stil-pilot-testplan.md, user 10.11.). Do the edit models carry a style over the whole picture and keep the
people and the layout? Through the real plugin path (the window's request with the start settings of the mode, the
bridge with the PhotoCraft simulator of test_reference_mode, the real ComfyUI), Flux 3 and Qwen Image 2.1 (pilot 7a) or Flux 2 and Fibo (round 7b, the default), one seed:

- Part A, Edit canvas: 11 styles x 3 photos (03, 05, 11 of the 2 MP photo folder) x 2 models = 66 pictures;
- Part B, Sketch to image: the same 11 styles x 3 sketches of round 3 (house, hyenas, landscape; from
  data\\sketch-test\\round3-*\\eingabe, the subject typed there) x 2 models = 66 pictures;
- Part C, Text to image: the 7 own studio and stock styles (tools\\styles-own.json) x 2 prompts x 2 models = 28 pictures,
  the style added after a line break as the Styles button does.

The text of a style: its look in a frame sentence per tab (EDIT_FRAME, SKETCH_FRAME), Animated film in Sketch to image
word for word the tested template (models.SKETCH_ILLUSTRATION).

    python tests\\live_style_round.py plan --photos <folder>                  (what would run; no ComfyUI)
    python tests\\live_style_round.py run --photos <folder> [--part A B C] [--models flux2 fibo] [--sketches hyenas landscape] [--half | --other-half] [--url http://<ip>:8188] [--into <folder>]
                                          [--dry] [--free]                    (resumes in --into; key.json after every picture)
    python tests\\live_style_round.py rate [folder]       (blind: input left, result right; good / bad, faults 1 to 6)
    python tests\\live_style_round.py summary [folder]    (good and fault-free good per part, model, style; ergebnis.md)

``--dry`` runs the whole bridge against a fake ComfyUI (no GPU) and checks that the text reaches the graph.
Output: data\\style-pilot\\<time>\\ (eingabe\\, bilder\\, key.json, bewertung.json, ergebnis.md).
"""
import argparse
import json
import os
import random
import shutil
import socket
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# a data folder of its own (a copy of settings.json for the address and the linked files): the window built here must not
# write the plugin's state.json while the user works with the plugin
_HOME = Path(tempfile.mkdtemp(prefix="pccomfy-stylepilot-"))
if (DATA / "settings.json").exists():
    shutil.copyfile(DATA / "settings.json", _HOME / "settings.json")
os.environ["PCCOMFY_HOME"] = str(_HOME)
os.environ["PCCOMFY_NO_TIPS"] = "1"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from PIL import Image, ImageDraw  # noqa: E402

import live_sketch  # noqa: E402
import test_reference_mode as tr  # noqa: E402
from pccomfy import bridge, config as cfgmod, inventory, models  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = DATA / "style-pilot"
SEED = 1234
MODELS = ("flux3", "qwen", "flux2", "fibo")    # flux3 + qwen: the pilot (7a); flux2 + fibo: round 7b (user 10.11.)
DEFAULT_MODELS = ("flux2", "fibo")             # the round now due; the pilot ran with --models flux3 qwen
SECS = {"flux3": 30, "qwen": 30, "flux2": 45, "fibo": 70}   # rough seconds per picture for the plan (pilot: about 30 s)
PHOTOS = ("03_", "05_", "11_")                 # father with child, kid with goats on a meadow, construction site
SKETCHES = ("house.jpg", "hyenas.jpg", "Landscape-Drawing.jpg")
SKETCH_NAMES = {"house": "house.jpg", "hyenas": "hyenas.jpg", "landscape": "Landscape-Drawing.jpg"}  # --sketches

# The 11 styles of the pilot (user 10.11.), the look as the plugin stores it (tools/styles-looks.json)
LOOKS = {
    "Studio portrait": "a professional studio portrait photograph with soft key light, a seamless grey backdrop and "
                       "natural skin texture",
    "Stock photo (lifestyle)": "a bright lifestyle stock photograph with soft natural window light, warm natural tones "
                               "and a candid feel",
    "Studio product photo": "a clean commercial studio product photograph on a seamless white background with soft "
                            "diffused light and gentle shadows",
    "Vintage black-and-white photo": "a vintage black-and-white film photograph with visible grain, soft contrast and "
                                     "slightly faded tones",
    "Watercolor": "a watercolor painting with soft washes, gentle colour bleeds and visible paper texture",
    "Oil painting": "an oil painting with visible brushstrokes, rich colours and canvas texture",
    "Anime": "a modern anime illustration with clean line art, cel shading and vivid colours",
    "Pixel art": "16-bit pixel art with a limited colour palette and crisp square pixels",
    "Pencil drawing": "a detailed graphite pencil drawing with fine hatching and soft shading on white paper",
    "Animated film": "a still from a classic hand-drawn animated film with clean outlines, soft cel shading and warm colours",
    "3D render": "a stylized 3D render with soft global illumination, smooth materials and gentle depth of field",
}
EDIT_FRAME = "Transform this image into {look}. Keep the composition, the subjects and their positions."
SKETCH_FRAME = "Turn this sketch of {subject} into {look}. Keep the composition and the shapes of the drawing."
SKETCH_FIXED = {"Animated film": models.SKETCH_ILLUSTRATION}        # tested word for word (sketch rounds 3 and 3 b)

# Part C: two prompts per own style (tools/styles-own.json), fitting what the style is for
T2I_PROMPTS = {
    "Studio portrait": ("a man in his fifties with a grey beard", "a young woman with curly red hair"),
    "Business headshot": ("a woman in her forties, a team leader", "a young man, a software developer"),
    "Stock photo, lifestyle": ("a couple cooking together in a kitchen", "a woman reading a book on a sofa"),
    "Stock photo, office team": ("three colleagues discussing a project", "a team meeting at a whiteboard"),
    "Product photo, colour backdrop": ("a ceramic coffee mug", "a pair of wireless headphones"),
    "Product photo, lifestyle setting": ("a glass bottle of olive oil", "a leather wallet"),
    "Food photography": ("a bowl of ramen", "a slice of blueberry cheesecake"),
}
T2I_SIZE = (1024, 1024)                       # the empty canvas of part C (square, 1 MP)

FAULTS = (
    ("1", "style", "Stil nicht getroffen"),
    ("2", "content", "Inhalt verändert (Personen, Gesicht, Anzahl, Pose, Motiv)"),
    ("3", "layout", "Aufbau verschoben oder beschnitten"),
    ("4", "sketch", "bleibt Skizze / Linien übrig"),
    ("5", "artifact", "Bildfehler (Hände, Text, Verzerrung)"),
    ("6", "soft", "unscharf oder matschig"),
)
GOOD, BAD = "gut", "schlecht"


def own_styles() -> dict:
    data = json.loads((ROOT / "tools" / "styles-own.json").read_text(encoding="utf-8"))
    return {s["name"]: s["text"] for g in data["groups"] for s in g["styles"]}


def sketch_sources(files=SKETCHES) -> list:
    """The sketches of round 3 (all three or the --sketches choice) with the subject typed there."""
    runs = sorted(p for p in (DATA / "sketch-test").glob("round3-2*") if (p / "key.json").exists())
    if not runs:
        sys.exit("No folder data\\sketch-test\\round3-* (the sketches of round 3)")
    key = json.load(open(runs[-1] / "key.json", encoding="utf-8"))["items"]
    out = {}
    for it in key.values():
        if it["file"] in files and it["file"] not in out:
            out[it["file"]] = {"src": runs[-1] / "eingabe" / it["input"], "file": it["file"], "desc": it["desc"].strip()}
    missing = [f for f in files if f not in out]
    if missing:
        sys.exit(f"Sketches not in {runs[-1]}: {missing}")
    return [out[f] for f in files]


def photo_sources(folder) -> list:
    if not folder:
        sys.exit("--photos <folder> is needed (the 2 MP photos, see the memory testbilder-orte)")
    d = Path(folder)
    out = []
    for prefix in PHOTOS:
        hit = sorted(d.glob(prefix + "*"))
        if not hit:
            sys.exit(f"No photo {prefix}* in {d}")
        out.append({"src": hit[0], "file": hit[0].name, "desc": hit[0].stem.split("_", 1)[-1].replace("-", " ")})
    return out


def text_of(part: str, style: str, subject: str = "") -> str:
    if part == "A":
        return EDIT_FRAME.format(look=LOOKS[style])
    if part == "B":
        fixed = SKETCH_FIXED.get(style)
        return fixed.replace(models.SKETCH_MARK, subject) if fixed else SKETCH_FRAME.format(subject=subject, look=LOOKS[style])
    return subject + "\n" + own_styles()[style]          # C: as the Styles button adds it


def keep(half: bool, other: bool, k: int) -> bool:
    """One cell of parts A and B, k = style index + source index + model index: the full round keeps all, --half the even
    ones, --other-half the odd ones (round 7b ran --half; the two halves together are the full round, without overlap)."""
    return (k % 2 == 1) if other else (not half or k % 2 == 0)


def jobs(a) -> list:
    """(part, model, style, source) in run order: part by part, model by model (fewer model loads)."""
    out = []
    photos = photo_sources(a.photos) if "A" in a.part else []
    sketches = sketch_sources(tuple(SKETCH_NAMES[n] for n in a.sketches)) if "B" in a.part else []
    half = getattr(a, "half", False)
    other = getattr(a, "other_half", False)       # --other-half: exactly the cells --half leaves out
    for part in a.part:
        for m, mk in enumerate(a.models):
            srcs = photos if part == "A" else sketches
            if part in ("A", "B"):
                # --half (round 7b, user 10.11.): a sample, every style at least once per model and part; the models
                # take complementary halves, so together every style x source pair runs once
                out += [(part, mk, st, s) for i, st in enumerate(LOOKS) for j, s in enumerate(srcs)
                        if keep(half, other, i + j + m)]
            else:
                out += [(part, mk, st, {"src": None, "file": "", "desc": p}) for st in T2I_PROMPTS for p in T2I_PROMPTS[st]]
    return out


def cmd_plan(a):
    js = jobs(a)
    for part in a.part:
        sub = [j for j in js if j[0] == part]
        print(f"Part {part}: {len(sub)} pictures")
        for _, mk, st, s in sub[: len(sub) // len(a.models)][:: max(1, len(sub) // len(a.models) // 4)]:
            print(f"   {mk} {st} {s['file'] or ''}: {text_of(part, st, s['desc'])[:150]!r}")
    secs = sum(SECS.get(mk, 45) for _, mk, _, _ in js)
    print(f"\n{len(js)} pictures, about {secs / 3600:.1f} h (rough guess per picture: "
          + ", ".join(f"{mk} {SECS.get(mk, 45)} s" for mk in a.models) + ")")


MODE = {"A": "edit", "B": "sketch", "C": "txt2img"}


def window_request(app, part: str, mk: str, text: str):
    """The Request the window sends in this tab with the model's start settings (saved pages ignored), seed 1234."""
    app.v_model.set(mk)
    app.v_mode.set(MODE[part])
    app._factory = True
    try:
        app._on_model()
        app._on_mode()
    finally:
        app._factory = False
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", text)
    req = app._request()
    req.params = replace(req.params, seed=SEED)
    return req


def run_one(comfy, req, pic: Image.Image, exch: Path):
    """One run as the plugin makes it: a document with the picture as its only layer (part C: an empty white canvas)."""
    tr.W, tr.H = pic.size
    pc = tr.FakePC(exch)
    pc.docs.append(tr.Doc("photo.png", [{"id": 1, "img": pic.convert("RGBA"), "visible": True, "name": "Background"}]))
    b = bridge.Bridge(pc, comfy, exch)
    res = b.run(req)
    return tr.FakePC.composite(pc.docs[0]).convert("RGB"), res, b


def free_memory(comfy) -> None:
    try:
        comfy._json("/free", {"unload_models": True, "free_memory": True})
    except Exception as e:
        print(f"   (free memory failed: {type(e).__name__}: {e})", flush=True)


def _prompt_in(graph: dict, text: str) -> bool:
    words = [w for w in text.replace("\n", " ").split() if len(w) > 4][:6]
    blob = json.dumps(graph, ensure_ascii=False)
    return all(w in blob for w in words)


def input_names(items: dict, folder: Path) -> dict:
    """Source file -> input name already used in this round (key.json and the files in eingabe\\), so a run with
    --into gives new sources new names instead of overwriting the inputs of the earlier part (10.11.: part B
    overwrote the photos of part A, the rating window showed a sketch beside a photo result)."""
    names = {it["source"]: it["input"] for it in items.values() if it.get("input")}
    for p in folder.glob("*.png") if folder.exists() else ():
        if p.name not in names.values():
            names[f"<unknown {p.name}>"] = p.name
    return names


def assign_inputs(js: list, items: dict, folder: Path) -> dict:
    """Input name per source of these jobs: the old name if the source ran before, else the next free number."""
    names = input_names(items, folder)
    used = set(names.values())
    for _, _, _, s in js:
        if s["src"] is not None and s["file"] not in names:
            n = len(used) + 1
            while f"{n}.png" in used:
                n += 1
            names[s["file"]] = f"{n}.png"
            used.add(names[s["file"]])
    return names


def cmd_run(a):
    js = jobs(a)
    if a.dry:                    # a dry run works in its own folder and deletes it at the end, never the --into one
        out = BASE / ("dry-" + time.strftime("%Y%m%d-%H%M%S"))
    else:
        out = Path(a.into) if a.into else BASE / time.strftime("%Y%m%d-%H%M%S")
    for sub in ("bilder", "eingabe", "xch"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    kf = out / "key.json"
    old = json.load(open(kf, encoding="utf-8")) if kf.exists() else {}
    pics, names = {}, assign_inputs(js, old.get("items", {}), out / "eingabe")
    for _, _, _, s in js:
        if s["src"] is not None and s["file"] not in pics:
            im = Image.open(s["src"]).convert("RGB")
            im.save(out / "eingabe" / names[s["file"]])
            pics[s["file"]] = im
    blank = Image.new("RGB", T2I_SIZE, "white")
    key = old.get("items", {})
    order = list(old.get("order", []))

    base = len(order)                               # pictures of earlier runs keep their place

    def write_key():
        # blind: all pictures of this run mixed again on every write, after the old ones (10.11.: shuffling only
        # the newest picture left the run order, flux3 then qwen, style by style)
        new = sorted(f for f in key if f not in order[:base])
        random.Random(1011).shuffle(new)
        order[base:] = new
        json.dump({"items": key, "order": order, "seed": SEED, "looks": LOOKS, "edit_frame": EDIT_FRAME,
                   "sketch_frame": SKETCH_FRAME, "t2i_prompts": T2I_PROMPTS},
                  open(kf, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    if a.dry:
        comfy = tr.FakeComfy()
    else:
        url = a.url or cfgmod.load()["comfyui"]["url"]
        host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
        try:
            socket.create_connection((host, port), timeout=2).close()
        except OSError:
            sys.exit(f"ComfyUI is not running ({url}). Start it first.")
        comfy = ComfyUI(url)
        inv = inventory.fetch(comfy, cfgmod.model_map())
        for mk in a.models:
            if inv.tab_status(mk).state != "ready":
                print(f"WARNING: {mk}: not all its files are there", flush=True)
    app = live_sketch.make_app("http://127.0.0.1:1" if a.dry else (a.url or cfgmod.load()["comfyui"]["url"]))
    n, t_start, failed = 0, time.time(), 0
    for part, mk, st, s in js:
        n += 1
        if any(r["part"] == part and r["model_key"] == mk and r["style"] == st and r["source"] == (s["file"] or s["desc"])
               for r in key.values()):
            continue
        text = text_of(part, st, s["desc"])
        req = window_request(app, part, mk, text)
        pic = pics[s["file"]] if s["src"] is not None else blank
        t0 = time.time()
        try:
            im, res, b = run_one(comfy, req, pic, out / "xch")
        except Exception as e:            # one failing run must not stop the round
            failed += 1
            print(f"{n}/{len(js)} {part} {mk} {st} {s['file'] or s['desc']}: FAILED {type(e).__name__}: {e}", flush=True)
            continue
        if a.dry:
            ok = _prompt_in(comfy.graphs[-1], text)
            print(f"{n}/{len(js)} {part} {mk} {st} {s['file'] or s['desc']}: {Path(req.workflow or '').name}, "
                  f"text in graph: {'yes' if ok else 'NO'}", flush=True)
            failed += not ok
            continue
        fid = f"{len(key) + 1:04d}"
        im.save(out / "bilder" / f"{fid}.png")
        key[fid] = {"part": part, "model": models.BY_KEY[mk].label, "model_key": mk, "style": st,
                    "source": s["file"] or s["desc"], "input": names.get(s["file"], ""), "desc": s["desc"],
                    "text": text, "caption": res.get("vgl", ""), "seed": SEED, "secs": round(time.time() - t0, 1)}
        write_key()
        if a.free:
            free_memory(comfy)
    if not a.dry:
        write_key()
    else:
        shutil.rmtree(out, ignore_errors=True)       # a dry run leaves no folder behind
    app.root.destroy()
    print(f"\n{'DRY RUN' if a.dry else 'DONE'} in {(time.time() - t_start) / 60:.1f} min: "
          f"{len(js) if a.dry else len(key)} pictures, {failed} failed"
          + ("" if a.dry else f", in {out}\nNext: python tests\\live_style_round.py rate"), flush=True)
    return failed


def latest(folder):
    if folder:
        return Path(folder)
    runs = sorted(p for p in BASE.iterdir() if (p / "key.json").exists()) if BASE.exists() else []
    if not runs:
        sys.exit(f"No round in {BASE}")
    return runs[-1]


PART_NAME = {"A": "Edit canvas", "B": "Sketch to image", "C": "Text to image"}


def cmd_rate(a):
    """One result at a time beside its input (part C: the prompt instead); the model stays hidden, the style is shown.
    Keys: G good, S bad, 1 to 6 faults (also on good), arrows."""
    import tkinter as tk
    from PIL import ImageTk
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    items, order = key["items"], key["order"]
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    root = tk.Tk()
    root.title("Stil-Pilot bewerten (blind)")
    root.configure(bg="#282828")
    st = {"i": next((k for k, f in enumerate(order) if not data.get(f, {}).get("wahl")), 0), "loading": False}
    faults = {code: tk.BooleanVar() for _, code, _ in FAULTS}
    choice, note = tk.StringVar(), tk.StringVar()
    top = tk.Label(root, bg="#282828", fg="#e6e6e6", font=("Segoe UI", 12, "bold"), wraplength=1800, justify="left")
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
    ff = tk.Frame(root, bg="#282828")
    ff.pack(pady=2)
    tk.Label(ff, text="Fehler ankreuzen (Tasten 1–6, auch bei „gut“ möglich):", bg="#282828", fg="#cfcfcf",
             font=("Segoe UI", 10)).grid(row=0, column=0, columnspan=3, sticky="w")
    for k, (digit, code, text) in enumerate(FAULTS):
        tk.Checkbutton(ff, text=f"{digit}  {text}", variable=faults[code], bg="#282828", fg="#f0c674", selectcolor="#535353",
                       activebackground="#282828", activeforeground="#ffffff", font=("Segoe UI", 10),
                       command=lambda: save()).grid(row=1 + k // 3, column=k % 3, sticky="w", padx=8)
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

    def placeholder(text, side_px):
        im = Image.new("RGB", (side_px, side_px // 2), "#3a3a3a")
        ImageDraw.Draw(im).multiline_text((16, 16), text, fill="#e6e6e6", spacing=6)
        return im

    def show():
        fid = order[st["i"]]
        it = items[fid]
        top.configure(text=f"Bild {st['i'] + 1}/{len(order)}  ·  {PART_NAME[it['part']]}  ·  Stil: {it['style']}  ·  {it['desc']}")
        side_px = min((root.winfo_screenwidth() - 60) // 2, root.winfo_screenheight() - 330)
        left = (Image.open(out / "eingabe" / it["input"]).convert("RGB") if it["input"]
                else placeholder("Text to image\n\nPrompt: " + it["desc"] + "\nStil: " + it["style"], side_px))
        st["photos"] = []
        for lbl, im in zip(pics, (left, Image.open(out / "bilder" / f"{fid}.png").convert("RGB"))):
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
        data[fid] = {"wahl": choice.get(), "notiz": note.get().strip(),
                     "fehler": [code for _, code, _ in FAULTS if faults[code].get()]}
        fout.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        count()

    def go(step):
        st["i"] = max(0, min(len(order) - 1, st["i"] + step))
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
    """Good and fault-free good (memory: he often calls a picture with a fault good) per part, model, style."""
    items = key["items"]
    rows: dict = {}
    fault_rows: dict = {}
    for fid, it in items.items():
        rec = data.get(fid, {})
        if not rec.get("wahl"):
            continue
        good = rec["wahl"] == GOOD
        clean = good and not rec.get("fehler")
        for k in (("Teil", PART_NAME[it["part"]]), ("Modell", it["model"]),
                  ("Teil × Modell", f"{PART_NAME[it['part']]} · {it['model']}"),
                  ("Stil (A und B)", it["style"]) if it["part"] != "C" else ("Stil (C)", it["style"]),
                  ("Stil × Teil × Modell", f"{it['style']} · {it['part']} · {it['model']}")):
            r = rows.setdefault(k, [0, 0, 0])
            r[0] += 1
            r[1] += good
            r[2] += clean
        for f in rec.get("fehler", []):
            fault_rows[f] = fault_rows.get(f, 0) + 1
    rated = sum(1 for f in items if data.get(f, {}).get("wahl"))
    lines = [f"# Stil-Pilot {key.get('folder', '')}".rstrip(), "", f"Bewertet: {rated} von {len(items)} (blind, Seed {SEED})", ""]
    for kind in ("Teil", "Modell", "Teil × Modell", "Stil (A und B)", "Stil (C)", "Stil × Teil × Modell"):
        sub = sorted((name, r) for (k, name), r in rows.items() if k == kind)
        if not sub:
            continue
        lines += [f"## Je {kind}", "", f"| {kind} | bewertet | gut | fehlerfrei gut |", "|---|---|---|---|"]
        lines += [f"| {name} | {r[0]} | {r[1]} | {r[2]} |" for name, r in sub] + [""]
    if fault_rows:
        names = {c: t for _, c, t in FAULTS}
        lines += ["## Fehler (auch bei „gut“)", "", "| Fehler | Anzahl |", "|---|---|"]
        lines += [f"| {names.get(c, c)} | {n} |" for c, n in sorted(fault_rows.items(), key=lambda x: -x[1])] + [""]
    notes = [(items[f], r["notiz"]) for f, r in data.items() if r.get("notiz") and f in items]
    if notes:
        lines += ["## Notizen", ""] + [f"- {it['part']} {it['model']} {it['style']} ({it['desc']}): {n}" for it, n in notes]
    return "\n".join(lines) + "\n"


def cmd_summary(a):
    out = latest(a.folder)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    key["folder"] = out.name
    data = json.loads((out / "bewertung.json").read_text(encoding="utf-8")) if (out / "bewertung.json").exists() else {}
    text = summarize(key, data)
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        r = sub.add_parser(name)
        r.add_argument("--photos", help="the folder of the 2 MP photos (03_, 05_, 11_)")
        r.add_argument("--part", nargs="+", default=["A", "B", "C"], choices=["A", "B", "C"])
        r.add_argument("--models", nargs="+", default=list(DEFAULT_MODELS), choices=list(MODELS))
        r.add_argument("--sketches", nargs="+", default=list(SKETCH_NAMES), choices=list(SKETCH_NAMES),
                       help="the sketches of part B (round 7b, user 10.11.: hyenas landscape)")
        r.add_argument("--half", action="store_true",
                       help="parts A and B as a sample: half the pictures, every style once per model at least")
        r.add_argument("--other-half", action="store_true",
                       help="parts A and B: exactly the pictures --half leaves out (half + other-half = the full round)")
        r.add_argument("--url", help="the ComfyUI address (default: config.toml of PCCOMFY_HOME), e.g. http://<ip of PC C>:8188")
        if name == "run":
            r.add_argument("--into", help="resume in this folder")
            r.add_argument("--dry", action="store_true", help="the whole bridge against a fake ComfyUI, no GPU")
            r.add_argument("--free", action="store_true", help="ask ComfyUI to free memory after every run")
    for name in ("rate", "summary"):
        s = sub.add_parser(name)
        s.add_argument("folder", nargs="?", help="the round's folder (default: the newest)")
    a = ap.parse_args()
    if getattr(a, "half", False) and getattr(a, "other_half", False):
        ap.error("--half and --other-half exclude each other")
    if a.cmd in ("plan", "run") and "A" not in a.part:
        a.photos = a.photos or ""
    res = {"plan": cmd_plan, "run": cmd_run, "rate": cmd_rate, "summary": cmd_summary}[a.cmd](a)
    sys.exit(1 if a.cmd == "run" and res else 0)


if __name__ == "__main__":
    main()
