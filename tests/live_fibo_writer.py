"""Manual check (not part of run_all.py): which text model writes Fibo's prompt (VGL) and describes the canvas better,
Qwen3-VL 4B int8 ConvRot or Qwen 3.5 9B int8 ConvRot (user 6.11.).

Only the text step runs (no picture is drawn), so the GPU is busy for seconds per case. For every case both files get the
same picture and text; the script times each run and checks the VGL: valid JSON, all keys of Bria's schema, nothing
before or after the JSON, an `edit_instruction` that is a command (edit cases only), an empty `text_render` unless the
text was asked for.

    python tests\\live_fibo_writer.py

Uses the sample pictures in ComfyUI's input folder (Cat.jpeg, Dog.jpeg, Flowers.jpg, Architecture.png, DancerInWhite.png,
Helmet.png). Output: data\\fibo-writer-test\\<time>\\ (report.md and the raw text of every run).
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pccomfy import config as cfgmod, workflows  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = cfgmod.CONFIG_DIR / "fibo-writer-test"
WRITERS = {"4B": "qwen3vl_4b_int8_convrot.safetensors", "9B": "qwen3.5_9b_int8_convrot.safetensors"}

EDIT_CASES = [      # (picture, instruction)
    ("Cat.jpeg", "make the cat wear a small red hat"),
    ("Dog.jpeg", "change the background to a snowy forest"),
    ("Flowers.jpg", "turn the photo into an oil painting"),
    ("Architecture.png", "change the lighting to golden hour"),
    ("DancerInWhite.png", "change the dress to a blue one"),
    ("Helmet.png", "remove the helmet's visor reflection and add a scratch on the left side"),
]
T2I_CASES = [
    "a red fox sleeping in the snow",
    "three apples and two pears on a wooden table",
    "a neon sign that says OPEN above a rainy street at night",
    "portrait of an old fisherman, soft window light",
]
DESCRIBE_CASES = ["Cat.jpeg", "Architecture.png", "DancerInWhite.png"]

KEYS_COMMON = ["short_description", "objects", "background_setting", "lighting", "aesthetics", "photographic_characteristics",
               "style_medium", "artistic_style", "context", "text_render"]
OBJECT_KEYS = ["description", "location", "relative_size", "shape_and_color", "texture", "appearance_details", "relationship",
               "orientation"]
BAD_WORDS = ("changed", "added", "removed", "replaced", "has been", "instead of", "the original")
VERBS = ("add", "change", "make", "move", "remove", "render", "turn", "zoom", "replace", "convert", "apply", "set", "give", "put")


def check_vgl(text: str, edit: bool, asked_text: bool = False) -> list[str]:
    """What is wrong with this VGL (empty list = correct)."""
    t = text.strip()
    bad = []
    if t.startswith("```") or t.endswith("```"):
        bad.append("wrapped in a Markdown code block")
    try:
        j = json.loads(t.strip("`").removeprefix("json").strip() if t.startswith("```") else t)
    except ValueError as e:
        return bad + [f"not valid JSON ({str(e)[:50]})"]
    keys = KEYS_COMMON + (["edit_instruction"] if edit else [])
    miss = [k for k in keys if k not in j]
    if miss:
        bad.append("missing keys: " + ", ".join(miss))
    extra = [k for k in j if k not in KEYS_COMMON + ["edit_instruction"]]
    if extra:
        bad.append("extra keys: " + ", ".join(extra))
    if not edit and "edit_instruction" in j:
        bad.append("edit_instruction in a text to image prompt")
    objs = j.get("objects")
    if not isinstance(objs, list) or not objs:
        bad.append("objects is not a filled list")
    else:
        if len(objs) > 5:
            bad.append(f"{len(objs)} objects (max. 5)")
        for o in objs:
            m = [k for k in OBJECT_KEYS if k not in o]
            if m:
                bad.append("an object lacks: " + ", ".join(m))
                break
    if j.get("text_render") and not asked_text:
        bad.append("text_render filled without a text in the request")
    if not isinstance(j.get("lighting"), dict) or not all(k in j["lighting"] for k in ("conditions", "direction", "shadows")):
        bad.append("lighting incomplete")
    if not isinstance(j.get("aesthetics"), dict) or not all(k in j["aesthetics"] for k in ("composition", "color_scheme", "mood_atmosphere")):
        bad.append("aesthetics incomplete")
    ei = str(j.get("edit_instruction", "")).strip()
    if edit:
        if not ei or ei.split()[0].lower().strip(",.") not in VERBS:
            bad.append(f"edit_instruction is no command: {ei[:50]!r}")
        if "reference image" in ei.lower() or "original image" in ei.lower():
            bad.append("edit_instruction names the reference image")
        low = json.dumps({k: v for k, v in j.items() if k != "edit_instruction"}).lower()
        hits = [w for w in BAD_WORDS if w in low]
        if hits:
            bad.append("edit words outside edit_instruction: " + ", ".join(hits))
    return bad


def run(c: ComfyUI, graph: dict, node: str) -> tuple[str, float]:
    t0 = time.time()
    pid = c.queue(graph)
    hist = c.wait(pid)
    out = (hist.get("outputs", {}).get(node) or {}).get("text") or [""]
    return "\n".join(str(x) for x in out), time.time() - t0


def edit_graph(clip: str, image: str, instruction: str) -> tuple[dict, str]:
    t = workflows.load_template(ROOT / "workflows" / "fibo2-edit.json")
    g = {k: t[k] for k in ("10", "11", "12", "13")}
    g["4"] = {"class_type": "LoadImage", "inputs": {"image": image}, "_meta": {"title": "pc:image"}}
    g["10"]["inputs"]["clip_name"] = clip
    g["12"]["inputs"]["prompt"] = instruction
    return g, "13"


def t2i_graph(clip: str, prompt: str) -> tuple[dict, str]:
    t = workflows.load_template(ROOT / "workflows" / "fibo2-t2i.json")
    g = {k: t[k] for k in ("20", "21", "22", "23")}
    g["20"]["inputs"]["clip_name"] = clip
    g["22"]["inputs"]["prompt"] = prompt
    return g, "23"


def describe_graph(clip: str, image: str) -> tuple[dict, str]:
    t = workflows.load_template(ROOT / "workflows" / "describe-image.json")
    g = {k: t[k] for k in ("2", "3", "4")}
    g["1"] = {"class_type": "LoadImage", "inputs": {"image": image}, "_meta": {"title": "pc:image"}}
    g["2"]["inputs"]["clip_name"] = clip
    return g, "4"


def main():
    url = cfgmod.load()["comfyui"]["url"]
    c = ComfyUI(url)
    out = BASE / time.strftime("%Y%m%d-%H%M%S")
    out.mkdir(parents=True)
    rep = ["# Fibo-Textmodell: 4B gegen 9B", "", "Zeit = ein Lauf je Fall, das erste Modell-Laden steckt im ersten Fall jeder Datei; Prüfung = `check_vgl` in tests/live_fibo_writer.py", ""]
    rows, n = [], 0
    jobs = [("edit", f"{img}: {ins}", lambda clip, i=img, s=ins: edit_graph(clip, i, s), True, False) for img, ins in EDIT_CASES]
    jobs += [("t2i", p, lambda clip, p=p: t2i_graph(clip, p), False, "says" in p) for p in T2I_CASES]
    jobs += [("describe", img, lambda clip, i=img: describe_graph(clip, i), None, False) for img in DESCRIBE_CASES]
    for name, clip in WRITERS.items():          # one file after the other: the model stays loaded (ComfyUI would swap them otherwise)
        for i, (kind, label, mk, edit, asked) in enumerate(jobs):
            g, node = mk(clip)
            text, sec = run(c, g, node)      # every case once: a repeat would come from ComfyUI's cache (0 s)
            n += 1
            (out / f"{i + 1:02d}-{kind}-{name}.txt").write_text(f"{label}\n\n{text}\n", encoding="utf-8")
            problems = check_vgl(text, edit, asked) if edit is not None else (["empty"] if not text.strip() else [])
            rows.append((kind, label, name, sec, problems, len(text)))
            print(f"{kind:8} {name} {sec:5.1f} s  {len(text):5d} chars  {'OK' if not problems else '; '.join(problems)}  [{label[:50]}]", flush=True)
    rep += ["| Fall | Datei | Zeit | Zeichen | VGL-Prüfung |", "|---|---|---|---|---|"]
    for kind, label, name, sec, probs, ln in rows:
        rep.append(f"| {kind}: {label} | {name} | {sec:.1f} s | {ln} | {'in Ordnung' if not probs else '; '.join(probs)} |")
    for kind in ("edit", "t2i", "describe"):
        for name in WRITERS:
            sel = [r for r in rows if r[0] == kind and r[2] == name]
            ok = sum(1 for r in sel if not r[4])
            avg = sum(r[3] for r in sel) / len(sel)
            rep.append(f"\n**{kind} {name}:** {ok} von {len(sel)} in Ordnung, im Mittel {avg:.1f} s")
    (out / "report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print(f"\nReport: {out / 'report.md'}")


if __name__ == "__main__":
    main()
