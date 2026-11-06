"""Manual check (not part of run_all.py): can a text encoder the model already has replace another text model file? (user 6.11.)

Three parts, each on the real ComfyUI (GPU; every run is one text step or one picture):

    python tests\\live_writer_compare.py krea     Krea 2: qwen3vl_4b_fp8_scaled (A) against qwen3vl_4b_int8_convrot (B) as the model's
                                                 text encoder: same prompts and seeds, pictures A | B | difference; plus the
                                                 Krea-2 prompt enhancer text with both files.
    python tests\\live_writer_compare.py flux2    Flux 2: the Flux 3 prompt upsampler (9B, A) against qwen3vl_4b_int8_convrot (B)
                                                 as the prompt upsampler: texts, then one picture per text.
    python tests\\live_writer_compare.py qwen     Qwen 2.1: qwen3.5_9b_w4a8_gptq (A) against qwen3vl_8b_int8_convrot (B) as the prompt
                                                 enhancer (texts, then pictures) and as the describer (Describe Canvas, 3 pictures).
    add --dry to only build the graphs and check the files are known to ComfyUI.

Output: data\\writer-compare\\<time>-<part>\\ (texts, pictures, sheets, report.md). Nothing in the plugin changes.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from PIL import Image  # noqa: E402

from pccomfy import workflows  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

sys.path.insert(0, str(ROOT / "tests"))
from live_flux2_file_compare import psnr, sheet  # noqa: E402

WF = ROOT / "workflows"
KREA_A, KREA_B = "qwen3vl_4b_fp8_scaled.safetensors", "qwen3vl_4b_int8_convrot.safetensors"
FLUX_A, FLUX_B = "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors", "qwen3vl_4b_int8_convrot.safetensors"
QWEN_A, QWEN_B = "qwen3.5_9b_w4a8_gptq.safetensors", "qwen3vl_8b_int8_convrot.safetensors"
DESCRIBE_IMAGES = ["Cat.jpeg", "Architecture.png", "DancerInWhite.png"]    # in ComfyUI's input folder


def prompts(n: int) -> list[str]:
    """n prompts from docs/tests/testprompts.md: the first one of every Medium group, spread over the groups."""
    lines = (ROOT / "docs" / "tests" / "testprompts.md").read_text(encoding="utf-8").splitlines()
    out, medium = [], False
    for ln in lines:
        if ln.startswith("###"):
            medium, got = ln.rstrip().endswith("Medium"), False
        elif medium and not got and re.match(r"\d+\. ", ln):
            out.append(re.sub(r"^\d+\. ", "", ln).strip())
            got = True
    step = max(1, len(out) // n)
    return out[::step][:n]


def run_text(c: ComfyUI, graph: dict, node: str) -> tuple[str, float]:
    t0 = time.time()
    hist = c.wait(c.queue(graph))
    out = (hist.get("outputs", {}).get(node) or {}).get("text") or [""]
    return "\n".join(str(x) for x in out), time.time() - t0


def writer_graph(wf: str, clip: str, ctype: str, prompt: str, seed: int = 7) -> tuple[dict, str]:
    """Only the text step of a workflow's prompt writer, with another text model file (the system prompt stays the workflow's)."""
    t = workflows.load_template(WF / wf)
    w = str(workflows.prompt_writers(t)[0])
    clip_id, sys_id = str(t[w]["inputs"]["clip"][0]), str(t[w]["inputs"]["system_prompt"][0])
    g = {clip_id: json.loads(json.dumps(t[clip_id])), sys_id: json.loads(json.dumps(t[sys_id])), w: json.loads(json.dumps(t[w]))}
    g[clip_id]["inputs"]["clip_name"] = clip
    g[clip_id]["inputs"]["type"] = ctype
    g[w]["inputs"]["prompt"] = prompt
    g[w]["inputs"]["sampling_mode.seed"] = seed
    g["900"] = {"class_type": "PreviewAny", "inputs": {"source": [w, 0]}, "_meta": {"title": "out"}}
    return g, "900"


def describe_graph(clip: str, image: str) -> tuple[dict, str]:
    t = workflows.load_template(WF / "describe-image.json")
    g = {k: t[k] for k in ("2", "3", "4")}
    g["1"] = {"class_type": "LoadImage", "inputs": {"image": image}, "_meta": {"title": "pc:image"}}
    g["2"]["inputs"]["clip_name"] = clip
    return g, "4"


def picture_graph(wf: str, prompt: str, seed: int, swap: dict | None = None, size=(1024, 1024)) -> tuple[dict, str]:
    """The model's own t2i workflow with a typed prompt (writer off); `swap` = {node-id: clip file} for the text encoder."""
    tpl = workflows.bypass_prompt_writer(workflows.load_template(WF / wf), prompt)
    if workflows.lora_switches(tpl):        # the model's own speed LoRA off (as it starts): the full recipe, and no LoRA file needed
        tpl = workflows.bypass_lora(tpl)
    for nid, f in (swap or {}).items():
        tpl[nid]["inputs"]["clip_name"] = f
    p = workflows.GenParams(prompt=prompt, seed=seed, width=size[0], height=size[1])
    return workflows.apply_template(tpl, p, None, None)


