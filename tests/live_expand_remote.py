r"""Manual check (not part of run_all.py): the Expand round with the four models that have Expand (user 5.11.2026).

The test runs on the ComfyUI of another PC (PC C), started from this PC: the address comes from config.toml of PCCOMFY_HOME
(see tests/live_remote_one.py). Nothing is changed on the other PC; every case only queues one job.

Pictures: the photos in <folder> (not the sub-folder "archiv"), scaled to 2 MP, in the sub-folder "2MP"; the same photos with
the right 30 % cut off, in "2MP-beschnitten". Two kinds of Expand per photo:

    A  the 2 MP photo, 20 % of its width to the right and 20 % of its height to the bottom at the same time
    B  the cut photo (70 % of the width), 20 % of ITS width to the right (the cut-off part is "painted back", but 14 % smaller)
    C  only Flux 2 and Qwen: the 2 MP photo, 50 % of its width to the right. In B their work area stays under the model's own ~1 MP,
       so the cap makes no difference there; C is big enough for 1.0 MP against 2.0 MP to give different pictures (measured 5.11.)

Every kind runs with "Original size, up to" 1.0 MP and 2.0 MP, with Flux 3, Flux 2, Qwen Image 2.1 and Fibo 2.0 (each model with its own
Expand start values, empty prompt, one seed). The run goes through the plugin's real bridge (Bridge.run) against a small
PhotoCraft simulator (tests/test_reference_mode.py): crop around the new area, scale, model, layer mask, composite. Cases whose
graph and uploaded pictures are identical (the cap does not matter when the work area is smaller than the cap) are run once; the
result counts for both. The generation time of every run is written down.

    python tests\live_expand_remote.py prepare [--folder <folder>]      scale and cut the photos (writes fotos.json)
    python tests\live_expand_remote.py dry [--folder <folder>]          build all graphs without ComfyUI, count the distinct ones
    python tests\live_expand_remote.py run [--models flux3 ...] [--into <round>]   the real run (model after model, resumable)
    python tests\live_expand_remote.py rate [pairs|models] [round]     blind rating (pairs: 1.0 against 2.0 MP; models: the four side by side)
    python tests\live_expand_remote.py summary [round]                 the result tables and times (ergebnis.md)

Output: <PCCOMFY_HOME>/expand-remote/<round>/ (bilder/<token>.png, records.json with times, bewertung.json)."""
import argparse
import copy
import hashlib
import io
import json
import os
import random
import re
import socket
import statistics
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image  # noqa: E402

import live_style_test as base  # noqa: E402
import test_reference_mode as T  # noqa: E402  (the PhotoCraft simulator and a stand-in for ComfyUI)
from pccomfy import config as cfgmod, inventory, workflows  # noqa: E402
from pccomfy.bridge import Bridge  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

FOLDER = Path(os.environ.get("EXPAND_PHOTOS", "."))        # the folder with the photos: --folder or the variable EXPAND_PHOTOS
MODELS = ("flux3", "flux2", "qwen", "fibo")        # the models that have Expand (Krea 2 and MOSS are parked)
KINDS = ("A", "B", "C")
C_MODELS = ("flux2", "qwen")                        # kind C only for these (see above)
CAPS = (1.0, 2.0)                                   # "Original size, up to" in MP
SEED = 101
MP = 2.0e6
GROW = 0.20
GROW_C = 0.50
CUT = 0.30
BASE = cfgmod.CONFIG_DIR / "expand-remote"


def photos(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))


