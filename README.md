<div align="center">

# PhotoCraft AI

**Photoshop-style generative AI for PhotoCraft, running on your own PC.**
Pick a function, type a prompt, press Generate: the result arrives as a new layer in your document.

<img src="readme-images/plugin-window.png" alt="The plugin window: eight functions, six models, prompt box and Generate button" width="330">

Tested: Windows 11 · 16 GB VRAM · PhotoCraft 0.20.2 · ComfyUI version: 0.42.0 

[Quick start](#quick-start) · [Install on Windows](#install-on-windows) · [Install on Linux](#install-on-linux) · [First start](#first-start) · [Functions](#functions) · [Help](#help) · [Technical details](#technical-details) · [Licences](#licences-of-the-models)

</div>

---

- **Seven function buttons:** Text to image, Expand, Fill, Remove, Edit Canvas, Multi Image Edit and Upscale / Refine.
- **Six models:** Flux 3 Klein, Flux 2 Klein, Qwen 2.1 Edit, Fibo 2.0 Edit Turbo, Krea 2 Turbo and MOSS Image.
- **Local:** the models run in ComfyUI on your own graphics card.
- **Easy Mode:** only the function buttons and the prompt; the plugin picks the best installed model.

> Unofficial community project, not affiliated with PhotoCraft, ArtCraft or Storyteller. PhotoCraft is in early alpha
> and so is this plugin. "PhotoCraft AI" is a working title.

## Quick start

You need [PhotoCraft](https://github.com/storytold/photocraft/releases) and [ComfyUI](https://github.com/comfyanonymous/ComfyUI#installing) installed, an NVIDIA graphics card with 16 GB VRAM, and Python 3.11 or newer ([download](https://www.python.org/downloads/windows/)).

**Windows**

1. Click **Code ▸ Download ZIP** (green button at the top of this page) and unpack it to a folder you keep, for example `C:\Tools\photocraft-ai`.
2. Double-click **`setup-windows.bat`**. It sets everything up and puts **PhotoCraft AI** on your desktop.
3. Start ComfyUI, close PhotoCraft, then double-click **PhotoCraft AI** on your desktop. PhotoCraft opens and the plugin window appears next to it.
4. In the plugin window click the gear ▸ **Easy Mode** tab ▸ download the starter models, then restart ComfyUI.
5. Switch on **Easy Mode**, pick a function, type a prompt and press **Generate** (Ctrl+Enter).

**Linux** (Debian/Ubuntu; other distributions: [Install on Linux](#install-on-linux))

```bash
sudo apt install python3 python3-tk python3-venv
git clone <this repository> && cd <this repository>
./setup-linux.sh
```

Then do steps 3 to 5 above, starting **PhotoCraft AI** from your application menu.

## How it fits together

```
PhotoCraft  <-->  this plugin (a small window)  <-->  ComfyUI (your graphics card)
```

- **PhotoCraft** is the image editor where you work and where the results land as layers.
- **ComfyUI** runs the AI models on your graphics card.
- **This plugin** sits between them: it sends your picture or selection to ComfyUI and puts the result back as a layer.

You need Windows 10/11 or Linux, an NVIDIA card with 16 GB VRAM, Python 3.11+ (Linux: 3.10+), PhotoCraft 0.20.2, and ComfyUI 0.42 or newer.

## Install on Windows

1. **Download**: click **Code ▸ Download ZIP** at the top of this page and unpack it to a folder you keep (not Downloads). Using git is fine too, see [Technical details](#technical-details).
2. **Set up**: double-click **`setup-windows.bat`**. It shows its four steps as it goes: Python, a private Python environment, the packages, and the desktop shortcut **PhotoCraft AI**. It finds `photocraft.exe` itself and asks once if it can't. (`setup-windows.bat /check` only looks and changes nothing.)
3. **Start**: start ComfyUI, close PhotoCraft, double-click **PhotoCraft AI** on your desktop. PhotoCraft opens, and a few seconds later the plugin window appears.

When you install Python, keep its default options: "tcl/tk" and "Add python.exe to PATH" must stay ticked.
Then go on with [First start](#first-start).

## Install on Linux

X11 and Wayland. On Linux the window is not docked to PhotoCraft (Wayland does not allow it); it is a normal window next to it and closes with PhotoCraft.

1. **System packages** (Python 3.10+ with tkinter and venv):

   ```bash
   # Debian/Ubuntu
   sudo apt install python3 python3-tk python3-venv
   # Fedora
   sudo dnf install python3 python3-tkinter
   # Arch
   sudo pacman -S python tk
   # optional, to paste pictures from the clipboard: wl-clipboard (Wayland) or xclip (X11)
   sudo apt install wl-clipboard xclip
   ```

2. **Get the plugin**: download the ZIP and unpack it, or `git clone <this repository>`.
3. **Set up**: run `./setup-linux.sh` in the plugin folder. It makes a private Python environment, installs the packages and adds **PhotoCraft AI** to your application menu. It never installs system packages itself; if something is missing it prints the command for your distribution. (`./setup-linux.sh --check` only looks and changes nothing.)
4. **Start**: start ComfyUI, close PhotoCraft, then start **PhotoCraft AI** from the menu (or run `./photocraft-ai.sh`). PhotoCraft is found in `PATH`, `/opt`, `~/Applications`, `~/.local/bin` or as a Flatpak. If it is somewhere else: `PHOTOCRAFT=/path/to/photocraft ./photocraft-ai.sh`.

Then go on with [First start](#first-start). Window too small or too big? Gear window ▸ **Other settings** ▸ **Interface scale**.

## First start

1. **Get the models.** Open the plugin's settings window (gear symbol) ▸ **Easy Mode** tab. One button downloads the starter models: Flux 3 Klein, plus Qwen 2.1 Edit and Fibo 2.0 Edit Turbo (the button shows the total size). Easy Mode needs Flux 3 plus Qwen or Fibo, so you can also get just one of the two from its model tab. Flux 3 needs a free Hugging Face login once (the button opens its page). Restart ComfyUI afterwards. The models have different licences, some without commercial use: see [Licences of the models](#licences-of-the-models).
2. **Generate.** Switch on **Easy Mode**, pick a function, type a prompt and press **Generate** (Ctrl+Enter).

Easy Mode shows only the basic function buttons and the prompt; the plugin picks the best installed model and its tested settings. Multi Image Edit is not part of Easy Mode: switch it off to use it and to get all settings. To use every model, download the rest from the model tabs of the settings window.

Optional: Flux 3 Upscale needs one ComfyUI custom node pack, and GGUF model files need another. Both are described in [Technical details](#technical-details).

## Functions

You pick a **function** at the top, type a prompt and press **Generate**. The plugin sends the picture (or the selection)
to ComfyUI and puts the result back into PhotoCraft as a new layer in a group, with a soft layer mask where that makes sense.

| Function | What it does |
|---|---|
| **Text to image** | A new picture from text only, as a new layer. |
| **Expand image** | Extend the canvas with the Crop tool, fill the new area white; the plugin paints it. |
| **Fill Selection** | Select an area, type what should appear there. |
| **Remove Selection** | Select an object, with a little margin around it; it is removed and the background filled in. |
| **Edit Canvas** | Changes the whole picture from your text ("make it night"). |
| **Multi Image Edit** | Edits the picture with reference images (drop or paste images into the slots). |
| **Upscale / Refine** | Pick a factor (1.5x to 4x) in the row "Upscale factor": the whole picture is enlarged into a new document, up to 24 MP. Or pick a button in the row "Refine" (Default; with Flux 2 also Neutral and Studio portrait; with Flux 3 also Restore): the picture is cleaned up at the same size, as a new layer. A selection is ignored. |

<details>
<summary>Which model offers which function</summary>

| | Flux 3 | Flux 2 | Qwen | Fibo | Krea 2 | MOSS |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Fill Selection | | | ✓ | ✓ | | |
| Remove Selection | ✓ | ✓ | ✓ | ✓ | | |
| Expand image | ✓ | ✓ | ✓ | ✓ | | |
| Edit Canvas | ✓ | ✓ | ✓ | ✓ | | |
| Multi Image Edit | ✓ | ✓ | ✓ | ✓ | | |
| Upscale (new file) | ✓ | ✓ | ✓ | ✓ (up to 2x) | | |
| Refine (same size) | ✓ | ✓ | ✓ | ✓ | | |
| Text to image | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

</details>

More in the window: **variants** (several results as layers in one group), prompt history, prompt templates, Enhance prompt with LLM, live preview. The **scissors** at the bottom right (**Remove background**) opens a small menu: **BiRefNet**, **RMBG-2.0** or **Both** (two layers, RMBG-2.0 on top). The subject is cut out of the visible picture and added as a new layer with a transparent background, and the edge colours are cleaned so no light rim shows on a dark background. It needs the optional `birefnet.safetensors` and/or `rmbg-2.0.safetensors` (gear window ▸ Models ▸ Additional); RMBG-2.0 is for non-commercial use only, and its download symbol in the settings window uses a community mirror because the official file needs a Hugging Face login. To get it by hand: log in at [huggingface.co/briaai/RMBG-2.0](https://huggingface.co/briaai/RMBG-2.0), accept the terms, download `model.safetensors`, rename it to `rmbg-2.0.safetensors` and put it into ComfyUI's `models/background_removal` folder (restart ComfyUI). Advanced settings: **edge feather, context size, mask density (PhotoCraft 0.17+), custom LoRAs, sharpen.**

## Help

| You see | What to do |
|---|---|
| The dot next to **ComfyUI** (bottom left) is red, or "ComfyUI not connected" | Start ComfyUI. If it runs on another address or port: gear ▸ **Other settings** ▸ **ComfyUI address**, then Refresh. |
| "PhotoCraft not found" when you start | Windows: run `.venv\Scripts\python.exe -m pccomfy shortcut --photocraft "C:\path\to\photocraft.exe"` in the plugin folder (type `powershell` into Explorer's address bar). Linux: `PHOTOCRAFT=/path/to/photocraft ./photocraft-ai.sh`. |
| "PhotoCraft did not open the control port" | Another PhotoCraft is already running: close all of them and start through the shortcut or menu entry. Or another program uses port 7878. |
| "No control-channel token" or "rejected the token" | PhotoCraft was started without the plugin's start options. Close it and start through the shortcut or menu entry. Flatpak: see [Technical details](#technical-details). |
| "You need to download …", or a model button is greyed out | Open the gear window: a red dot marks a missing file. Download it, then restart ComfyUI (it reads its model folders only at start). |
| A Flux 3 download is refused | Log in to Hugging Face and accept the licence on the model page first. |
| On Linux nothing appears | Run `./photocraft-ai.sh` in a terminal; the message tells you what is missing. |

**Update.** Download the new ZIP and unpack it over the old folder, or run `git pull` in the plugin folder if you used `git clone`; then run the setup script again and restart the plugin. Your settings, including "Set as my settings", stay in `data\` (Linux: `~/.config/pccomfy/`) and are not touched.

**Report a problem.** Open an issue on this repository's **Issues** page and tell us:
- what you did, what you expected and what happened (the status line at the bottom of the window is useful);
- your operating system, graphics card, and the versions of PhotoCraft, ComfyUI and the plugin (the ZIP's date or the git commit);
- the last lines of `data\exchange\runs.jsonl` (Linux: `~/.cache/pccomfy/exchange/runs.jsonl`): one line per run. `last-graph.json` in the same folder is the exact request sent to ComfyUI.

Both files can contain your prompts, so look through them before you post.

## Technical details

**Install with git.**

```bash
git clone <this repository>
cd <this repository>
```

**Windows, by hand** (what `setup-windows.bat` does):

```bat
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install pillow numpy websocket-client tkinterdnd2
:: desktop shortcut (optional)
.venv\Scripts\python.exe -m pccomfy shortcut --photocraft "C:\path\to\photocraft.exe"
:: start without the shortcut (ComfyUI running, PhotoCraft closed)
.venv\Scripts\python.exe photocraft-ai.pyw --photocraft "C:\path\to\photocraft.exe"
```

If `setup-windows.bat` said it uses Python directly, use the path in `data\python.txt` instead of `.venv\Scripts\python.exe`.
The shortcut starts PhotoCraft with a control channel for the plugin (local only, protected by a token, file access limited to `data\exchange`) and then the plugin, without a console window.

**Linux, by hand** (what `setup-linux.sh` does):

```bash
# create the venv with the system Python: a Python from uv or pyenv brings a Tk that does not draw the Inter font
/usr/bin/python3 -m venv .venv
.venv/bin/pip install pillow numpy websocket-client tkinterdnd2
# Python 3.10 (Ubuntu 22.04) also needs: .venv/bin/pip install tomli
./photocraft-ai.sh
# menu entry (optional)
.venv/bin/python -m pccomfy shortcut --photocraft /path/to/photocraft
```

Settings and the PhotoCraft token live in `~/.config/pccomfy/`. A different ComfyUI address or port goes into `~/.config/pccomfy/config.toml` (see `config.example.toml`). `.venv/bin/python -m pccomfy scale` shows how the plugin detected the display scale.

**PhotoCraft as a Flatpak.** It is found by itself; to name it: `PHOTOCRAFT=flatpak:ai.storyteller.photocraft ./photocraft-ai.sh`. The Flatpak sandbox sees only Pictures and Documents, so the plugin opens `~/.config/pccomfy` and `~/.cache/pccomfy` for the Flatpak run; that lets PhotoCraft write its token file there.

**Custom nodes.** Flux 3 Upscale uses the *Color Match* node of [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes). Install the pack from the ComfyUI Manager or the link, then restart ComfyUI. Without it only Flux 3 Upscale cannot run (the line at the bottom of the plugin names the pack); everything else uses ComfyUI's own nodes. GGUF files (link them with the chain symbol in the gear window) need [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF).

**Model files.** You only need the files for the models you want. The gear window lists the files each model needs, with size, ComfyUI target folder and a download button; the plugin enables a model when it finds all the files for its standard settings. To fit into 16 GB VRAM, release 1 uses the int8 ConvRot files. Some files are gated: log in to Hugging Face and accept the licence on the model page first. Flux 3 is one of them.

**Known limitations.**
- Developed and tested on Windows 11 with a 16 GB NVIDIA card. On Linux it was run on Ubuntu 24.04 (Wayland); other distributions and X11 are not tested yet.
- During a run, PhotoCraft briefly opens a temporary document. Please don't switch documents or change the selection while a run is going.
- A run consists of several PhotoCraft steps (history entries).
- CMYK, Lab and 16-bit documents go through 8-bit RGB.

## Licences of the models

The plugin's code is MIT / Apache-2.0, but **the models have their own licences**, and several limit commercial use.
This is a summary of what the model pages state, not legal advice; read the licence on each model page before you use
results commercially.

| Model | Licence | Commercial use |
|---|---|---|
| Flux 3 (Klein) and its LoRAs | FLUX Kommunity License | Free only below a yearly revenue limit (USD 5 million, with conditions); above that you need a licence from Black Forest Labs |
| Flux 2 (Klein) | FLUX non-commercial | No |
| Qwen (Qwen-Image 2.1) | Qwen Research License | No (research and evaluation only); products must say "Built with Qwen" |
| Fibo 2.0 | CC BY-NC 4.0 | No |
| Krea 2 | Krea 2 Community License | See the licence on its model page |
| MOSS | Apache 2.0 | Yes |

Other files: the 4x UltraSharp upscaler (Flux 3 Upscale and Fibo Upscale) is CC BY-NC-SA 4.0, so no commercial use; the Lenovo UltraReal LoRA for MOSS asks for credit (Danrisi), the Qwen3-VL and Qwen 3.5 text encoders,
SeedVR2 and the MOSS LoRAs are Apache 2.0, BiRefNet is MIT. RMBG-2.0 (Bria AI, the optional second cut-out model) is source-available for non-commercial use only; the download link in the plugin points to a community mirror of the official file.

## Credits

- [PhotoCraft](https://github.com/storytold/photocraft) by the ArtCraft team
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and the Comfy-Org model repositories
- [ausboss](https://huggingface.co/ausboss) (Restore and Outpaint LoRAs for Flux 3)
- [photocraft-comfyui-bridge](https://github.com/Peszemeszek/photocraft-comfyui-bridge) by Peszemeszek, the starting
  point of this project (MIT / Apache-2.0)
- The model authors: Black Forest Labs (Flux 2 / Flux 3 Klein), Qwen (Qwen-Image 2.1), Bria (Fibo 2.0 and RMBG-2.0), Krea (Krea 2),
  MOSS-Image, ByteDance (SeedVR2), obsxrver (Flux 2 Klein int8 ConvRot), lodestones (MOSS DMD2 LoRA), Danrisi (Lenovo
  UltraReal LoRA), vizsumit (UltraReal LoRA for Flux 2)
- [ThetaCursed/Krea2-Style-Explorer](https://github.com/ThetaCursed/Krea2-Style-Explorer) (MIT): the style prompts of the
  Styles button, licence in [pccomfy/assets/LICENSE-krea-style-explorer.txt](pccomfy/assets/LICENSE-krea-style-explorer.txt)
- [Lucide](https://lucide.dev) (ISC): the window's icons follow its shapes and style
- [Inter](https://rsms.me/inter/) font by Rasmus Andersson (SIL Open Font License 1.1, see
  [pccomfy/assets/fonts/OFL-Inter.txt](pccomfy/assets/fonts/OFL-Inter.txt))

## License

Dual-licensed under [MIT](LICENSE-MIT) or [Apache-2.0](LICENSE-APACHE), at your option. The models are not part of this
repository and have their own licences (see above).
