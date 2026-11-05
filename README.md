<div align="center">

# PhotoCraft AI

**Text to Image, Fill, Remove, Expand, Edit, Upscale and more — inside PhotoCraft, running locally in ComfyUI.**

Tested: Windows 11 · 16 GB VRAM · PhotoCraft 0.20.1 · ComfyUI version: 0.42.0 

<sub>Replace Photoshop's generative AI features with locally running models. Supports: MOSS Image, Krea 2 Turbo, Flux 3 Image Klein, Flux 2 Image Klein, Qwen 2.1 Edit and Fibo 2.0 Edit Turbo  </sub>

</div>

---

> Unofficial community project, not affiliated with PhotoCraft, ArtCraft or Storyteller. PhotoCraft is in early alpha
> and so is this plugin. "PhotoCraft AI" is a working title.

## Install on Windows

1. **Get the parts**: Windows 10/11 with an NVIDIA card (16 GB VRAM), [Python 3.11+](https://www.python.org/downloads/windows/)
   (tested with 3.13 and 3.14; tick "tcl/tk" and "Add python.exe to PATH"; if several versions are installed, the setup prefers 3.13, 3.12, 3.11 and takes 3.14 last), PhotoCraft 0.20.1, and ComfyUI 0.42 or newer.
2. **Install the plugin**: *Code › Download ZIP* and unpack it (or `git clone` the repository), then double-click **`setup-windows.bat`**. It also creates the
   desktop shortcut **PhotoCraft AI** (it looks for `photocraft.exe` itself and asks once if it can't find it). The script shows its four steps as it goes; `setup-windows.bat /check` only looks and changes nothing.
3. **Start it**: start ComfyUI, close PhotoCraft, then double-click **PhotoCraft AI** on your desktop. PhotoCraft opens,
   and a few seconds later the plugin window appears.
4. **Get the models**: open the plugin's settings window (gear symbol). Under **Easy Mode** one button downloads the starter models
   (Flux 3 Klein Image, Qwen 2.1 Edit and Fibo 2.0 Edit Turbo; the button shows the total size). Easy Mode needs **Flux 3 plus
   Qwen or Fibo**: together they cover all seven Easy Mode functions, so you can also get just one of the two from its model tab in the gear window. Flux 3 needs a free Hugging Face login
   once (the button opens its page). Restart ComfyUI afterwards.
5. **Custom node**: the plugin needs one ComfyUI custom node pack, [ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)
   (Flux 3 Upscale uses its *Color Match* node). Install it from the ComfyUI Manager or the link, then restart ComfyUI. If you already have it,
   nothing changes. Without it only Flux 3 Upscale cannot run (the line at the bottom of the plugin names the pack); everything else uses ComfyUI's own nodes.
6. In the plugin window switch on **Easy Mode**, pick a function, type a prompt, press **Generate** (Ctrl+Enter).
   GGUF files work too (link them with the chain symbol in the gear window; needs [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF)).

Easy Mode shows only the basic function buttons and the prompt; the plugin picks the best installed model and its tested
settings. Multi Image Edit is not part of Easy Mode: switch it off to use it and to get all settings. 

Download all models via the settings tabs to get the full experience!

## Install on Linux

The plugin also runs on Linux (X11 and Wayland). It opens as a normal window next to PhotoCraft; unlike on Windows it is not
attached to the PhotoCraft window.

1. **Get the parts**: an NVIDIA card (16 GB VRAM), the current PhotoCraft, ComfyUI 0.42 or newer, and your distribution's Python 3.11+ (tested with 3.13 and 3.14)
   with tkinter and venv (Debian/Ubuntu: `sudo apt install python3 python3-tk python3-venv`; Fedora: `sudo dnf install python3 python3-tkinter`;
   Arch: `sudo pacman -S python tk`). Use the distribution's Python, not one from uv or pyenv: only its Tk draws the Inter font.
   Optional: `wl-clipboard` (Wayland) or `xclip` (X11) to paste pictures from the clipboard.
2. **Install the plugin**: unpack or `git clone` it, then run `./setup-linux.sh` in its folder. It makes `.venv`, installs the
   packages and adds **PhotoCraft AI** to your application menu. It never installs system packages itself; if something
   is missing it prints the command for your distribution. It shows its five steps as it goes; `./setup-linux.sh --check` only looks and changes nothing.
3. **Start it**: start ComfyUI, close PhotoCraft, then start **PhotoCraft AI** from the menu (or run `./photocraft-ai.sh`). PhotoCraft opens and the
   plugin window appears. If the `photocraft` program is not found (it is searched in `PATH`, `/opt`, `~/Applications` and
   a few more places), set `PHOTOCRAFT=/path/to/photocraft` or run `.venv/bin/python -m pccomfy shortcut --photocraft /path/to/photocraft`.
4. **Models and use**: as in steps 4 to 6 above (the custom node pack ComfyUI-KJNodes is needed on Linux too). Settings and the PhotoCraft token live in `~/.config/pccomfy/`; a different ComfyUI address or port
   goes into `~/.config/pccomfy/config.toml` (see `config.example.toml`).
5. **Window too small or too big?** The plugin takes PhotoCraft's scale, else your desktop's. If that is wrong, open the gear window › **Other settings** › **Interface scale** and pick a value; it counts from the next start. `.venv/bin/python -m pccomfy scale` shows what the plugin detected.

## What it does

You pick a **function** at the top, type a prompt and press **Generate**. The plugin sends the picture (or the selection) 
to ComfyUI and puts the result back into PhotoCraft as a new layer in a group, with a soft layer mask where that makes sense.

More settings in the window: **variants** (generates several results as layers in one group), prompt history, prompt templates,
Enhance prompt with LLM, live preview. The **scissors** at the bottom right (**Remove background**) cuts the subject out of the visible picture and adds it as a new layer with a transparent background; it needs the optional `birefnet.safetensors` (gear window › Models › Additional). Advanced settings: **edge feather, context size, mask density (PhotoCraft 0.17+), add custom LoRAs, sharpen.**


| Function | What it does |
|---|---|
| **Text to image** | A new picture from text only, as a new layer. |
| **Expand image** | Extend the canvas with the Crop tool, fill the new area white; the plugin paints it. |
| **Fill Selection** | Select an area, type what should appear there. |
| **Remove Selection** | Select an object, with a little margin around it; it is removed and the background filled in. |
| **Edit Canvas** | Changes the whole picture from your text ("make it night"). |
| **Multi Image Edit** | Edits the picture with reference images (drop or paste images into the slots). |
| **Upscale (new file)** | Enlarges the picture or selection into a new document, up to 24 MP. |
| **Refine (same size)** | Cleans up the picture or selection at the same size, as a new layer. |


Which model offers which function:

| | Flux 3 | Flux 2 | Qwen | Fibo | Krea 2 | MOSS |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Fill Selection | | | ✓ | ✓ | | |
| Remove Selection | ✓ | ✓ | ✓ | ✓ | | |
| Expand image | ✓ | ✓ | ✓ | ✓ | | |
| Edit Canvas | ✓ | ✓ | ✓ | ✓ | | |
| Multi Image Edit | ✓ | ✓ | ✓ | ✓ | | |
| Upscale (new file) | ✓ | ✓ | ✓ | | | |
| Refine (same size) | ✓ | ✓ | ✓ | ✓ | | |
| Text to image | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |


## Update and troubleshooting

- **Update**: download the new version, or run `git pull` in the plugin folder if you used `git clone`, and restart
  the plugin. Your settings stay in `data\`.
- **What the shortcut does**: it starts PhotoCraft with a control channel for the plugin (local only, protected by a
  token, file access limited to `data\exchange`) and then the plugin, without a console window.
- **Recreate the desktop shortcut**: run this in the plugin folder (type `powershell` into Explorer's address bar):

  ```
  .venv\Scripts\python.exe -m pccomfy shortcut
  ```

  Add `--photocraft "C:\path\to\photocraft.exe"` to name the file yourself. If `setup-windows.bat` said it
  uses Python directly, use the path in `data\python.txt` instead of `.venv\Scripts\python.exe`.

## Models

You only need the files for the models you want. The gear window lists the files each model needs, with size, ComfyUI target
folder and a download button; the plugin enables a model when it finds all the files for its standard settings.

- Release 1 uses the **int8 ConvRot** files, which fit into 16 GB VRAM.
- Some files are **gated**: log in to Hugging Face and accept the licence on the model page first. Flux 3 is one of them.


## Known limitations

- Tested on Windows with a 16 GB NVIDIA card. Linux is new: so far it was run in WSL (WSLg) only, not yet on a full desktop distribution.
- During a run, PhotoCraft briefly opens a temporary document. Please don't switch documents or change the
  selection while a run is going.
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

Other files: the 4x UltraSharp upscaler (Flux 3 Upscale) is CC BY-NC-SA 4.0, so no commercial use; the Lenovo UltraReal LoRA for MOSS asks for credit (Danrisi), the Qwen3-VL and Qwen 3.5 text encoders,
SeedVR2 and the MOSS LoRAs are Apache 2.0, BiRefNet is MIT.

## Credits

- [PhotoCraft](https://github.com/storytold/photocraft) by the ArtCraft team
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and the Comfy-Org model repositories
- [ausboss](https://huggingface.co/ausboss) (Restore and Outpaint LoRAs for Flux 3)
- [photocraft-comfyui-bridge](https://github.com/Peszemeszek/photocraft-comfyui-bridge) by Peszemeszek, the starting
  point of this project (MIT / Apache-2.0)
- The model authors: Black Forest Labs (Flux 2 / Flux 3 Klein), Qwen (Qwen-Image 2.1), Bria (Fibo 2.0), Krea (Krea 2),
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
