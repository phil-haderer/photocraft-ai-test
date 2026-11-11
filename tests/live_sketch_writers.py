"""Manual check (not part of run_all.py): which text model writes the Sketch prompt (user 10.11.). Today Flux 3, Flux 2 and
Qwen Image 2.1 expand the prompt with BFL's upsampler (qwen3.5 9B, 6.7 GB, gated). Tested against it, through the real
plugin path (the bridge with the PhotoCraft simulator of test_reference_mode and the real ComfyUI, the built Sketch
workflows; only the CLIPLoader of the upsampler, node 401, gets another file):

- Flux 3: its own encoder qwen3vl_4b (no extra download);
- Flux 2: qwen3vl_4b (its own encoder qwen_3_8b reads only text, it cannot see the scribble);
- Qwen Image 2.1: its own encoder qwen3vl_8b, and qwen3vl_4b (the 8 GB candidate).

Pictures from older rounds on this PC: the seven sketches of round 3 (Photo) and the six photos with red scribbles of
round 2 A (Scribble on photo, crop path of the build), the subject as there; seed 1234; BFL runs again in the same path,
so every pair differs only in the writer. Fibo has no writer in Sketch and is left out.

    python tests\\live_sketch_writers.py plan                  (what would run; no ComfyUI)
    python tests\\live_sketch_writers.py run [--dry] [--into <folder>] [--only flux3 ...] [--pictures N] [--free]
                                               [--sketch-template photo|illustration] [--part a b c d e]
                                                              (resumes in --into; key.json after every picture)

Parts of the round on PC A (docs/sketch-schreiber-plan.md, step 2; --part replaces --only and --sketch-template):
a Qwen 4B (the rest), b Qwen 4B + instruction v2, c Flux 2 4B + instruction v2 with Illustration, d Flux 2 BFL with
Illustration, e Flux 2 4B + instruction v2 with Photo (c to e on the seven sketches only).

Output: data\\sketch-test\\writers-<time>\\ (eingabe\\, bilder\\, key.json with the written prompt and the time of each run).
Rate with ``python tests\\live_sketch.py rate <folder>`` (blind, good / bad with faults).
"""
import argparse
import json
import os
import shutil
import random
import socket
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
# a data folder of its own (a copy of settings.json for the address and the linked files): the window built here must not
# write the plugin's state.json (last model, pages) while the user works with the plugin
_HOME = Path(tempfile.mkdtemp(prefix="pccomfy-writers-"))
if (DATA / "settings.json").exists():
    shutil.copyfile(DATA / "settings.json", _HOME / "settings.json")
os.environ["PCCOMFY_HOME"] = str(_HOME)
os.environ["PCCOMFY_NO_TIPS"] = "1"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from PIL import Image  # noqa: E402

import live_sketch  # noqa: E402
import test_reference_mode as tr  # noqa: E402
from pccomfy import bridge, config as cfgmod, inventory, models  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = DATA / "sketch-test"
SEED = 1234
UPS = "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors"
VL4, VL8 = "qwen3vl_4b_int8_convrot.safetensors", "qwen3vl_8b_int8_convrot.safetensors"
# model -> the writers to compare; the first is today's
IN4 = "qwen3vl 4B instruction"
IN4V2 = "qwen3vl 4B instruction v2"      # the neutral sketch part (user 10.11.: Illustration must not become a photo)
WRITERS = {"flux3": ("BFL upsampler", "qwen3vl 4B", IN4),
           "flux2": ("BFL upsampler", "qwen3vl 4B", IN4),
           "qwen": ("BFL upsampler", "qwen3vl 8B", "qwen3vl 4B", IN4)}
WRITER_FILE = {"BFL upsampler": UPS, "qwen3vl 4B": VL4, "qwen3vl 8B": VL8, IN4: VL4, IN4V2: VL4}
# User 10.11. evening: does 4B catch up with another system prompt? The workflows' prompt (node 402) asks for a caption of
# the whole finished picture; BFL's upsampler writes an edit instruction anyway, 4B follows the prompt word for word.
# This one asks 4B for the instruction itself.
_INSTR_HEAD = (
    "You write the edit instruction for an image editing model. You get a picture and a short request. Write ONE clear "
    "English instruction that starts with a verb. If the picture carries rough coloured scribble lines: say where they "
    "are (which part of the picture, what they lie on) and what replaces them exactly there; name the new object with "
    "its look, material, colour, size and pose, matching the light, perspective and style of the photo; the scribble "
    "lines must be gone and everything else stays unchanged. ")