def run_picture(c: ComfyUI, graph: dict, out: str) -> tuple[Image.Image, float]:
    t0 = time.time()
    hist = c.wait(c.queue(graph))
    return c.output_images(hist, out)[0], time.time() - t0


def known(c: ComfyUI, *files: str):
    have = c._choices("CLIPLoader", "clip_name")
    miss = [f for f in files if f not in have]
    if miss:
        raise SystemExit("ComfyUI does not list: " + ", ".join(miss))


def pair_report(out: Path, title: str, rows: list[str], extra: list[str]):
    (out / "report.md").write_text("\n".join([f"# {title}", "", *rows, "", *extra]) + "\n", encoding="utf-8")
    print("\n".join(rows + extra))
    print(f"\nResults: {out}")


def pictures_ab(c, out: Path, cases: list[tuple[str, str, int]], make, label: str) -> list[str]:
    """cases: (name, prompt, seed); make(prompt, seed, tag) -> (graph, outnode). Runs all A, then all B; sheets A | B | difference."""
    times, rows = {}, ["| case | time A (s) | time B (s) | mean diff | PSNR (dB) |", "|---|---|---|---|---|"]
    for tag in ("A", "B"):
        for k, (name, prompt, seed) in enumerate(cases):
            g, node = make(prompt, seed, tag)
            im, secs = run_picture(c, g, node)
            im.save(out / f"{name}_{tag}.png")
            times[(tag, name)] = secs
            print(f"{label} {tag} {name}: {secs:.1f} s", flush=True)
    for name, prompt, seed in cases:
        a, b = Image.open(out / f"{name}_A.png"), Image.open(out / f"{name}_B.png")
        if a.size != b.size:
            b = b.resize(a.size)
        mae, db = psnr(a, b)
        sheet(a, b).save(out / f"{name}_sheet.png")
        rows.append(f"| {name}: {prompt[:70]} | {times[('A', name)]:.1f} | {times[('B', name)]:.1f} | {mae:.2f} | {db:.1f} |")
    return rows


def part_krea(c, out, dry):
    known(c, KREA_A, KREA_B)
    ps = prompts(4)
    if dry:
        picture_graph("krea2-turbo-t2i.json", ps[0], 1, {"2": KREA_B})
        writer_graph("krea2-turbo-t2i.json", KREA_B, "stable_diffusion", ps[0])
        return
    cases = [(f"krea_p{i + 1}_s{s}", p, s) for i, p in enumerate(ps) for s in (1234, 98765)]
    rows = pictures_ab(c, out, cases, lambda p, s, tag: picture_graph("krea2-turbo-t2i.json", p, s, {"2": KREA_A if tag == "A" else KREA_B}), "krea")
    extra = ["", "A = fp8 scaled (today), B = int8 ConvRot. PSNR above about 35 dB = practically the same picture; look at the sheets.", "",
             "## Krea-2 prompt enhancer text with both files (type krea2 as in the workflow)", ""]
    for i, p in enumerate(ps):
        for tag, f in (("A", KREA_A), ("B", KREA_B)):
            g, node = writer_graph("krea2-turbo-t2i.json", f, "krea2", p)
            text, secs = run_text(c, g, node)
            (out / f"enhance_p{i + 1}_{tag}.txt").write_text(f"{p}\n\n{text}\n", encoding="utf-8")
            extra.append(f"- p{i + 1} {tag}: {secs:.1f} s, {len(text)} characters")
            print("krea enhance", i + 1, tag, f"{secs:.1f} s", len(text), flush=True)
    pair_report(out, "Krea 2: text encoder fp8 scaled (A) against int8 ConvRot (B)", rows, extra)