def slug(stem: str) -> str:
    return "-".join(re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-").split("-")[:3])


def cmd_prepare(a):
    folder = Path(a.folder)
    out_a, out_b = folder / "2MP", folder / "2MP-beschnitten"
    out_a.mkdir(exist_ok=True)
    out_b.mkdir(exist_ok=True)
    meta = []
    for k, p in enumerate(photos(folder), 1):
        with Image.open(p) as im:
            im = im.convert("RGB")
            f = (MP / (im.width * im.height)) ** 0.5
            small = im.resize((max(1, round(im.width * f)), max(1, round(im.height * f))), Image.LANCZOS)
        name = f"{k:02d}_{slug(p.stem)}.png"
        small.save(out_a / name)
        cut = small.crop((0, 0, round(small.width * (1 - CUT)), small.height))
        cut.save(out_b / name)
        meta.append({"id": f"{k:02d}", "file": name, "original": p.name, "size": list(small.size), "cut_size": list(cut.size)})
        print(f"{name}: {im.width}x{im.height} -> {small.width}x{small.height} ({small.width * small.height / 1e6:.2f} MP), "
              f"cut {cut.width}x{cut.height}")
    json.dump(meta, open(folder / "fotos.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\n{len(meta)} photos in {out_a} and {out_b}")


def canvas_for(kind: str, photo: Image.Image) -> Image.Image:
    """The picture as it lies in PhotoCraft after the canvas was made bigger: the margin is transparent."""
    w, h = photo.size
    cw, ch = {"A": (w + round(w * GROW), h + round(h * GROW)), "B": (w + round(w * GROW), h),
              "C": (w + round(w * GROW_C), h)}[kind]
    c = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    c.paste(photo.convert("RGBA"), (0, 0))
    return c


def expand_request(app, key: str):
    """The Request the window would send for Expand with this model's start values (saved pages ignored)."""
    app.v_model.set(key)
    app.v_mode.set("outpaint")
    app._factory = True
    try:
        app._on_model()
        app._on_mode()
    finally:
        app._factory = False
    app.t_prompt.delete("1.0", "end")
    return app._request(), app._model().label


class Recorder(T.FakeComfy):
    """Stands in for ComfyUI in the dry run: keeps the graph and a hash of every uploaded picture."""

    def upload_image(self, image, name):
        buf = io.BytesIO()
        image.convert("RGBA").save(buf, "PNG")
        self.uploads[name] = hashlib.sha256(buf.getvalue()).hexdigest()[:16] + f"_{image.width}x{image.height}"
        return name


def graph_key(graph: dict, uploads: dict) -> str:
    s = json.dumps(graph, sort_keys=True)
    for name, h in uploads.items():
        s = s.replace(name, "IMG:" + h)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def run_case(comfy, req0, folder: Path, entry: dict, kind: str, cap: float):
    """One Expand run through Bridge.run against the PhotoCraft simulator. Returns (composite, seconds, comfy)."""
    src = folder / ("2MP-beschnitten" if kind == "B" else "2MP") / entry["file"]
    with Image.open(src) as im:
        c = canvas_for(kind, im.convert("RGB"))
    T.W, T.H = c.size
    tmp = tempfile.mkdtemp(prefix="expand-remote-")
    pc = T.FakePC(tmp)
    pc.docs.append(T.Doc("scene.png", [{"id": 1, "img": c, "visible": True}], None))
    b = Bridge(pc, comfy, tmp)
    req = copy.deepcopy(req0)
    req.native, req.native_mp = True, float(cap)
    req.params = replace(req.params, prompt="", seed=SEED)
    t0 = time.time()
    b.run(req)
    secs = time.time() - t0
    return pc.composite(pc.doc), secs, c.size


def cases(meta):
    for m in MODELS:
        for e in meta:
            for kind in KINDS:
                if kind == "C" and m not in C_MODELS:
                    continue
                for cap in CAPS:
                    yield m, e, kind, cap


def cmd_dry(a):
    folder = Path(a.folder)
    meta = json.load(open(folder / "fotos.json", encoding="utf-8"))
    app = base.make_app("http://127.0.0.1:1")
    reqs = {m: expand_request(app, m) for m in MODELS}
    rows, t0 = [], time.time()
    for m, e, kind, cap in cases(meta):
        comfy = Recorder()
        _img, _s, csize = run_case(comfy, reqs[m][0], folder, e, kind, cap)
        assert len(comfy.graphs) == 1, (m, e["id"], kind, cap, len(comfy.graphs))
        rows.append({"model": m, "photo": e["id"], "kind": kind, "cap": cap, "canvas": list(csize),
                     "key": graph_key(comfy.graphs[0], comfy.uploads), "uploads": sorted(comfy.uploads.values())})
    print(f"{len(rows)} cases built in {time.time() - t0:.0f} s\n")
    total = {}
    print(f"{'model':8} {'cases':>6} {'distinct':>9}   photos where 1.0 and 2.0 MP give the same picture, per kind")
    for m in MODELS:
        rs = [r for r in rows if r["model"] == m]
        distinct = len({(r["key"]) for r in rs})
        total[m] = distinct
        same = "  ".join(f"{k} {sum(1 for p in {r['photo'] for r in rs} if len({r2['key'] for r2 in rs if r2['photo'] == p and r2['kind'] == k}) == 1)}/{len(meta)}"
                         for k in KINDS if any(r["kind"] == k for r in rs))
        print(f"{m:8} {len(rs):>6} {distinct:>9}   {same}")
    print(f"\ntotal {len(rows)} cases, {sum(total.values())} distinct runs ({len(rows) - sum(total.values())} duplicates skipped)")
    # a sanity check of the comparison: the same case built twice gives the same key
    m, e, kind, cap = next(iter(cases(meta)))
    k1, k2 = [graph_key(c.graphs[0], c.uploads) for c in (Recorder(), Recorder()) if run_case(c, reqs[m][0], folder, e, kind, cap)]
    print("same case twice -> same key:", k1 == k2)
    json.dump(rows, open(BASE.parent / "expand-remote-dry.json", "w", encoding="utf-8"), indent=1)
    app.root.destroy()


class Timed(ComfyUI):
    """The real ComfyUI client; remembers when the job was queued and when it was done (the generation time)."""
    t_queued = t_done = 0.0

    def queue(self, graph, preview=None):
        pid = super().queue(graph, preview)
        self.t_queued = time.time()
        return pid

    def wait(self, *a, **k):
        r = super().wait(*a, **k)
        self.t_done = time.time()
        return r


def case_keys(app_reqs, folder, meta, model):
    """[(entry, kind, cap, key, canvas)] for one model: every case built without ComfyUI to find the distinct ones."""
    rows = []
    for m, e, kind, cap in cases(meta):
        if m != model:
            continue
        rec = Recorder()
        _img, _s, csize = run_case(rec, app_reqs[m][0], folder, e, kind, cap)
        rows.append((e, kind, cap, graph_key(rec.graphs[0], rec.uploads), list(csize)))
    return rows


def cmd_run(a):
    folder = Path(a.folder)
    meta = json.load(open(folder / "fotos.json", encoding="utf-8"))
    url = cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    try:
        socket.create_connection((host, port), timeout=3).close()
    except OSError:
        sys.exit(f"ComfyUI does not answer ({url}).")
    out = Path(a.into) if a.into else BASE / time.strftime("%Y%m%d-%H%M%S")
    (out / "bilder").mkdir(parents=True, exist_ok=True)
    rfile = out / "records.json"
    records = json.load(open(rfile, encoding="utf-8")) if rfile.exists() else []
    comfy = Timed(url)
    inv = inventory.fetch(comfy, cfgmod.model_map())
    app = base.make_app(url)
    reqs = {m: expand_request(app, m) for m in a.models}
    print(f"ComfyUI: {url}\nRound: {out}\n", flush=True)
    t_start = time.time()
    for m in a.models:
        if inv.tab_status(m).state != "ready":
            print(f"SKIPPED {m}: its files are not all there", flush=True)
            continue
        rows = case_keys(reqs, folder, meta, m)
        first, done_keys = True, {r["key"]: r for r in records if r["model"] == m and r.get("token")}
        print(f"== {reqs[m][1]}: {len(rows)} cases, {len({r[3] for r in rows})} distinct runs", flush=True)
        for e, kind, cap, key, csize in rows:
            if any(r["model"] == m and r["photo"] == e["id"] and r["kind"] == kind and r["cap"] == cap for r in records):
                continue                                           # done in an earlier part of this round
            rec = {"model": m, "photo": e["id"], "kind": kind, "cap": cap, "key": key, "canvas": csize}
            if key in done_keys:                                   # the same graph and pictures: the same result, not run again
                rec.update(token=done_keys[key]["token"], same_as=done_keys[key]["token"])
            else:
                token = os.urandom(4).hex()
                t0 = time.time()
                try:
                    img, secs, _c = run_case(comfy, reqs[m][0], folder, e, kind, cap)
                    img.convert("RGB").save(out / "bilder" / f"{token}.png")
                    rec.update(token=token, seconds=round(secs, 1), gen_seconds=round(comfy.t_done - comfy.t_queued, 1),
                               first_of_model=first, got=list(img.size))
                except Exception as ex:                            # one broken case must not stop the round
                    rec.update(error=f"{type(ex).__name__}: {ex}"[:300], seconds=round(time.time() - t0, 1))
                first = False
                if rec.get("token"):
                    done_keys[key] = rec
            records.append(rec)
            json.dump(records, open(rfile, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            note = (f"{rec['gen_seconds']} s (total {rec['seconds']} s)" if "gen_seconds" in rec
                    else ("same as an earlier run" if rec.get("same_as") else f"ERROR {rec.get('error')}"))
            print(f"{m} {e['id']} {kind} {cap}: {note}", flush=True)
    print(f"\nDONE in {(time.time() - t_start) / 60:.1f} min -> {out}\nNext: python tests\\live_expand_remote.py rate pairs", flush=True)
    app.root.destroy()


def latest(folder):
    if folder:
        return Path(folder)
    runs = sorted(p for p in BASE.iterdir() if (p / "records.json").exists()) if BASE.exists() else []
    if not runs:
        sys.exit(f"No round in {BASE}")
    return runs[-1]


def rating_items(records, mode):
    """The blind items. pairs: one per (model, photo, kind) whose 1.0 and 2.0 MP pictures differ: two pictures. models: one per
    (photo, kind): the 2.0 MP result of every model that has one. The order inside an item is shuffled (fixed seed per item)."""
    by = {}
    for r in records:
        if r.get("token"):
            by.setdefault((r["model"], r["photo"], r["kind"]), {})[r["cap"]] = r
    items = []
    if mode == "pairs":
        for (m, ph, kind), caps in sorted(by.items()):
            if 1.0 in caps and 2.0 in caps and caps[1.0]["token"] != caps[2.0]["token"]:
                items.append({"id": f"pair|{m}|{ph}|{kind}", "tokens": [caps[1.0]["token"], caps[2.0]["token"]]})
    else:
        groups = {}
        for (m, ph, kind), caps in by.items():
            if 2.0 in caps:
                groups.setdefault((ph, kind), []).append(caps[2.0]["token"])
        for (ph, kind), toks in sorted(groups.items()):
            if len(toks) > 1:
                items.append({"id": f"models|{ph}|{kind}", "tokens": toks})
    for it in items:
        random.Random(it["id"]).shuffle(it["tokens"])
    random.Random(7).shuffle(items)
    return items


def cmd_rate(a):
    import tkinter as tk
    from PIL import ImageTk
    out = latest(a.round)
    records = json.load(open(out / "records.json", encoding="utf-8"))
    items = rating_items(records, a.mode)
    if not items:
        sys.exit("Nothing to rate yet in this mode.")
    fout = out / "bewertung.json"
    data = json.loads(fout.read_text(encoding="utf-8")) if fout.exists() else {}
    root = tk.Tk()
    root.title(f"Expand-Test bewerten (blind, {a.mode})")
    root.configure(bg="#282828")
    st = {"i": next((k for k, it in enumerate(items) if it["id"] not in data), 0), "photos": []}
    head = tk.Label(root, bg="#282828", fg="#e6e6e6", font=("Segoe UI", 12, "bold"))
    head.pack(fill="x", pady=(8, 2))
    row = tk.Frame(root, bg="#282828")
    row.pack(padx=8)
    btns = tk.Frame(root, bg="#282828")
    btns.pack(pady=6)
    status = tk.Label(root, bg="#282828", fg="#9a9a9a")
    status.pack()

    multi = a.mode == "models"
    st.update(bad=[], good=[])
    note = tk.StringVar()

    def save(choice=None):
        """pairs: choice = index / "equal" / "none". models: choice None = the ticked "Gut" boxes (several allowed).
        Both: the "Schlecht" ticks and the note are saved with the case."""
        it = items[st["i"]]
        ent = {"tokens": it["tokens"], "bad": [k for k, v in enumerate(st["bad"]) if v.get()], "note": note.get().strip()}
        if choice is None:
            good = [k for k, v in enumerate(st["good"]) if v.get()]
            if not good:
                status.configure(text="Nichts als gut angehakt: Gut ankreuzen, oder 'Gleich gut' / 'Alle schlecht' wählen.")
                return
            ent["good"] = good
            ent["best"] = good[0] if len(good) == 1 else "multi"
        else:
            ent["best"] = choice
        data[it["id"]] = ent
        fout.write_text(json.dumps(data, indent=1), encoding="utf-8")
        go(1)

    def go(step):
        st["i"] = max(0, min(len(items) - 1, st["i"] + step))
        show()

    def show():
        it = items[st["i"]]
        for w in row.winfo_children():
            w.destroy()
        for w in btns.winfo_children():
            w.destroy()
        n = len(it["tokens"])
        pw, ph = (root.winfo_screenwidth() - 60) // n - 10, root.winfo_screenheight() - 230
        st["photos"] = []
        old = data.get(it["id"], {})
        st["bad"], st["good"] = [], []
        note.set(old.get("note", ""))
        for k, tok in enumerate(it["tokens"]):
            im = Image.open(out / "bilder" / f"{tok}.png").convert("RGB")
            im.thumbnail((pw, ph))
            ph_img = ImageTk.PhotoImage(im)
            st["photos"].append(ph_img)
            cell = tk.Frame(row, bg="#282828")
            cell.grid(row=0, column=k, padx=5)
            lab = tk.Label(cell, image=ph_img, bg="#282828", cursor="hand2")
            lab.pack()
            lab.bind("<Button-1>", lambda e, t=tok: os.startfile(out / "bilder" / f"{t}.png"))     # full size in the viewer
            bv = tk.BooleanVar(value=k in old.get("bad", []))
            st["bad"].append(bv)
            opt = dict(bg="#282828", fg="#e6e6e6", selectcolor="#444444", activebackground="#282828", activeforeground="#ffffff")
            tk.Checkbutton(cell, text=f"Schlecht  (Alt+{k + 1})", variable=bv, **opt).pack(side="left", padx=6)
            if multi:
                gv = tk.BooleanVar(value=k in old.get("good", []) or old.get("best") == k)
                st["good"].append(gv)
                tk.Checkbutton(cell, text=f"Gut  ({k + 1})", variable=gv, **opt).pack(side="left", padx=6)
        if multi:
            tk.Button(btns, text="Speichern und weiter (Enter)", command=lambda: save(), width=26).grid(row=0, column=0, columnspan=2, padx=10)
        else:
            for k in range(n):
                tk.Button(btns, text=f"Das ist besser ({k + 1})", command=lambda k=k: save(k), width=22).grid(row=0, column=k, padx=10)
        tk.Button(btns, text="Gleich gut (G)", command=lambda: save("equal")).grid(row=1, column=0, pady=6)
        tk.Button(btns, text="Alle schlecht (S)", command=lambda: save("none")).grid(row=1, column=1, pady=6)
        tk.Button(btns, text="← Zurück", command=lambda: go(-1)).grid(row=1, column=2, pady=6)
        head.configure(text=f"Fall {st['i'] + 1}/{len(items)}   (bewertet: {sum(1 for i in items if i['id'] in data)})")
        cur = data.get(it["id"], {}).get("best")
        status.configure(text=f"gespeichert in {fout}" + (f"   ·   bisher gewählt: {cur}" if cur is not None else "")
                         + "   ·   Klick auf ein Bild öffnet es in voller Größe")

    nrow = tk.Frame(root, bg="#282828")
    nrow.pack(before=btns, pady=(4, 0))
    tk.Label(nrow, text="Notiz:", bg="#282828", fg="#e6e6e6").pack(side="left")
    nent = tk.Entry(nrow, textvariable=note, width=90)
    nent.pack(side="left", padx=6)

    def typing():
        return root.focus_get() is nent       # keys 1-4, G, S and the arrow only work outside the note field

    def key_choice(k):
        if typing() or k >= len(items[st["i"]]["tokens"]):
            return
        if multi:
            st["good"][k].set(not st["good"][k].get())
        else:
            save(k)

    def key_bad(k):
        if k < len(st["bad"]):
            st["bad"][k].set(not st["bad"][k].get())

    for k in range(1, 5):
        root.bind(str(k), lambda e, k=k: key_choice(k - 1))
        root.bind(f"<Alt-Key-{k}>", lambda e, k=k: key_bad(k - 1))
    root.bind("g", lambda e: None if typing() else save("equal"))
    root.bind("s", lambda e: None if typing() else save("none"))
    root.bind("<Return>", lambda e: save() if multi and not typing() else None)
    root.bind("<Left>", lambda e: None if typing() else go(-1))
    show()
    root.state("zoomed")
    root.mainloop()


def cmd_summary(a):
    out = latest(a.round)
    records = json.load(open(out / "records.json", encoding="utf-8"))
    bfile = out / "bewertung.json"
    data = json.loads(bfile.read_text(encoding="utf-8")) if bfile.exists() else {}
    who = {r["token"]: r for r in records if r.get("token")}
    lines = [f"# Expand-Test auf PC C, Auswertung ({out.name})", ""]
    lines += ["## Paare: 1,0 gegen 2,0 MP (je Modell und Art)", "",
              "| Modell | Art | Fälle | 2 MP besser | 1 MP besser | gleich | alle schlecht |", "|---|---|---|---|---|---|---|"]
    stats = {}
    for iid, v in data.items():
        if not iid.startswith("pair|"):
            continue
        _p, m, _ph, kind = iid.split("|")
        s = stats.setdefault((m, kind), [0, 0, 0, 0, 0])
        s[0] += 1
        b = v["best"]
        if b in ("equal", "none"):
            s[3 if b == "equal" else 4] += 1
        else:
            s[1 if who[v["tokens"][b]]["cap"] == 2.0 else 2] += 1
    for (m, kind), s in sorted(stats.items()):
        lines.append(f"| {m} | {kind} | {s[0]} | {s[1]} | {s[2]} | {s[3]} | {s[4]} |")
    tot = [sum(s[i] for s in stats.values()) for i in range(5)]
    lines += [f"| **zusammen** | | {tot[0]} | {tot[1]} | {tot[2]} | {tot[3]} | {tot[4]} |", ""]
    lines += ["## Modelle nebeneinander (je Art, das 2,0-MP-Ergebnis; bei Mehrfachwahl zählt jedes gewählte Modell)", "",
              "| Art | Fälle | " + " | ".join(MODELS) + " | gleich | alle schlecht |", "|---|---|" + "---|" * (len(MODELS) + 2)]
    wins = {}
    for iid, v in data.items():
        if not iid.startswith("models|"):
            continue
        _p, _ph, kind = iid.split("|")
        s = wins.setdefault(kind, {"n": 0, "equal": 0, "none": 0, **{m: 0 for m in MODELS}})
        s["n"] += 1
        b = v["best"]
        if "good" in v:
            for g in v["good"]:
                s[who[v["tokens"][g]]["model"]] += 1
        elif b in ("equal", "none"):
            s[b] += 1
        else:
            s[who[v["tokens"][b]]["model"]] += 1
    for kind, s in sorted(wins.items()):
        lines.append(f"| {kind} | {s['n']} | " + " | ".join(str(s[m]) for m in MODELS) + f" | {s['equal']} | {s['none']} |")
    bad = {}
    for iid, v in data.items():
        for k in v.get("bad", []):
            r = who[v["tokens"][k]]
            bad.setdefault((r["model"], r["kind"], r["cap"]), []).append(r["photo"])
    lines += ["", "## Als schlecht markiert (Haken), je Modell, Art und Grenze", "",
              "| Modell | Art | Grenze | Anzahl | Fotos |", "|---|---|---|---|---|"]
    for (m, kind, cap), phs in sorted(bad.items()):
        lines.append(f"| {m} | {kind} | {cap} | {len(phs)} | {', '.join(sorted(phs))} |")
    notes = [(iid, v["note"]) for iid, v in sorted(data.items()) if v.get("note")]
    if notes:
        lines += ["", "## Notizen", ""] + [f"- {iid}: {n}" for iid, n in notes]
    lines += ["", "## Generationszeit (Median in Sekunden; nur Läufe, die wirklich liefen)", "",
              "| Modell | Grenze 1,0 MP | Grenze 2,0 MP | Läufe |", "|---|---|---|---|"]
    for m in MODELS:
        rs = [r for r in records if r["model"] == m and "gen_seconds" in r]
        med = {c: (f"{statistics.median(r['gen_seconds'] for r in rs if r['cap'] == c):.0f}"
                   if any(r["cap"] == c for r in rs) else "-") for c in CAPS}
        lines.append(f"| {m} | {med[1.0]} | {med[2.0]} | {len(rs)} |")
    err = [r for r in records if r.get("error")]
    lines += ["", f"Fehlerfälle: {len(err)}" + "".join(f"\n- {r['model']} {r['photo']} {r['kind']} {r['cap']}: {r['error']}" for r in err)]
    text = "\n".join(lines) + "\n"
    (out / "ergebnis.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("prepare", "dry", "run"):
        s = sub.add_parser(name)
        s.add_argument("--folder", default=str(FOLDER))
        if name == "run":
            s.add_argument("--models", nargs="+", default=list(MODELS), choices=MODELS)
            s.add_argument("--into", help="continue this existing round")
    r = sub.add_parser("rate")
    r.add_argument("mode", choices=("pairs", "models"))
    r.add_argument("round", nargs="?")
    sm = sub.add_parser("summary")
    sm.add_argument("round", nargs="?")
    a = ap.parse_args()
    {"prepare": cmd_prepare, "dry": cmd_dry, "run": cmd_run, "rate": cmd_rate, "summary": cmd_summary}[a.cmd](a)


if __name__ == "__main__":
    main()