_INSTR_TAIL = (" Output only the instruction as one block of prose, 60 to 150 words, with no lists, Markdown or "
               "explanations.")
# v1: rated on PC B (10.11.), the sketch part fixed to a photograph; kept for those pictures
INSTRUCTION_SYSTEM_V1 = _INSTR_HEAD + (
    "If the picture is a sketch or drawing: say to turn it into a realistic photograph and name each element of the "
    "drawing with its real material, colour and place, keeping the composition, shapes and proportions exactly, with no "
    "drawing lines left.") + _INSTR_TAIL
# v2 (user 10.11.): the sketch part neutral, the look comes from the request; the scribble part word for word as v1.
# Built into Flux 2's Sketch workflow since 10.11.: it lives in pccomfy/models.py now (one place)
INSTRUCTION_SYSTEM = models.SKETCH_WRITER_SYSTEM
SYSTEM_OF = {IN4: INSTRUCTION_SYSTEM_V1, IN4V2: INSTRUCTION_SYSTEM}

# the sketch templates by name (photos with scribbles always get "Scribble on photo")
TEMPLATES = {"photo": "Photo", "illustration": "Illustration"}
TEMPLATE_TEXT = {"Photo": models.SKETCH_PHOTO, "Illustration": models.SKETCH_ILLUSTRATION,
                 "Scribble on photo": models.SKETCH_SCRIBBLE}
# docs/sketch-schreiber-plan.md, step 2: part -> (model, writer, sketch template, kinds of picture)
PARTS = {"a": ("qwen", "qwen3vl 4B", "Photo", ("sketch", "photo")),
         "b": ("qwen", IN4V2, "Photo", ("sketch", "photo")),
         "c": ("flux2", IN4V2, "Illustration", ("sketch",)),
         "d": ("flux2", "BFL upsampler", "Illustration", ("sketch",)),
         "e": ("flux2", IN4V2, "Photo", ("sketch",))}


def sources():
    """The pictures: round 3's sketches and round 2 A's scribbled photos, with the subject typed there."""
    items = []
    for pattern, kind in (("round3-2*", "sketch"), ("round2-A-2*", "photo")):
        runs = sorted(p for p in BASE.glob(pattern) if (p / "key.json").exists())
        if not runs:
            sys.exit(f"No folder {pattern} in {BASE}")
        key = json.load(open(runs[-1] / "key.json", encoding="utf-8"))["items"]
        seen = set()
        for it in key.values():
            if it["kind"] != kind or it["input"] in seen:
                continue
            seen.add(it["input"])
            src = next(runs[-1].joinpath("eingabe").glob(Path(it["input"]).stem + ".*"))     # round 2 A keeps .jpg
            items.append({"src": src, "file": it["file"], "desc": it["desc"].strip(),
                          "kind": kind, "round": runs[-1].name})
    for k, s in enumerate(items, 1):
        s["input"] = f"{k}.png"
    return items


def template_of(s: dict, sketch_template: str) -> str:
    """The template the picture runs with: a photo with scribbles always "Scribble on photo", a sketch the chosen one."""
    return "Scribble on photo" if s["kind"] == "photo" else sketch_template


def text_of(s: dict, template: str) -> str:
    return TEMPLATE_TEXT[template].replace(models.SKETCH_MARK, s["desc"])


def job_list(a) -> list:
    """(model, writer, sketch template, kinds) in run order: the parts, or every writer of --only with one template."""
    if a.part:
        return [PARTS[p] for p in a.part]
    return [(mk, w, TEMPLATES[a.sketch_template], ("sketch", "photo")) for mk in a.only for w in WRITERS[mk]]


