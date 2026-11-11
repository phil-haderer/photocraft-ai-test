"""The models the window offers as tabs, and what each of them can do.

A tab is a model; below it only the modes that work well with it are enabled. Each mode names the workflow that runs it and
the settings it starts with (the same keys a preset saves). What a model can do comes from live tests; see the project
notes ("plugin-erfahrungen"): add a mode here once it has been tried.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PLACEHOLDER = "<DESCRIBE THE IMAGE>"


@dataclass(frozen=True)
class Mode:
    workflow: str
    settings: dict = field(default_factory=dict)
    prompt_hint: str = ""           # what an empty prompt field starts with in this mode
    prompts: tuple = ()             # (label, text, tip): ready-made prompts, shown as radio buttons next to "Prompt"
    prompt_tip: str = ""            # an orange hint under the prompt field in this mode (the field gets an orange frame)
    run_as: str = ""                # the mode the bridge runs when it is another one (Fibo "Refine" runs as a whole-image edit)
    remove_text: bool = False       # Remove Selection: the field stays usable and takes an optional name of the object ("the dog")
    describe: bool = False          # Expand with Krea 2 / MOSS: a prompt is required, the Describe button under the field writes one
    steps_tip: str = ""             # the tooltip of the Steps field in this mode ("" = none)
    max_scale: float = 0.0          # Upscale: the largest factor this model is offered for (0 = all four; the others are greyed out)
    stage_row: bool = False         # Upscale: its stages sit in one row between "Upscale factor" and "Refine" (grey while Refine is on)


@dataclass(frozen=True)
class Model:
    key: str
    label: str
    tip: str
    modes: dict                     # mode key -> Mode (a mode that is not here is greyed out)
    max_refs: int = 0               # Multi Image Edit: how many reference-image slots this model takes (0 = none)
    tag_style: str = ""             # Multi Image Edit: how this model names an image in the prompt; {n} counts from 1 (the picture
                                    # is image 1, the first reference image 2), {i} from 0 ("" = no names)
    requires: tuple = ()            # model detection: the model files this tab needs (file names, as ComfyUI lists them); () = not set yet
    ref_side: int = 1024            # Multi Image Edit: the longest side of a reference image sent to the model (user 4.11.; Flux 3 as its picture)
    bbox: bool = False              # Multi Image Edit: the BBOX switch (the selection becomes <obj_1>, see bridge.BBOX_SENTENCE); Flux 3 only
    seam: str = "off"               # seam correction in Fill / Remove / Expand: "on" always (one corrected layer), "off" never
                                    # (user 29.10.: Fibo on, the others off; the A/B checkbox was removed 1.11., Qwen fixed off)

    def workflows(self) -> list[str]:
        out = []
        for m in self.modes.values():
            if m.workflow not in out:
                out.append(m.workflow)
        return out


_SOFT = {"layer_mask": "soft", "mask_grow": 8, "mask_blur": 8}

# Refine / Upscale (Flux 2 and 3 Klein): the field holds the WHOLE prompt and starts with what the workflow sends by default;
# describing the picture in front of it helps. Flux 2 also offers relight prompts (live tested).
FLUX2_DEFAULT = "A sharp, natural photograph of the same scene: clean detail and texture, true-to-life colors, soft natural light. Keep the composition and colors exactly as they are."
FLUX2_DEFAULT_PREV = "A sharp, natural photograph of the same scene: clean detail and texture, true-to-life colors, soft natural light. Keep the composition, and colors exactly as they are."
FLUX2_DEFAULT_OLD = "A sharp, natural photograph of the same scene: clean detail and texture, true-to-life colors, soft natural light. Keep the composition, people, faces and colors exactly as they are."
# Fibo Upscale (provisional, 6.11.): FLUX2_DEFAULT ("true-to-life colors, soft natural light") coloured an old sepia photo in the first trial;
# this text names no colour or light, only sharpness (docs/tests/fibo-upscale-ergebnis.md; more prompts follow in the next test round)
FIBO_UPSCALE_DEFAULT = "A sharp, high-resolution version of the same photograph: clean detail and texture. Keep the composition, the subjects, the colors and the light exactly as they are."
FLUX3_DEFAULT = "Restore the photo: remove blur, noise and compression artifacts and recover sharp, natural detail, keeping the same composition and colors."
RELIGHT_NEUTRAL = "A crystal-clear, high-fidelity photograph of the subject captured under perfectly neutral, even lighting. The scene utilizes soft global illumination to eliminate harsh shadows and high contrast, resulting in a balanced, flat-field exposure. The white balance is calibrated to 5500K (daylight neutral), ensuring absolutely accurate, true-to-life colors with no warm or cool color casts. Photographed with a Sony A7R V using a 55mm f/8 lens for maximum sharpness from edge to edge and zero distortion. The aesthetic is objective, documentary-style, and ultra-realistic. 8k resolution, clean ISO 100, raw output. Remove watermarks and checkerboard patterns."
RELIGHT_STUDIO = "Transform the image into a professionally lit studio portrait with soft, diffused lighting. Remove harsh sunlight, strong contrast, and directional shadows."
FLUX2_REFINE_PROMPTS = (
    ("Default", FLUX2_DEFAULT, "The workflow's own prompt: a sharp, natural photograph of the same scene."),
    ("Neutral", RELIGHT_NEUTRAL, "Relight: soft, even, neutral light without harsh shadows, true-to-life colours."),
    ("Studio portrait", RELIGHT_STUDIO, "Relight: a professionally lit studio portrait with soft, diffused light."),
)
FLUX3_RESTORE = "Restore this old photo: remove scratches, white lines, dust, folds and stains, and bring back sharp facial detail. Keep the people, their faces, their expressions, their poses and the framing exactly unchanged."   # after Pixaroma's "Restore and Colorize" (wording agreed with the user 1.11.)
FLUX3_REFINE_PROMPTS = (
    ("Default", FLUX3_DEFAULT, "The workflow's own prompt: restore sharp, natural detail."),
    ("Restore", FLUX3_RESTORE, "Repair an old or damaged photo: scratches, dust, folds and stains go, faces get their detail back."),
)
# Qwen Image 2.1 Upscale and Refine (workflow qwen212KUpscale_v10): the generic prompt of the workflow is the standard setting (user 2.11.: perfect)
QWEN_UPSCALE_DEFAULT = "Enhance this image to high resolution while preserving the original composition, lighting, and atmosphere. Image can be illustration or real photo, keep the original input style."
FIBO_REFINE = "relight the scene to natural lighting"   # Fibo Refine's old prompt (now FLUX2_DEFAULT, user 28.10.); kept as a stock text
FILL_TIP = "Draw a selection and prompt e.g. “add a red flower”. Always hide the layers of previous results before running again."   # wording from the user (3.11.)
QWEN_SMALL = "Small selections don't work well with Qwen."   # user 30.10.: small fills came out shifted (helikopter.psd)
REMOVE_NAME_TIP = "Name what to remove (e.g. “car”)."
REMOVE_AGAIN = "If the first try doesn't work, try removing it a second time."   # idea of the user (28.10.), for all models since 3.11.
REMOVE_TIP = REMOVE_NAME_TIP + " " + REMOVE_AGAIN
MULTI_TIP = "Example: “Place the bag from {tag} on the table.” Cut out the object first."   # {tag}: the model's name for reference image 1 (user 3.11.)
EDIT_TIP = "Describe the result: “Replace the laptop with a book.” or “Remove the sitting person.”"   # user 3.11., the same for every model
# Krea 2 / MOSS Expand (wording chosen by the user 29.10.; A/B test docs/tests/krea-moss-expand-ab.md)
EXPAND_DESCRIBE_TIP = ("This model needs a prompt: describe the surroundings only (place, light, style), not the main subject. "
                       "Describe writes one for you.")
DESCRIBE_TIP = "Add a short description of your image in front of the default prompt for better results."   # Upscale, every model (user 3.11.)
REFINE_TIP = "Refine keeps the size and redraws fine detail. " + DESCRIBE_TIP   # Refine, every model (user 3.11.)
T2I_TIP = "A new image is added to the canvas."   # user 3.11.
FLUX3_DEFAULT_OLD = "Restore the photo: remove blur, noise and compression artifacts and recover sharp, natural detail, keeping the same composition, people and colors."
# Sketch (docs/sketch-plan.md; tab "Sketch" under Edit): the whole prompt stands in the field and can be edited (user 10.11.); the
# user replaces SKETCH_MARK with what the sketch shows. Left in, the bridge turns it into the generic sentence
# (bridge.sketch_text). The wordings are the ones of the blind test rounds 1 to 7 (docs/tests/sketch-ergebnis.md): Photo,
# the animated-film look without "expressive faces" (round 3b) and Scribble on photo (rounds 5 to 7).
SKETCH_MARK = "<WHAT IT SHOWS>"
SKETCH_PHOTO = ("Turn this sketch of " + SKETCH_MARK + " into a realistic photograph. Keep the composition, the shapes and the "
                "proportions of the drawing exactly. Natural light, real materials, no drawing lines left.")
SKETCH_ILLUSTRATION = ("Turn this sketch of " + SKETCH_MARK + " into a still from a classic hand-drawn animated film: clean "
                       "outlines, soft cel shading, warm colours. Keep the composition and the shapes of the drawing.")
SKETCH_SCRIBBLE = ("Replace the coloured scribbles with " + SKETCH_MARK + ", realistic and matching the light and perspective of "
                   "the photo. Remove every scribble line and keep everything else unchanged.")
SCRIBBLE_LABEL = "Scribble on photo"     # the template that finds the scribble and changes only the place around it (scribble.py)
SKETCH_PROMPTS = (
    ("Photo", SKETCH_PHOTO, "The whole sketch becomes a realistic photograph."),
    ("Illustration", SKETCH_ILLUSTRATION, "The whole sketch becomes a hand-drawn animated-film picture."),
    (SCRIBBLE_LABEL, SKETCH_SCRIBBLE, "Scribbles on a photo become real objects; only the place around them changes."),
)
SCRIBBLE_MODE = "scribble"      # the window mode of the tab Scribble on photo (plan B, 10.11.: its own tab under Edit)
SCRIBBLE_PROMPTS = ((SCRIBBLE_LABEL, SKETCH_SCRIBBLE, "Scribbles on a photo become real objects; only the place around them changes."),)
# Sketch to image: its styles come from Styles (styles.json, mode "sketch"); the two tested ones keep the template texts word
# for word (Realistic photo = SKETCH_PHOTO, Animated film = SKETCH_ILLUSTRATION). An empty field shows this in grey and does not run.
# The frame sentences of the styles of Edit canvas and Sketch to image ({look} = a style's look, tools/styles-looks.json; the
# same frames as the style pilot, tests/live_style_round.py; tools/build_style_looks.py writes the texts into styles.json).
EDIT_FRAME = "Transform this image into {look}. Keep the composition, the subjects and their positions."
SKETCH_FRAME = "Turn this sketch of " + SKETCH_MARK + " into {look}. Keep the composition and the shapes of the drawing."
SKETCH_PLACEHOLDER = "Choose a style under Styles"
NO_STYLE = "Choose a style under Styles, or type a prompt."
SKETCH_TIP = ("Replace " + SKETCH_MARK + " with what the sketch shows, with its surroundings: "
              "“a house and a road in a green summer meadow”.")
WRITTEN_TIP = "Loaded the written prompt: it runs as it is, without the prompt writer. Choose a style or a template to start fresh."   # Sketch after the history (user 10.11.)
SCRIBBLE_TIP = ("Scribble in bright red or green, or on its own layer. Replace " + SKETCH_MARK + " with what goes there: "
                "“a red vintage car”.")
NO_SCRIBBLE = "No scribble found. Scribble in bright red or green, or on its own layer."
# The system prompt of Flux 2's Sketch writer (qwen3vl 4B, node 402 of flux2-klein-sketch.json): an edit instruction, not a
# caption; the sketch part is neutral so Illustration stays an illustration (writer round on PC A, 10.11.: Photo and
# Illustration 7/7; docs/tests/sketch-schreiber-ergebnis.md). Flux 3 and Qwen keep BFL's upsampler.
SKETCH_WRITER_SYSTEM = (
    "You write the edit instruction for an image editing model. You get a picture and a short request. Write ONE clear "
    "English instruction that starts with a verb. If the picture carries rough coloured scribble lines: say where they "
    "are (which part of the picture, what they lie on) and what replaces them exactly there; name the new object with "
    "its look, material, colour, size and pose, matching the light, perspective and style of the photo; the scribble "
    "lines must be gone and everything else stays unchanged. If the picture is a sketch or drawing: say to turn it into "
    "the finished picture in the look the request asks for (a realistic photograph, a still from an animated film or "
    "another style) and name each element of the drawing with its colour, material and place, keeping the composition, "
    "shapes and proportions exactly, with no sketch lines left unless the look has outlines. Output only the instruction "
    "as one block of prose, 60 to 150 words, with no lists, Markdown or explanations.")
SKETCH_MODE = "sketch"      # the window mode of the tab; it runs as a whole-image edit
SCRIBBLE_PREFIX = "Replace the coloured scribbles"


EDIT_TABS_VERSION = 2       # saved with every run and page since plan B (10.11.): Scribble on photo has its own tab


def legacy_sketch_mode(mode: str, prompt: str, version=None) -> str:
    """Before plan B (10.11.) Scribble on photo was a template of the tab Sketch: a run or page saved before (no
    ``edit_tabs`` version) in mode "sketch" whose prompt is the scribble sentence belongs to the tab Scribble on photo now."""
    old = version is None and mode == SKETCH_MODE and str(prompt).lstrip().startswith(SCRIBBLE_PREFIX)
    return SCRIBBLE_MODE if old else mode
STOCK_PROMPTS = {FIBO_UPSCALE_DEFAULT, FLUX2_DEFAULT_PREV, FLUX2_DEFAULT_OLD, FLUX3_DEFAULT_OLD, PLACEHOLDER, FLUX2_DEFAULT, FLUX3_DEFAULT, FLUX3_RESTORE, QWEN_UPSCALE_DEFAULT, RELIGHT_NEUTRAL, RELIGHT_STUDIO, FIBO_REFINE,
                 SKETCH_PHOTO, SKETCH_ILLUSTRATION, SKETCH_SCRIBBLE}   # texts the window may replace when the mode changes

# The tooltips of the function buttons: one general text per function, the same for every model (user 28.10.); what
# holds for one model only goes into its tip under the prompt (Mode.prompt_tip). No ranking in it (user 3.11.).
FUNCTION_TIPS = {
    "inpaint": "Select an area, type what should appear there, then Generate.",
    "remove": "Select the object (whole object inside), then Generate. Text is optional: name what to remove (\"the dog\").",
    "multi_edit": ("Edit the picture with reference images in the slots below (drop, paste or add files). "
                   "Name them in the text by their tags. The whole picture changes; a selection is ignored."),
    "outpaint": ("Extend the canvas with the Crop tool (Enter) and fill the new area white, then Generate.\n"
                 "Text is optional; an empty prompt often works best. Expand large areas in small steps."),
    "edit": "Changes the whole picture from your text (\"make it night\"). A selection is ignored.",
    "img2img": "Reworks the picture (or selection) from your text.",
    "upscale": "Enlarges the whole picture into a NEW document, up to 16 MP. A selection is ignored.",
    "refine": "Cleans up the whole picture at the same size, as a new layer. A selection is ignored.",
    "txt2img": "New picture from text only, as a new layer. A selection is ignored.",
    "sketch": "Turns a sketch on the canvas into a picture in the style you choose under Styles. A selection is ignored.",
    "scribble": "Turns coloured scribbles on a photo into real objects; only the place around them changes. A selection is ignored.",
}

QWEN = Model(
    "qwen", "Qwen Image 2.1",
    "Qwen Image 2.1 Edit: instruction editor, best at Fill Selection, Remove Selection and Expand. Base res. 1024 works best.",
    {
        "txt2img": Mode("qwen-image-21-t2i.json", dict(native=True, base_res=1024, turbo=False, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),   # LLM off like the others (user 30.10.)
        "edit": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=False, layer_mask="none"), prompt_tip=EDIT_TIP),
        "multi_edit": Mode("qwen-image-21-edit.json", dict(base_res=1024, turbo=False, layer_mask="none"), prompt_tip=MULTI_TIP, run_as="edit"),
        "sketch": Mode("qwen-image-21-sketch.json", dict(base_res=1024, turbo=False, layer_mask="none", enhance=True), prompt_tip=SKETCH_TIP, run_as="edit"),   # Sketch to image: a style from Styles (plan B, 10.11.)
        "scribble": Mode("qwen-image-21-sketch.json", dict(base_res=1024, turbo=False, layer_mask="none", enhance=True), SKETCH_SCRIBBLE, SCRIBBLE_PROMPTS, SCRIBBLE_TIP, run_as="edit"),   # its own tab (plan B)
        # soft: opaque over the selection, fading out to the crop's side (Bridge: soft_layer_mask; Fill mask test round 30.10.)
        "inpaint": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=False, feather_pct=4.0), prompt_tip=FILL_TIP + " " + QWEN_SMALL),
        "outpaint": Mode("qwen-image-21-edit.json", dict(base_res=1024, context=0.4, turbo=False, layer_mask="soft")),   # soft mask: only the new area (+ overlap) is returned, the original stays untouched (user 4.11.); Context 40 %
        "remove": Mode("qwen-image-21-edit.json", dict(_SOFT, base_res=1024, context=0.4, turbo=False, feather_pct=10.0), prompt_tip=REMOVE_TIP, remove_text=True),
        # native 2K upscale: no upscaler node and no LoRA, 25 steps; the result is about the scale factor times the picture, up to 16 MP
        "upscale": Mode("qwen-image-21-upscale.json", dict(scale=1.5, turbo=False, context=0.0), QWEN_UPSCALE_DEFAULT, prompt_tip=DESCRIBE_TIP),
        # the upscale graph at the size of the canvas (factor 1), with the Turbo LoRA as a switch (own file so Upscale stays
        # as it is)
        "refine": Mode("qwen-image-21-refine.json", dict(turbo=False, context=0.0), QWEN_UPSCALE_DEFAULT, prompt_tip=REFINE_TIP),
    },
    requires=(
        "qwen_image_2.1_int8_convrot.safetensors",
        "qwen_image_2.1_vae_bf16.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=8, tag_style="<image{n}>")

FLUX2 = Model(
    "flux2", "Flux 2 Klein Edit",
    "FLUX.2 Klein 9B: text to image, whole-image edits, Fill Selection, Remove Selection, Expand, Upscale, Refine.",
    {
        "txt2img": Mode("flux2-klein-t2i.json", dict(native=True, base_res=1024, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),
        "edit": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="none"), prompt_tip=EDIT_TIP),
        "multi_edit": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="none"), prompt_tip=MULTI_TIP, run_as="edit"),
        "sketch": Mode("flux2-klein-sketch.json", dict(base_res=1024, layer_mask="none", enhance=True), prompt_tip=SKETCH_TIP, run_as="edit"),   # Sketch to image: a style from Styles (plan B, 10.11.)
        "scribble": Mode("flux2-klein-sketch.json", dict(base_res=1024, layer_mask="none", enhance=True), SKETCH_SCRIBBLE, SCRIBBLE_PROMPTS, SCRIBBLE_TIP, run_as="edit"),   # its own tab (plan B)
        # Fill (user 10.11.): the way its Remove runs, the edit graph with the red outline and the start values of Remove,
        # the wording bridge.FILL_PROMPT_NATURAL (Flux Fill round 2: 8 of 8 good; docs/tests/fill-flux-ergebnis.md)
        "inpaint": Mode("flux2-klein-edit.json", dict(_SOFT, base_res=1024, context=0.4, feather_pct=10.0), prompt_tip=FILL_TIP),
        "remove": Mode("flux2-klein-edit.json", dict(_SOFT, base_res=1024, context=0.4, feather_pct=10.0), prompt_tip=REMOVE_TIP, remove_text=True),
        "outpaint": Mode("flux2-klein-edit.json", dict(base_res=1024, layer_mask="soft")),   # soft mask: only the new area is returned (user 4.11.)
        # Upscale with the stage "Tiles", on at the start (user 10.11.; upscale stage round: 2 of 3 good with tiles, 0 of 3 without);
        # Refine keeps the graph without tiles as its own file, unchanged
        "upscale": Mode("flux2-klein-upscale.json", dict(scale=1.5, turbo=True, context=0.0), FLUX2_DEFAULT, prompt_tip=DESCRIBE_TIP, stage_row=True),
        "refine": Mode("flux2-klein-refine.json", dict(turbo=True, context=0.0), FLUX2_DEFAULT, FLUX2_REFINE_PROMPTS, REFINE_TIP),
    },
    requires=(
        "flux-2-klein-9b_int8_convrot.safetensors",
        "qwen_3_8b_fp8mixed.safetensors",
        "flux2-vae.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=3, tag_style="image {n}", seam="off")

FLUX3 = Model(
    "flux3", "Flux 3 Klein Edit",
    "FLUX.3 Klein: text to image, whole-image edits, Remove Selection, Expand, Upscale, Refine.",
    {
        "txt2img": Mode("flux3-klein-t2i.json", dict(native=True, base_res=1536, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),
        "edit": Mode("flux3-klein-edit.json", dict(base_res=1536, layer_mask="none"), prompt_tip=EDIT_TIP),
        "multi_edit": Mode("flux3-klein-edit.json", dict(base_res=1536, layer_mask="none"), prompt_tip=MULTI_TIP, run_as="edit"),
        "sketch": Mode("flux3-klein-sketch.json", dict(base_res=1536, layer_mask="none", enhance=True), prompt_tip=SKETCH_TIP, run_as="edit"),   # Sketch to image: a style from Styles (plan B, 10.11.)
        "scribble": Mode("flux3-klein-sketch.json", dict(base_res=1536, layer_mask="none", enhance=True), SKETCH_SCRIBBLE, SCRIBBLE_PROMPTS, SCRIBBLE_TIP, run_as="edit"),   # its own tab (plan B)
        "remove": Mode("flux3-klein-edit.json", dict(_SOFT, base_res=1536, context=0.4, feather_pct=10.0), prompt_tip=REMOVE_TIP, remove_text=True),
        # Expand: its own graph with ausboss' outpaint LoRA (29.10., after Pixaroma's "14. Flux 3 Klein - Outpaint"; without
        # it Flux 3 slid or zoomed the picture instead of filling the margin): grey margin, ~1 megapixel, Context 1.0 (confirmed 4.11.)
        "outpaint": Mode("flux3-klein-outpaint.json", dict(base_res=1024, context=1.0, layer_mask="soft")),   # Context 100 % fits (user 4.11. evening); soft mask: only the new area is returned
        "upscale": Mode("flux3-klein-upscale.json", dict(scale=1.5, turbo=True, stage_on=False, stage2_on=True, context=0.0, detail=0.7), FLUX3_DEFAULT, prompt_tip=DESCRIBE_TIP),
        "refine": Mode("flux3-klein-refine.json", dict(turbo=False, context=0.0), FLUX3_DEFAULT, FLUX3_REFINE_PROMPTS, REFINE_TIP),
    },
    requires=(
        "flux3-image-klein-int8-convrot.safetensors",
        "qwen3vl_4b_int8_convrot.safetensors",
        "flux2-vae.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=3, tag_style="<ref_image_{i}>", seam="off", bbox=True, ref_side=1536)   # with BBOX ticked only one (refslots.BBOX_MAX_REFS)

# MOSS: the DMD2 speed LoRA (8 steps, CFG 1.5) is the model's own LoRA; the Lenovo UltraReal LoRA and the skip-layer
# guidance (SLG) are switches that start on (best result in the live tests); the LLM prompt enhancer starts off.
_MOSS = dict(turbo=True, stage_on=True, stage2_on=False, stage3_on=False)     # the stages of moss-image-t2i.json: UltraReal (on), skip-layer guidance (off)
MOSS_STEPS_TIP = "Turn up the steps to 35 for best results."     # wording of the user (29.10.), 35 after the CFG test
_MOSS_INPAINT = {"turbo": False, "stage_on": True, "stage2_on": False, "base_res": 1216, "layer_mask": "soft", "mask_grow": 8, "mask_blur": 16,
                 "context": 1.0}      # 0.4 gave the model too little surroundings (user test 1.11.: Fill did not fit the picture)
MOSS = Model(
    "moss", "MOSS Image",
    "MOSS-Image: text to image.",
    {
        # Text to image starts without DMD2 and without SLG, no LLM: the user's live test 29.10. (with DMD2 or SLG the photos
        # looked artificial, with the LLM prompt too). Without DMD2 the workflow runs 25 steps at CFG 3.0 (35 was the blind-test winner, 25 is the default since 2.11.) (pc_no_lora; blind
        # test docs/tests/moss-cfg.md)
        "txt2img": Mode("moss-image-t2i.json", {**_MOSS, "turbo": False, "native": True, "base_res": 1280,
                                                "layer_mask": "none", "enhance": False},
                        prompt_tip=T2I_TIP, steps_tip=MOSS_STEPS_TIP),
    },
    requires=(
        "moss_image_sft_int8_convrot.safetensors",
        "qwen3.5_9b_w4a8_gptq.safetensors",
        "flux2-vae_small.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=3, tag_style="image {n}", seam="off")

# Krea-2 Turbo: a fast distilled text-to-image model (8 steps, CFG 1). Text to image has the model's own prompt enhancer
# (starts off, like the other models').
KREA2 = Model(
    "krea2", "Krea 2 Turbo",
    "Krea-2 Turbo: fast text to image.",
    {
        "txt2img": Mode("krea2-turbo-t2i.json", dict(native=True, base_res=1024, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),
    },
    requires=(
        "krea2_turbo_int8_convrot.safetensors",
        "qwen3vl_4b_int8_convrot.safetensors",
        "qwen_image_vae.safetensors",
    ))   # the model files this tab needs (details per mode: manifest.py)

# Expand with Krea 2 and MOSS was switched off (user 29.10.; MOSS came back 1.11. with the Inpainting v10 recipe, see MOSS above): in a blind test with the user's own pictures
# (docs/tests/expand-seam-testrunde.md) only 2 of 64 Krea 2 and 10 of 64 MOSS results were good, also with a description
# of the surroundings, a wider overlap, the seam correction or a second run over the border. The modes are kept here,
# with the Describe button they used, so they can come back when a better recipe exists (idea: Krea 2 AnyPaint LoRA).
PARKED_EXPAND = {
    "krea2": Mode("krea2-turbo-inpaint.json", dict(base_res=1024, layer_mask="soft"),
                  prompt_tip=EXPAND_DESCRIBE_TIP, describe=True),
    "moss": Mode("moss-image-inpaint.json", _MOSS_INPAINT, prompt_tip=EXPAND_DESCRIBE_TIP, describe=True),   # Inpainting v10 with the plugin's cut-out
}
# their graph files stay in the workflows folder but are not offered in the Workflow list: picked there they counted as a
# workflow of your own ("Image -> image" appeared, user 29.10.)
PARKED_WORKFLOWS = {m.workflow for m in PARKED_EXPAND.values()}   # (moss-image-inpaint-v10.json deleted 10.11.; in git history)

FIBO = Model(
    "fibo", "Fibo 2.0 Edit Turbo",
    "Instruction editor with all edit functions.",
    {
        "txt2img": Mode("fibo2-t2i.json", dict(native=True, base_res=1224, layer_mask="none", enhance=False), prompt_tip=T2I_TIP),   # Sharpen 0 % (user 5.11.; was 20 % since 28.10.)
        "edit": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False), prompt_tip=EDIT_TIP),
        "multi_edit": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False), prompt_tip=MULTI_TIP, run_as="edit"),
        "sketch": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False), prompt_tip=SKETCH_TIP, run_as="edit"),   # no writer (sketch round 2: best without)   # Sketch to image: a style from Styles (plan B, 10.11.)
        "scribble": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False), SKETCH_SCRIBBLE, SCRIBBLE_PROMPTS, SCRIBBLE_TIP, run_as="edit"),   # its own tab (plan B)
        "refine": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="none", enhance=False, sharpen=0.1), FLUX2_DEFAULT, run_as="edit",
                       prompt_tip=REFINE_TIP),   # Sharpen 10 % (final, user 31.10.)
        # Upscale (6.11.): Fibo draws the picture anew at the larger size (the user's Fibo2_turbo_edit_2K-ROPE workflow); 8 steps; up to
        # 3x since 10.11. (upscale stage round: 3x 4 of 4 good, 4x 2 of 4 with made-up writing once, so 4x stays grey; docs/tests/upscale-stufen-ergebnis.md)
        # Prompt C (the Qwen upscale text) is the standard since 7.11. (rounds 3 and 4: truest to the original); the stage "4x UltraSharp first"
        # starts on (best at 1.5x and 2x), "Tiles" is a second stage that excludes it; above 3 MP the result is made in tiles by itself (auto_on_above_mp)
        "upscale": Mode("fibo2-upscale.json", dict(scale=1.5, layer_mask="none", enhance=False, context=0.0), QWEN_UPSCALE_DEFAULT, prompt_tip=DESCRIBE_TIP, max_scale=3.0,
                        stage_row=True),   # the stages in one row of the Upscale / Refine box (8.11.; Fibo first, the others after test round 2.3/1)
        "inpaint": Mode("fibo2-edit.json", dict(base_res=1024, context=0.1, layer_mask="soft", feather_pct=10.0, enhance=False), prompt_tip=FILL_TIP),   # Context 0.1 chosen by the user 1.11. (was 0.4 from the test round 28.10.); Edge feather 10 % stays
        "outpaint": Mode("fibo2-edit.json", dict(base_res=1024, context=1.0, layer_mask="soft", enhance=False)),   # Context 100 %: with 40 % Fibo saw mostly the white margin and drew bars (user 4.11.); soft mask: only the new area is returned
        "remove": Mode("fibo2-edit.json", dict(base_res=1024, layer_mask="soft", feather_pct=10.0, enhance=False), prompt_tip=REMOVE_TIP, remove_text=True),
    },
    requires=(
        "fibo2_edit_turbo_int8_convrot.safetensors",
        "qwen3vl_4b_int8_convrot.safetensors",
        "flux2-vae.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=2, tag_style="<image_{n}>", seam="on")

# MiniMax H3 Image (PLAN 2.0b, docs/plan-minimax-h3-image.md; Release 1): distilled, 6 steps, CFG 1, no negative prompt; it
# works on about 4 to 20 MP. Text to image draws the area of the size row (gen_mp) in the canvas' aspect ratio; without the
# tick "Downsize to canvas" the result opens as a new document in that size (user 10.11.), with it it becomes a layer scaled
# down to the canvas (the official min_generation_area rule). The prompt writer (Qwen 3.5 9B with the official task prompt)
# starts off. 4 MP is the start until step 1 of the plan has measured the times.
GEN_MP_STEPS = (4, 8, 12, 16, 20)       # the size row of MiniMax (user 10.11.)
MINIMAX_STEPS_TIP = "MiniMax H3 Image is made for 6 steps at CFG 1."
MINIMAX_T2I_TIP = "Without “Downsize to canvas” the picture opens as a new document in the chosen size."
MINIMAX_EDIT = dict(gen_mp=4, downsize=True, layer_mask="none", enhance=False)     # Edit / Multi image edit: 4 MP and "Downsize to canvas" on
MINIMAX = Model(
    "minimax", "MiniMax H3 Image",
    "MiniMax H3 Image: text to image, edit and multi image edit at 4 to 20 MP.",
    {
        "txt2img": Mode("minimax-h3-image-t2i.json", dict(native=True, gen_mp=4, downsize=False, layer_mask="none", enhance=False),
                        prompt_tip=MINIMAX_T2I_TIP, steps_tip=MINIMAX_STEPS_TIP),
        # Edit and Multi image edit (step 4, user 11.11.): the size row as in Text to image, "Downsize to canvas" starts ON (a
        # layer in the canvas like every edit model; off = a new document in the chosen size)
        "edit": Mode("minimax-h3-image-edit.json", MINIMAX_EDIT, prompt_tip=EDIT_TIP, steps_tip=MINIMAX_STEPS_TIP),
        "multi_edit": Mode("minimax-h3-image-edit.json", MINIMAX_EDIT, prompt_tip=MULTI_TIP, steps_tip=MINIMAX_STEPS_TIP, run_as="edit"),
    },
    requires=(
        "minimax_h3_image_pruned_w4a8.safetensors",
        "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "minimax_h3_image_vae_fp16.safetensors",
    ),   # the model files this tab needs (details per mode: manifest.py)
    max_refs=6, tag_style="<Picture {n}>")   # <Picture 1> is the picture, the references follow (<Picture 2> ...); ref_side stays 1024 like the others

MODELS = [FLUX3, FLUX2, QWEN, FIBO, KREA2, MOSS, MINIMAX]      # the order of the tabs
BY_KEY = {m.key: m for m in MODELS}

SHORT = {"flux3": "Flux 3", "flux2": "Flux 2", "qwen": "Qwen Image 2.1", "fibo": "Fibo", "krea2": "Krea 2", "moss": "MOSS",
         "minimax": "MiniMax"}


def model_for_workflow(name: str) -> Model | None:
    """The model a workflow file belongs to (None for a workflow of your own)."""
    return next((m for m in MODELS if name in m.workflows()), None)
