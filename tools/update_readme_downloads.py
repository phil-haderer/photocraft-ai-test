"""Writes the collapsible model download lists into README.md, from pccomfy/manifest.py and pccomfy/models.json.

The block sits between the lines `<!-- model-downloads:start -->` and `<!-- model-downloads:end -->`. One menu per model
(what it needs, what is optional), then one for the optional files that belong to no single model.
Run: python tools/update_readme_downloads.py [--check]
  --check   only report; exit code 1 when the README block is out of date (tests/test_readme_downloads.py does the same)
Run it after every change of the model files (manifest.py, models.json). Links are the direct file links of models.json.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
README = ROOT / "README.md"
START, END = "<!-- model-downloads:start -->", "<!-- model-downloads:end -->"

from pccomfy import manifest  # noqa: E402

TITLES = {"flux3": "Flux 3 Klein", "flux2": "Flux 2 Klein", "qwen": "Qwen Image 2.1", "fibo": "Fibo 2.0",
          "krea2": "Krea 2 Turbo", "moss": "MOSS Image"}
MODE_NAMES = {"txt2img": "Text to image", "edit": "Edit", "multi_edit": "Multi image edit", "inpaint": "Fill",
              "remove": "Remove", "outpaint": "Expand", "upscale": "Upscale", "refine": "Refine"}
FOLDER_ORDER = ("unet", "clip", "vae", "lora", "upscale_model", "preview", "bg_removal")
GATED_PAGES = {"black-forest-labs/flux-3-image-klein-comfy": "https://huggingface.co/black-forest-labs/flux-3-image-klein-comfy"}


def size_text(n: int) -> str:
    return f"{n / 1e9:.1f} GB" if n >= 1e9 else f"{max(1, round(n / 1e6))} MB"


def folder_of(f) -> str:
    base = manifest.KINDS[f.kind][2]
    sub = f.name.replace("\\", "/").rsplit("/", 1)[0] if ("\\" in f.name or "/" in f.name) else ""
    return f"models/{base}" + (f"/{sub}" if sub else "")


def short_name(f) -> str:
    return f.name.replace("\\", "/").rsplit("/", 1)[-1]


def source_of(f) -> str:
    """The link text: where the file comes from."""
    m = re.match(r"https://huggingface\.co/([^/]+/[^/]+)/", f.url)
    if m:
        return f"Hugging Face: {m.group(1)}"
    if "civitai.com" in f.url:
        return "Civitai"
    m = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/", f.url)
    return f"GitHub: {m.group(1)}" if m else "download"


def row(f, used_for: str) -> str:
    flags = []
    if f.note.startswith("gated"):
        flags.append("needs a free Hugging Face login and acceptance of the licence")
    if "civitai" in f.url:
        flags.append("Civitai may ask you to log in")
    link = f"[{source_of(f)}]({f.url})" if f.url else "no public source"
    extra = f" ({'; '.join(flags)})" if flags else ""
    return f"| `{short_name(f)}` | {used_for} | `{folder_of(f)}` | {size_text(f.size)} | {link}{extra} |"


def used_text(modes: list[str]) -> str:
    names = list(dict.fromkeys(modes))
    return "all functions" if (not names or len(names) >= 7) else ", ".join(names)


def table(rows: list[str], used_head: str) -> list[str]:
    return ["", f"| File | {used_head} | Goes into ComfyUI's | Size | Download |", "|---|---|---|---|---|"] + rows


NODE_NOTES = {      # custom node packs a model's functions need (manifest.NODE_PACKS); everything else uses ComfyUI's own nodes
    "flux3": "Upscale also needs the custom node pack [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) (Color Match). Install it from the ComfyUI Manager or the link, then restart ComfyUI.",
    "fibo": "The tiles option of Upscale also needs the custom node pack [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes) (Color Match). Install it from the ComfyUI Manager or the link, then restart ComfyUI.",
}


def model_block(key: str) -> list[str]:
    t = manifest.TABS[key]
    need: dict[str, list[str]] = {}      # file -> the functions that need it ("" = all)
    for n in t.required:
        need.setdefault(n, [])
    for mode, spec in t.modes.items():
        for n in spec.requires:
            if n in need and need[n] == []:
                continue
            need.setdefault(n, []).append(MODE_NAMES.get(mode, mode))
    opt: dict[str, str] = {}
    for n in list(t.optional) + [x for s in t.modes.values() for x in s.optional]:
        f = manifest.FILES.get(n)
        if f is None or f.kind == "bg_removal" or n in need:
            continue
        opt[n] = manifest.FEATURE_USE.get(n, "")
    order = lambda n: (FOLDER_ORDER.index(manifest.FILES[n].kind), n)    # noqa: E731
    total = sum(manifest.FILES[n].size for n in need)
    out = [f"<details>", f"<summary><b>{TITLES[key]}</b>: about {size_text(total)} needed</summary>"]
    out += table([row(manifest.FILES[n], used_text(need[n])) for n in sorted(need, key=order)], "Needed for")
    if opt:
        out += ["", "Optional (the model works without them, the named feature is greyed out):"]
        out += table([row(manifest.FILES[n], opt[n] or "extra") for n in sorted(opt, key=order)], "Feature")
    if key in NODE_NOTES:
        out += ["", "**Custom node:** " + NODE_NOTES[key]]
    out += ["", "</details>", ""]
    return out


def extra_block() -> list[str]:
    files = [f for f in manifest.FILES.values() if f.kind == "bg_removal"]
    rows = [row(f, manifest.FEATURE_USE.get(f.name, "")) for f in sorted(files, key=lambda f: f.name)]
    out = ["<details>", "<summary><b>Remove background</b> (scissors button, optional)</summary>"]
    out += table(rows, "Feature")
    out += ["", "RMBG-2.0 is a community copy of the official file, which needs a Hugging Face login "
            "([official page](https://huggingface.co/briaai/RMBG-2.0)).", "", "</details>", ""]
    return out


def render() -> str:
    lines = [START, ""]
    for key in ("flux3", "flux2", "qwen", "fibo", "krea2", "moss"):
        lines += model_block(key)
    lines += extra_block()
    lines += [END]
    return "\n".join(lines)


def update(text: str) -> str:
    a, b = text.index(START), text.index(END) + len(END)
    return text[:a] + render() + text[b:]


def main() -> int:
    text = README.read_text(encoding="utf-8")
    new = update(text)
    if new == text:
        print("README download lists are up to date")
        return 0
    if "--check" in sys.argv:
        print("README download lists are OUT OF DATE: run python tools/update_readme_downloads.py")
        return 1
    README.write_text(new, encoding="utf-8", newline="\n")
    print("README download lists written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