def writer_workflow(mk: str, writer: str, folder: Path) -> Path:
    """The model's Sketch workflow with another file in the upsampler's loader (type stable_diffusion, as the other
    qwen3vl writers of the plugin, e.g. fibo2-edit.json)."""
    name = models.BY_KEY[mk].modes["sketch"].workflow
    g = json.loads((ROOT / "workflows" / name).read_text(encoding="utf-8"))
    if writer != "BFL upsampler":
        g["401"]["inputs"]["clip_name"] = WRITER_FILE[writer]
        g["401"]["inputs"]["type"] = "stable_diffusion"
    if writer in SYSTEM_OF:
        g["402"]["inputs"]["value"] = SYSTEM_OF[writer]
    out = folder / f"{Path(name).stem}--{writer.replace(' ', '_')}.json"
    out.write_text(json.dumps(g, indent=1), encoding="utf-8")
    return out


def cmd_plan(a):
    items = sources()
    jobs = job_list(a)
    for s in items:
        print(f"{s['input']:>6} {s['kind']:<6} {s['file']:<45} \"{s['desc']}\"")
    runs = sum(1 for _, _, _, kinds in jobs for s in items if s["kind"] in kinds)
    print(f"\n{len(items)} pictures, {len(jobs)} model-writer-template sets = {runs} runs: "
          + ", ".join(f"{mk} {w} ({tpl})" for mk, w, tpl, _ in jobs))


def window_request(app, mk: str, s: dict, template: str):
    """The Request the window sends for Sketch with this model's start settings (saved pages ignored), the template of the
    picture's kind and its text in the field, seed 1234."""
    from dataclasses import replace
    app.v_model.set(mk)
    app.v_mode.set("sketch")
    app._factory = True
    try:
        app._on_model()
        app._on_mode()
    finally:
        app._factory = False
    app._sketch_pick(template)
    app.t_prompt.delete("1.0", "end")
    app.t_prompt.insert("1.0", text_of(s, template))
    req = app._request()
    assert req.enhance and req.scribble == (s["kind"] == "photo"), (mk, s["input"], req.enhance, req.scribble)
    req.params = replace(req.params, seed=SEED)
    return req


def run_one(comfy, req, pic: Image.Image, exch: Path):
    """One run as the plugin makes it: a document with the picture as its only layer, the bridge, the composite."""
    tr.W, tr.H = pic.size                 # the simulator's document size
    pc = tr.FakePC(exch)
    pc.docs.append(tr.Doc("photo.png", [{"id": 1, "img": pic.convert("RGBA"), "visible": True, "name": "Background"}]))
    b = bridge.Bridge(pc, comfy, exch)
    res = b.run(req)
    return tr.FakePC.composite(pc.docs[0]).convert("RGB"), res


def free_memory(comfy) -> None:
    """ComfyUI's /free: unload every model and free RAM and VRAM before the next run (a failure only gets a line)."""
    try:
        comfy._json("/free", {"unload_models": True, "free_memory": True})
    except Exception as e:
        print(f"   (free memory failed: {type(e).__name__}: {e})", flush=True)


