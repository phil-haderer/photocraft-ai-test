"""The model manifest: which files each tab needs, and where a user gets them.

Pure data, no ComfyUI and no Tk. Three levels per tab (decided with the user, see PLAN.md task 6 to 8):

* ``required``: files the whole tab needs. When one is missing the tab is greyed out.
* ``modes[mode].requires``: extra files of one mode. When one is missing the whole tab is locked (standard settings rule),
  unless the mode is ``alone``: then only that mode is greyed out (Sketch, whose upsampler is 6.7 GB and gated; user 9.11.).
* ``optional`` (tab or mode): switches and helpers (speed LoRAs, prompt enhancers). A missing one is only a note.

The file names are the ones the shipped ``workflows/*.json`` load (checked by tests/test_detection.py). The tab level
``required`` set is mirrored in ``models.Model.requires`` (the same names, ``tab_required``); a test keeps the two equal.
Download links are direct file links (Hugging Face ``resolve/main``, Civitai download API), each checked on 2026-10-27
against the user's working copy by size and, where the name was not unique, by SHA256; the table with licences is
``docs/model-downloads.md``. An empty link means: no public source right now.
The files themselves (name, kind, link, note, size, SHA-256) live in ``models.json`` next to this file, read at start (7.11.); which model needs which file stays here (``TABS``).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

# kind -> (loader node class, input field, folder inside ComfyUI's models folder)
KINDS = {
    "unet": ("UNETLoader", "unet_name", "diffusion_models"),
    "clip": ("CLIPLoader", "clip_name", "text_encoders"),
    "vae": ("VAELoader", "vae_name", "vae"),
    "lora": ("LoraLoaderModelOnly", "lora_name", "loras"),
    "preview": ("", "", "vae_approx"),       # live preview decoders (TAESD): no loader node, ComfyUI lists /models/vae_approx
    "bg_removal": ("LoadBackgroundRemovalModel", "bg_removal_name", "background_removal"),   # "Cut out" in the reference slots
    "upscale_model": ("UpscaleModelLoader", "model_name", "upscale_models"),               # 4x UltraSharp in Flux 3 Upscale
}
# helpers several models share, listed apart in the settings window as "Additional models" (user 30.10.), with their use
# Own use line of a file under "Additional" with no model list behind it (the scissors work with every model, so no "...: Flux 3, Flux 2 ..."; user 6.11.)
ADDITIONAL_USE = {
    "birefnet.safetensors": "Remove background (scissors), Cut out in Multi Image Edit",
    "rmbg-2.0.safetensors": "Remove background (scissors), second model",
}
ADDITIONAL_KINDS = {"bg_removal": "Remove background (scissors), Cut out in Multi Image Edit", "preview": "Live preview"}
KIND_LABEL = {"unet": "Diffusion model", "clip": "Text encoder", "vae": "VAE", "lora": "LoRA", "preview": "Preview decoder",
              "bg_removal": "Background removal", "upscale_model": "Upscale model"}


@dataclass(frozen=True)
class File:
    name: str                       # as ComfyUI lists it (a LoRA carries its sub-folder, "Moss\\lora_dmd2.safetensors")
    kind: str                       # key of KINDS
    url: str = ""                   # direct download link ("" = no public source right now)
    note: str = ""                  # licence, gated, "likely, not confirmed" ...
    aliases: tuple = ()             # other names the same file is known under
    size: int = 0                   # bytes, as the source serves it (0 = not known)
    sha256: str = ""                # the SHA-256 the source publishes ("" = none published); set from _SHA256 below

    @property
    def size_text(self) -> str:
        """"9.4 GB", "165 MB" ("" when not known)."""
        if not self.size:
            return ""
        return f"{self.size / 1e9:.1f} GB" if self.size >= 1e9 else f"{self.size / 1e6:.0f} MB"

    @property
    def folder(self) -> str:
        return KINDS[self.kind][2]

    @property
    def target(self) -> str:
        """Where to put it, relative to ComfyUI's models folder (Windows spelling)."""
        sub = self.name.replace("/", "\\").rpartition("\\")[0]
        return "models\\" + self.folder + (("\\" + sub) if sub else "")


MODELS_JSON = Path(__file__).with_name("models.json")       # the files and their download links (user 7.11.: a file of its own, easy to change)
_FIELDS = {"name", "kind", "url", "note", "aliases", "size", "sha256", "comment"}      # "comment" is for the reader of the file and is ignored