def part_flux2(c, out, dry):
    known(c, FLUX_A, FLUX_B)
    ps = prompts(8)
    if dry:
        writer_graph("flux2-klein-t2i.json", FLUX_B, "stable_diffusion", ps[0])
        picture_graph("flux2-klein-t2i.json", ps[0], 1)
        return
    texts, extra = {}, ["", "## Texts (the upsampler's system prompt from flux2-klein-t2i.json)", ""]
    for tag, f, ct in (("A", FLUX_A, "flux3"), ("B", FLUX_B, "stable_diffusion")):
        for i, p in enumerate(ps):
            g, node = writer_graph("flux2-klein-t2i.json", f, ct, p)
            text, secs = run_text(c, g, node)
            texts[(tag, i)] = text.strip()
            (out / f"text_p{i + 1}_{tag}.txt").write_text(f"{p}\n\n{text}\n", encoding="utf-8")
            extra.append(f"- p{i + 1} {tag}: {secs:.1f} s, {len(text)} characters, {'one paragraph' if text.count(chr(10)) < 2 else 'several lines'}")
            print("flux2 text", i + 1, tag, f"{secs:.1f} s", len(text), flush=True)
    cases = [(f"flux2_p{i + 1}", ps[i], 1234) for i in range(4)]
    rows = pictures_ab(c, out, cases, lambda p, s, tag: picture_graph("flux2-klein-t2i.json", texts[(tag, ps.index(p))] or p, s), "flux2")
    pair_report(out, "Flux 2: prompt upsampler 9B (A) against qwen3vl 4B int8 (B)", rows, extra)


def part_qwen(c, out, dry):
    known(c, QWEN_A, QWEN_B)
    ps = prompts(6)
    if dry:
        writer_graph("qwen-image-21-t2i.json", QWEN_B, "stable_diffusion", ps[0])
        describe_graph(QWEN_B, "Cat.jpeg")
        picture_graph("qwen-image-21-t2i.json", ps[0], 1)
        return
    texts, extra = {}, ["", "## Texts (the enhancer's system prompt from qwen-image-21-t2i.json)", ""]
    for tag, f, ct in (("A", QWEN_A, "moss_image"), ("B", QWEN_B, "stable_diffusion")):
        for i, p in enumerate(ps):
            g, node = writer_graph("qwen-image-21-t2i.json", f, ct, p)
            text, secs = run_text(c, g, node)
            texts[(tag, i)] = text.strip()
            (out / f"text_p{i + 1}_{tag}.txt").write_text(f"{p}\n\n{text}\n", encoding="utf-8")
            extra.append(f"- p{i + 1} {tag}: {secs:.1f} s, {len(text)} characters, {'one paragraph' if text.count(chr(10)) < 2 else 'several lines'}")
            print("qwen text", i + 1, tag, f"{secs:.1f} s", len(text), flush=True)
    extra += ["", "## Describe Canvas (describe-image.json, 200 tokens)", ""]
    for img in DESCRIBE_IMAGES:
        for tag, f in (("A", QWEN_A), ("B", QWEN_B)):
            g, node = describe_graph(f, img)
            text, secs = run_text(c, g, node)
            (out / f"describe_{Path(img).stem}_{tag}.txt").write_text(text + "\n", encoding="utf-8")
            extra.append(f"- {img} {tag}: {secs:.1f} s, {len(text)} characters: {text.strip()[:160]!r}")
            print("qwen describe", img, tag, f"{secs:.1f} s", len(text), flush=True)
    cases = [(f"qwen_p{i + 1}", ps[i], 1234) for i in range(4)]
    rows = pictures_ab(c, out, cases, lambda p, s, tag: picture_graph("qwen-image-21-t2i.json", texts[(tag, ps.index(p))] or p, s), "qwen")
    pair_report(out, "Qwen 2.1: enhancer and describer qwen3.5 9B w4a8 (A) against qwen3vl 8B int8 (B)", rows, extra)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=("krea", "flux2", "qwen"))
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    c = ComfyUI()
    out = ROOT / "data" / "writer-compare" / f"{time.strftime('%Y%m%d-%H%M%S')}-{a.part}"
    if not a.dry:
        out.mkdir(parents=True)
    {"krea": part_krea, "flux2": part_flux2, "qwen": part_qwen}[a.part](c, out, a.dry)
    if a.dry:
        print("ok: files known to ComfyUI, graphs build")


if __name__ == "__main__":
    main()