def cmd_run(a):
    items = sources()[: a.pictures or None]
    out = Path(a.into) if a.into else BASE / f"writers-{time.strftime('%Y%m%d-%H%M%S')}"
    for sub in ("bilder", "eingabe", "wf", "xch"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    pics = {}
    for s in items:
        im = Image.open(s["src"]).convert("RGB")
        im.save(out / "eingabe" / s["input"])
        pics[s["input"]] = im
    kf = out / "key.json"
    old = json.load(open(kf, encoding="utf-8")) if kf.exists() else {}
    key = old.get("items", {})
    rated_order = list(old.get("order", []))       # a resumed round keeps the order the user already rated in

    def write_key():
        new = [f for f in key if f not in rated_order]
        random.Random(1011).shuffle(new)            # blind: models and writers mixed; new pictures after the old ones
        extra = {k: v for k, v in old.items() if k not in ("items", "order", "writers", "seed", "prompts", "parts",
                                                           "system_prompt_instruction", "system_prompt_instruction_v2")}
        json.dump({"items": key, "order": rated_order + new, "writers": WRITERS, "seed": SEED, "prompts": TEMPLATE_TEXT,
                   "parts": {p: list(v) for p, v in PARTS.items()},
                   "system_prompt_instruction": INSTRUCTION_SYSTEM_V1, "system_prompt_instruction_v2": INSTRUCTION_SYSTEM,
                   **extra},       # keeps "part": "R5" set for rating
            open(kf, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    url = "http://127.0.0.1:1" if a.dry else cfgmod.load()["comfyui"]["url"]
    if not a.dry:
        host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
        try:
            socket.create_connection((host, port), timeout=2).close()
        except OSError:
            sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    comfy = ComfyUI(url)
    if not a.dry:
        inv = inventory.fetch(comfy, cfgmod.model_map())
        have = set(inv.lists.get("clip", [])) if hasattr(inv, "lists") else None
        for f in (UPS, VL4, VL8):
            if have is not None and not any(Path(h).name == f for h in have):
                print(f"WARNING: {f} not in ComfyUI's text encoder list", flush=True)
    app = live_sketch.make_app(url)
    jobs = job_list(a)
    total = sum(1 for _, _, _, kinds in jobs for s in items if s["kind"] in kinds)
    n, t_start = 0, time.time()
    for mk, writer, sketch_tpl, kinds in jobs:
        wf = writer_workflow(mk, writer, out / "wf")
        for s in items:
            if s["kind"] not in kinds:
                continue
            n += 1
            tpl = template_of(s, sketch_tpl)
            if any(r["model_key"] == mk and r["writer"] == writer and r["input"] == s["input"]
                   and r.get("prompt") == tpl for r in key.values()):
                continue
            req = window_request(app, mk, s, tpl)
            req.workflow = str(wf)
            if a.dry:
                print(f"{n}/{total} {mk} {writer} {s['input']} {s['kind']} {tpl}: {Path(wf).name}", flush=True)
                continue
            t0 = time.time()
            try:
                im, res = run_one(comfy, req, pics[s["input"]], out / "xch")
            except Exception as e:            # one failing writer (e.g. a loader type) must not stop the round
                print(f"{n}/{total} {mk} {writer} {tpl} {s['input']}: FAILED {type(e).__name__}: {e}", flush=True)
                continue
            fid = f"{len(key) + 1:04d}"
            im.save(out / "bilder" / f"{fid}.png")
            key[fid] = {"model": models.BY_KEY[mk].label, "model_key": mk, "writer": writer, "variant": writer,
                        "file": s["file"], "input": s["input"], "kind": s["kind"], "desc": s["desc"],
                        "prompt": tpl, "seed": SEED, "text": text_of(s, tpl), "caption": res.get("vgl", ""), "secs": round(time.time() - t0, 1),
                        "scribble": res.get("scribble", ""), "region": res.get("region"), "size": res.get("size")}
            write_key()
            print(f"{n}/{total} {mk} {writer} {s['input']} {s['kind']} {tpl}: {key[fid]['secs']:.0f} s, "
                  f"{len(key[fid]['caption'].split())} words", flush=True)
            if a.free:
                free_memory(comfy)
    if not a.dry:                             # a dry run leaves key.json as it is (it travels through git)
        write_key()
    print(f"\n{'DRY RUN' if a.dry else 'DONE'} in {(time.time() - t_start) / 60:.1f} min: {len(key)} pictures in {out}\n"
          f"Next: python tests\\live_sketch.py rate \"{out}\"", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("plan", "run"))
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--into")
    ap.add_argument("--pictures", type=int, default=0, help="only the first N pictures (a quick check)")
    ap.add_argument("--free", action="store_true",
                    help="ask ComfyUI to unload the models and free memory after every run (10.11.: Qwen with 8B, 4B and "
                         "the upsampler filled RAM and page file, ComfyUI stopped taking connections)")
    ap.add_argument("--only", nargs="+", default=list(WRITERS), choices=list(WRITERS))
    ap.add_argument("--sketch-template", default="photo", choices=list(TEMPLATES),
                    help="the template of the sketches (photos with scribbles always run with Scribble on photo)")
    ap.add_argument("--part", nargs="+", choices=list(PARTS),
                    help="parts of the round on PC A (docs/sketch-schreiber-plan.md); replaces --only and --sketch-template")
    a = ap.parse_args()
    {"plan": cmd_plan, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    main()