def load_files(path: Path = MODELS_JSON) -> list[File]:
    """The files of ``models.json`` in their order. A broken file stops the start with a message that names the entry."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        entries = doc["files"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise ValueError(f"{path}: cannot read the model list ({e}).") from e
    out: list[File] = []
    for i, e in enumerate(entries):
        where = f"{path}, entry {i + 1} ({e.get('name', '?') if isinstance(e, dict) else '?'})"
        if not isinstance(e, dict) or not isinstance(e.get("name"), str) or not e["name"]:
            raise ValueError(f"{where}: needs a name.")
        if set(e) - _FIELDS:
            raise ValueError(f"{where}: unknown field {sorted(set(e) - _FIELDS)}.")
        if e.get("kind") not in KINDS:
            raise ValueError(f"{where}: kind must be one of {', '.join(KINDS)}.")
        if not isinstance(e.get("size", 0), int) or isinstance(e.get("size", 0), bool):
            raise ValueError(f"{where}: size must be a whole number of bytes.")
        out.append(File(e["name"], e["kind"], e.get("url", ""), e.get("note", ""), tuple(e.get("aliases", ())),
                        e.get("size", 0), e.get("sha256", "")))
    names = [f.name for f in out]
    if len(set(names)) != len(names):
        raise ValueError(f"{path}: a file name appears twice: {sorted({n for n in names if names.count(n) > 1})}.")
    return out


_LIST = load_files()
FILES: dict[str, File] = {f.name: f for f in _LIST}


@dataclass(frozen=True)
class ModeSpec:
    requires: tuple = ()            # extra files this mode needs on top of the tab's
    optional: tuple = ()            # files of switches that belong to this mode
    nodes: tuple = ()               # node classes this mode needs (checked against ComfyUI's /object_info)
    alone: bool = False             # a missing file locks only this mode, not the model (Sketch, user 9.11.); the settings
                                    # window and the README list its files with the additional features


@dataclass(frozen=True)
class TabSpec:
    required: tuple                 # files the whole tab needs
    modes: dict = field(default_factory=dict)   # mode key -> ModeSpec (a mode that is not here has no extras)
    optional: tuple = ()            # files of switches that belong to the whole tab


_UPS = "flux2-vae.safetensors"
_ULTRA = ("Flux 2\\ultra_real_v4.safetensors",)
_UPSAMPLER = "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors"
_TAEF2 = "taef2_decoder.pth"           # live preview of the Flux 2 latent: Flux 2, Flux 3, Fibo, MOSS
DESCRIBE_FALLBACK = "qwen3.5_9b_int8_convrot.safetensors"     # the LLM button and "Describe" in the reference slots (user 30.10.)
# Sketch runs never without a writer (sketch round 2: 45 of 72 without, 64 of 71 with); missing, it locks only the tab
# Sketch (user 9.11.). Flux 3 and Qwen write with BFL's upsampler, Flux 2 with qwen3vl 4B and an instruction prompt (writer
# round 10.11., option B). Fibo's Sketch is its edit graph without a writer: no files of its own.
_SKETCH = ModeSpec(requires=(_UPSAMPLER,), alone=True)
_CUT_OWN_LLM = ModeSpec(optional=("birefnet.safetensors", "rmbg-2.0.safetensors"))     # the same without the 9B fallback, for every model: the 9B fallback is no longer listed anywhere (Fibo, Flux 3 and Qwen 6.11., Flux 2 6.11. evening)

TABS: dict[str, TabSpec] = {
    "flux3": TabSpec(
        required=("flux3-image-klein-int8-convrot.safetensors", "qwen3vl_4b_int8_convrot.safetensors", _UPS),
        modes={
            "txt2img": ModeSpec(optional=(_UPSAMPLER,)),
            "outpaint": ModeSpec(requires=("Flux 3\\flux-3-image-klein-outpaint.safetensors",)),
            # SeedVR2 pre-cleaning is a switch that starts off: the mode runs without its files (they are optional and the
            # switch is greyed out while they are missing, user 30.10.)
            # 4x UltraSharp is on by default (user 2.11.), so it is a required file: without it Flux 3 would be locked
            "upscale": ModeSpec(requires=("Flux 3\\flux-3-image-klein-restore.safetensors", "4x-UltraSharpV2.safetensors"),
                                optional=("seedvr2_3b_int8_convrot.safetensors", "seedvr2_ema_vae_fp16.safetensors")),
            "refine": ModeSpec(),   # the edit graph with the picture rescaled to its own size: no files of its own
            "multi_edit": _CUT_OWN_LLM,      # no 9B fallback file in the list (user 6.11.)
            "sketch": _SKETCH,
            "scribble": _SKETCH,   # the tab Scribble on photo: the same workflow and files as Sketch (plan B)
        },
        optional=(_TAEF2,)),
    "flux2": TabSpec(
        required=("flux-2-klein-9b_int8_convrot.safetensors", "qwen_3_8b_fp8mixed.safetensors", _UPS),
        modes={
            "txt2img": ModeSpec(optional=("qwen3vl_4b_int8_convrot.safetensors",)),      # the prompt writer: Qwen3-VL 4B (user 6.11.; the Flux 3 upsampler before)
            "upscale": ModeSpec(requires=_ULTRA),
            "refine": ModeSpec(requires=_ULTRA),
            "multi_edit": _CUT_OWN_LLM,      # no 9B fallback file in the list (user 6.11.)
            "sketch": ModeSpec(requires=("qwen3vl_4b_int8_convrot.safetensors",), alone=True),   # its writer (10.11.)
            "scribble": ModeSpec(requires=("qwen3vl_4b_int8_convrot.safetensors",), alone=True),   # the tab Scribble on photo: the same workflow and files as Sketch (plan B)
        },
        optional=(_TAEF2,)),
    "qwen": TabSpec(
        required=("qwen_image_2.1_int8_convrot.safetensors", "qwen_image_2.1_vae_bf16.safetensors"),
        modes={
            "txt2img": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",), optional=("qwen3.5_9b_w4a8_gptq.safetensors",)),
            "edit": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "inpaint": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "outpaint": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "multi_edit": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",), optional=_CUT_OWN_LLM.optional),   # runs the edit graph; no 9B fallback file in the list (user 6.11.)
            "remove": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "upscale": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "refine": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors",)),
            "sketch": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors", _UPSAMPLER), alone=True),
            "scribble": ModeSpec(requires=("qwen3vl_8b_int8_convrot.safetensors", _UPSAMPLER), alone=True),   # the tab Scribble on photo: the same workflow and files as Sketch (plan B)
        },
        optional=("qwen\\qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors", "taeqi2_1_decoder.pth")),      # no 9B int8 fallback in the list (user 6.11.): Describe uses the w4a8 writer of Qwen Text to image
    "fibo": TabSpec(
        required=("fibo2_edit_turbo_int8_convrot.safetensors", "qwen3vl_4b_int8_convrot.safetensors", _UPS),
        modes={"multi_edit": _CUT_OWN_LLM,
               "upscale": ModeSpec(requires=("4x-UltraSharpV2.safetensors",))},      # "4x UltraSharp first" starts on (user 7.11.): a required file. Fibo describes with its own 4B writer (user 6.11.): the 9B file is not listed
        optional=(_TAEF2,)),
    "krea2": TabSpec(
        required=("krea2_turbo_int8_convrot.safetensors", "qwen3vl_4b_int8_convrot.safetensors", "qwen_image_vae.safetensors"),
        optional=("lighttaew2_1.safetensors",)),          # live preview of the Wan 2.1 latent; its own 4B writer describes (6.11.)
    "moss": TabSpec(
        required=("moss_image_sft_int8_convrot.safetensors", "qwen3.5_9b_w4a8_gptq.safetensors", "flux2-vae_small.safetensors"),
        # Text to image starts with the UltraReal LoRA on: a file the start values use is required (user 30.10.)
        modes={"txt2img": ModeSpec(requires=("Moss\\lenovo_moss.safetensors",))},
        optional=("Moss\\lora_dmd2.safetensors", _TAEF2)),      # its own required 9B writer describes (6.11.)
    # MiniMax H3 Image (PLAN 2.0b, user 10.11.): UNet w4a8, text encoder nvfp4, VAE; the prompt writer (Qwen 3.5 9B w4a8)
    # starts off, so it is optional
    "minimax": TabSpec(
        required=("minimax_h3_image_pruned_w4a8.safetensors", "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                  "minimax_h3_image_vae_fp16.safetensors"),
        modes={"txt2img": ModeSpec(optional=("qwen3.5_9b_w4a8_gptq.safetensors",)),
               "edit": ModeSpec(optional=("qwen3.5_9b_w4a8_gptq.safetensors",)),      # the same writer, with the official edit task prompt
               "multi_edit": ModeSpec(optional=("qwen3.5_9b_w4a8_gptq.safetensors",) + _CUT_OWN_LLM.optional)}),
}


def used_by(name: str) -> list[str]:
    """The models (keys, in the order of TABS) whose list names this file, as a required or optional one."""
    out = []
    for key, t in TABS.items():
        names = set(t.required) | set(t.optional)
        for ms in t.modes.values():
            names |= set(ms.requires) | set(ms.optional)
        if name in names:
            out.append(key)
    return out


def preview_decoder(key: str) -> str:
    """The live preview decoder (TAESD) of a model: "" when it has none."""
    t = TABS.get(key)
    return next((n for n in (t.optional if t else ()) if n in FILES and FILES[n].kind == "preview"), "")


def tab_required(key: str) -> tuple:
    """The files a whole tab needs (what ``models.Model.requires`` carries)."""
    return TABS[key].required if key in TABS else ()


def mode_extra(key: str, mode: str) -> tuple:
    t = TABS.get(key)
    return t.modes[mode].requires if t and mode in t.modes else ()


def mode_required(key: str, mode: str) -> tuple:
    """Everything one mode needs: the tab's files plus the mode's own."""
    return tab_required(key) + mode_extra(key, mode)


def mode_alone(key: str, mode: str) -> bool:
    """True when a missing file of this mode greys out only the mode (ModeSpec.alone), not the whole model."""
    t = TABS.get(key)
    return bool(t and mode in t.modes and t.modes[mode].alone)


def mode_optional(key: str, mode: str) -> tuple:
    t = TABS.get(key)
    if t is None:
        return ()
    return t.optional + (t.modes[mode].optional if mode in t.modes else ())


def mode_nodes(key: str, mode: str) -> tuple:
    t = TABS.get(key)
    return t.modes[mode].nodes if t and mode in t.modes else ()


# The "LLM" button under the prompt describes the picture with the text model the chosen model already uses (user 30.10.),
# so nobody downloads another one. Image input checked live 30.10. for all of these. The last one is the fallback.
DESCRIBE_WRITERS = {
    "fibo": ("qwen3vl_4b_int8_convrot.safetensors",),     # the prompt writer of Fibo 2 too (user 6.11.)
    "qwen": ("qwen3.5_9b_w4a8_gptq.safetensors",),
    "moss": ("qwen3.5_9b_w4a8_gptq.safetensors",),
    "flux2": ("qwen3vl_4b_int8_convrot.safetensors",),     # the Flux 2 prompt writer too (user 6.11.)
    "flux3": ("qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors",),
    "krea2": ("qwen3vl_4b_int8_convrot.safetensors",),     # the same file as Fibo and Flux 3 (user 6.11.; Krea 2 used the fp8 file before)
    "minimax": ("qwen3.5_9b_w4a8_gptq.safetensors",),     # its prompt writer (PLAN 2.0b)
}


def describe_writers(model_key: str) -> tuple[str, ...]:
    """The text model files that can describe a picture for this model, best first (its own writer, then the fallback)."""
    own = DESCRIBE_WRITERS.get(model_key, ())
    return own + tuple(n for n in (DESCRIBE_FALLBACK,) if n not in own)


DESCRIBE_NAMES = {            # short names for the line in the settings
    "qwen3.5_9b_int8_convrot.safetensors": "Qwen 3.5 9B int8 ConvRot",
    "qwen3.5_9b_w4a8_gptq.safetensors": "Qwen 3.5 9B w4a8 GPTQ",
    "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors": "Flux 3 prompt upsampler (Qwen 3.5 9B)",
    "qwen3vl_4b_int8_convrot.safetensors": "Qwen3-VL 4B int8 ConvRot",
}


# What the optional files are for, as a short phrase for the heading "Needed for additional features (...)" (user 6.11.)
FEATURE_USE = {
    "taef2_decoder.pth": "live preview",
    "taeqi2_1_decoder.pth": "live preview",
    "lighttaew2_1.safetensors": "live preview",
    DESCRIBE_FALLBACK: "LLM button, Describe",
    "qwen3.5_9b_flux3_prompt_upsampler_w4a8.safetensors": "LLM prompt enhancement, Sketch",
    "qwen3.5_9b_w4a8_gptq.safetensors": "LLM prompt enhancement",
    "qwen3vl_4b_int8_convrot.safetensors": "LLM prompt enhancement, Describe, Sketch",     # optional only at Flux 2
    "birefnet.safetensors": "Cut out, remove background",
    "rmbg-2.0.safetensors": "Remove background (second model)",
    "qwen\\qwen_image_2.1_turbo_lora_avg_rank_178_bf16.safetensors": "Turbo LoRA",
    "Moss\\lora_dmd2.safetensors": "Turbo LoRA",
    "seedvr2_3b_int8_convrot.safetensors": "SeedVR2 pre-cleaning",
    "seedvr2_ema_vae_fp16.safetensors": "SeedVR2 pre-cleaning",
}


def feature_uses(names) -> str:
    """The distinct purposes of these optional files, in order, joined with commas ("live preview, LLM button, Describe")."""
    out: list[str] = []
    for n in names:
        for part in FEATURE_USE.get(n, "").split(", "):
            if part and part not in out:
                out.append(part)
    return ", ".join(out)


def describe_line(model_key: str, has) -> str:
    """The line in a model's settings tab: which text model the LLM button and the reference pictures of Multi Image Edit
    use, and the fallback. `has(name)` says whether ComfyUI lists the file."""
    short = lambda n: DESCRIBE_NAMES.get(n, n) + ("" if has(n) else " (missing)")  # noqa: E731
    own = DESCRIBE_WRITERS.get(model_key, (DESCRIBE_FALLBACK,))[0]
    head = f"Text model for the LLM button and for Describe in Multi Image Edit: {short(own)}."
    if own == DESCRIBE_FALLBACK:
        return head + " It is also used instead when the text model of another model is missing."
    return head + f" If it is missing, {short(DESCRIBE_FALLBACK)} is used instead."


# GGUF weights as an alternative to the main model file (user 5.11.): only a link to the Hugging Face page, shown under the
# model's weights in the settings window. GGUF files link like any other file (the chain symbol) and need ComfyUI-GGUF.
# model key -> page. The files tested by the user: Krea 2 Q3_K_M (vantagewithai), Fibo Q5_K_M (Abiray), Flux 2 Klein Q4_K_M.
GGUF_PAGES = {
    "krea2": "https://huggingface.co/vantagewithai/Krea-2-Turbo-GGUF",
    "fibo": "https://huggingface.co/Abiray/Fibo-2.0-edit-turbo-GGUF",
    "flux2": "https://huggingface.co/unsloth/FLUX.2-klein-9B-GGUF",
}

# node class prefix -> (pack, where to get it). Only what the shipped workflows use.
NODE_PACKS = (
    ("SeedVR2", "ComfyUI itself (SeedVR2 nodes): update ComfyUI", "https://github.com/comfyanonymous/ComfyUI"),
    ("ColorMatch", "ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes"),      # Flux 3 Upscale, Flux 2 and Fibo Upscale tiles: colours back to your picture
    ("GrowMaskWithBlur", "ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes"),
    ("MaskBoundingBox+", "ComfyUI_essentials", "https://github.com/cubiq/ComfyUI_essentials"),
)


def node_pack(cls: str) -> tuple[str, str] | None:
    for prefix, pack, url in NODE_PACKS:
        if cls.startswith(prefix):
            return pack, url
    return None


# Shown in the settings overlay (credits stay mandatory, see CLAUDE.md "Release 1 scope").
CONTRIBUTORS = (
    ("Peszemeszek", "photocraft-comfyui-bridge, the upstream this plugin is forked from (MIT OR Apache-2.0)", "https://github.com/Peszemeszek/photocraft-comfyui-bridge"),
    ("ComfyUI", "the node-based engine behind every generation", "https://github.com/comfyanonymous/ComfyUI"),
    ("Comfy-Org", "ComfyUI-ready model files: Qwen Image 2.1, Qwen3-VL, FLUX.2, MOSS-Image, SeedVR2, Fibo 2.0, MiniMax H3 Image", "https://huggingface.co/Comfy-Org"),
    ("Black Forest Labs", "FLUX.2 Klein and FLUX.3 Klein", "https://huggingface.co/black-forest-labs"),
    ("Qwen team (Alibaba)", "Qwen Image 2.1 and the Qwen text encoders", "https://huggingface.co/Qwen"),
    ("Bria", "Fibo 2.0 Edit, the VGL prompt format and RMBG-2.0 (second model of the Remove background scissors)", "https://huggingface.co/briaai/RMBG-2.0"),
    ("OpenMOSS", "MOSS-Image", "https://huggingface.co/OpenMOSS-Team"),
    ("Krea", "Krea 2 Turbo", "https://www.krea.ai"),
    ("MiniMax", "MiniMax H3 Image (MiniMax-H3-Image Community License Agreement)", "https://huggingface.co/MiniMaxAI/MiniMax-H3-Image"),
    ("ausboss", "the FLUX.3 Klein Restore and Outpaint LoRAs", "https://huggingface.co/ausboss"),
    ("lodestones", "MOSS-Image 8-step DMD2 LoRA", "https://huggingface.co/lodestones"),
    ("kianxyzw", "ComfyUI Model Linker, the model of the \"similar name\" hint under a missing file (MIT)", "https://github.com/kianxyzw/comfyui-model-linker"),
    ("ThetaCursed", "Krea2-Style-Explorer, the style prompts of the Styles button (MIT)", "https://github.com/ThetaCursed/Krea2-Style-Explorer"),
)
