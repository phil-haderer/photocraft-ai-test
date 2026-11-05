"""Tips of the day: the texts of the start-up popup (gui_tips.py). English, one tip per entry; edit the words between the quotes.
The order is the numbering of docs/tooltips-entwurf.md; the popup remembers the tips it showed by their text (gui_tips.tip_id), so tips may be removed or reordered. Check them against the code when functions change (PLAN.md point 16)."""

TIPS = (
    "Fill Selection: select an area and describe only what should appear there, e.g. \"add a red flower\". Always hide the layers of previous results before the next run.",
    "Remove Selection: keep the whole object inside the selection and name what to remove, e.g. \"car\".",
    "Remove Selection: if the first try doesn't work, run it a second time.",
    "Expand image: crop outward with the Crop tool (Enter), fill the new area white, and try an empty prompt first. Expand big areas in small steps.",
    "In Multi Image Edit your PhotoCraft picture is image 1 and slot 1 is image 2. Click the tag under a slot to add it to your prompt. Cut out the object in the reference image before using it.",
    "Drag a slot picture into the prompt box: its tag lands where you let go, and the text cursor shows the spot.",
    "The Describe icon on a slot picture writes a short description of it into your prompt, as its own line starting with the slot's tag (e.g. \"image 2: a red leather bag\"). Edit or delete it freely.",
    "Flux 3 Multi Image Edit with BBOX: draw a rectangular selection, put a reference in slot 1 and name the object from the reference image in the prompt, e.g. \"wine glass\". It is placed exactly in your rectangle.",
    "Edge feather softens the seam, in % of the selection's shorter side. It shows up with the soft layer mask (Fill, Remove); 0 = hard edge.",
    "\"Show feather\" paints the blend area red in PhotoCraft (Quick Mask). Click it again, or Generate, to get your selection back.",
    "Qwen fills small selections badly. Use a larger selection, or try Fibo 2.0 Edit Turbo.",
    "Right-click the chosen model chip and pick \"Set as my settings…\": the current sliders, sampler, steps and LoRAs become your start for this function and model, and \"Reset page\" returns to them. Shift-click \"Reset page\" for the standard settings.",
    "Right-click a model chip and tick \"Favourite for ...\": Easy Mode then uses this model first for that function. \"Reset favourite models\" (gear window, Other settings) forgets all favourites: Easy Mode and the functions use the default ranking again.",
    "MOSS does text to image only; Krea 2 is the fast text to image model.",
    "The gear window lists the files each model needs. The chain icon links a file ComfyUI already has under another name.",
    "\"Live preview\" shows the picture while it is made. It is greyed out until the model's preview decoder file is downloaded.",
    "MOSS text to image is best without the DMD2 speed LoRA: 25 steps at CFG 3.0. The LoRA (8 steps) is faster but looks more artificial.",
    "Ctrl+Enter generates. Esc or Ctrl+Alt+Enter cancels the run.",
    "The clock in the header lists your last 20 runs. Click one to load its settings with a new seed; nothing starts by itself.",
    "Describe Canvas (above the prompt) adds a short description of the picture in PhotoCraft to the end of your prompt. Ctrl+Z in the field undoes it.",
    "Upscale and Refine: the \"Mix source/new image\" slider blends the plain scaled original into the result; below 100 % it tames over-sharp results.",
    "Right-click a model chip and choose \"Hide this model\" to take it out of the window. It comes back with the tick in its tab of the gear window, or all at once with \"Show all hidden models\" (Other settings).",
    "Upscale and Refine: add a short description of your image in front of the default prompt for better results. Refine keeps the size and redraws fine detail.",
    "Edit Canvas: describe the result, e.g. \"Replace the laptop with a book.\" or \"Remove the sitting person.\"",
)
