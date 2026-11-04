"""Manual check (not part of run_all.py): Text to image at 0.5, 1 and 2 MP, all six models, with the Turbo LoRA and with 75 % of the steps (user 4.11.).

Two prompts: a portrait (3:4) and a landscape (16:9). Per model the variants are
  standard   the plugin's standard settings for Text to image (what a new user gets),
  turbo      only where the workflow has a speed LoRA switch (Qwen, MOSS): the switch on, steps and CFG as the window sets them,
  steps75    the standard settings with 75 % of the standard steps (Turbo LoRA off where there is a switch).
14 variants x 2 prompts x 3 sizes x 2 seeds = 168 pictures. Not blind: the sheets carry the names.

    python tests\\live_t2i_size_test.py plan                       (what would run; no ComfyUI needed)
    python tests\\live_t2i_size_test.py run [--seeds 2] [--models flux3 qwen ...] [--dry]
    python tests\\live_t2i_size_test.py sheets [folder]            (one sheet per model and prompt, columns = sizes, rows = variant and seed)
    python tests\\live_t2i_size_test.py summary [folder]           (seconds per variant and size, written to zeiten.md)
    python tests\\live_t2i_size_test.py pages [folder]             (one bewerten.html: every sheet as a page, full-size pictures, rating buttons)
    python tests\\live_t2i_size_test.py compare [folder]           (one vergleich.html: a page per model, prompt, size and seed, turbo | standard | 75 % steps side by side)

Output: data\\t2i-size-test\\<time>\\ (bilder\\<model>_<variant>_<prompt>_<size>_s<seed>.png, records.json, blatt-*.png, zeiten.md).
Needs ComfyUI with the files of the models; nothing in the plugin changes. ``--dry`` builds every graph but queues nothing.
"""
import argparse
import html
import json
import socket
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import live_style_test as base  # noqa: E402  (the app, the standard request and the helpers of the Styles round)
from pccomfy import config as cfgmod, imaging, inventory, workflows  # noqa: E402
from pccomfy.bridge import Bridge  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402

BASE = cfgmod.CONFIG_DIR / "t2i-size-test"
MODELS = base.MODELS
SEEDS = (101, 202)
PROMPTS = {
    "portrait": "Close-up portrait of a young woman in her early twenties, light freckles, a small fine-line crescent-moon tattoo on the "
                "right side of her neck below the ear, a thin gold nose stud and two small silver hoop earrings, loose dark hair, "
                "soft window light, 85 mm, sharp skin texture.",
    "landscape": "Wide landscape at golden hour: weathered Roman ruins, broken columns and an arch, merge with modern glass-and-steel "
                 "buildings, a tram line crossing the old forum, cypress trees, a few tourists, dramatic clouds, photorealistic.",
}
# size name -> {prompt: (width, height)}; all multiples of 32
SIZES = {
    "0.5MP": {"portrait": (640, 864), "landscape": (960, 544)},
    "1MP": {"portrait": (864, 1152), "landscape": (1376, 768)},
    "2MP": {"portrait": (1248, 1664), "landscape": (1856, 1056)},
}


def variants(app, mk: str):
    """[(name, Request, label, lora)] for one model, built by the real window code (so Steps and CFG are what the window sets).
    lora: "on" / "off" where the workflow has a speed LoRA switch, else "n/a"."""
    req, label = base.standard_request(app, mk)
    switch = app._has_lora_switch()
    out = [("standard", req, label, "off" if switch else "n/a")]
    steps = req.params.steps
    if switch:              # Qwen, MOSS: standard is the switch off; the window's Turbo values for "on"
        app.v_turbo.set(True)
        app._on_turbo()
        out.append(("turbo", app._request(), label, "on"))
        app.v_turbo.set(False)
        app._on_turbo()
    low = max(1, int(steps * 0.75 + 0.5))
    out.append(("steps75", replace(req, params=replace(req.params, steps=low), sampler_override={**req.sampler_override, "steps": low}), label, "off" if switch else "n/a"))
    return out


def cmd_plan(a):
    app = base.make_app(cfgmod.load()["comfyui"]["url"])
    total = 0
    for mk in a.models:
        for name, req, label, _lora in variants(app, mk):
            n = len(PROMPTS) * len(SIZES) * a.seeds
            total += n
            print(f"{label:22} {name:9} steps {req.params.steps:>2} cfg {req.params.cfg} Turbo LoRA {_lora} sampler {req.params.sampler}/{req.params.scheduler}  ({n} pictures)")
    print(f"\n{total} pictures; sizes {json.dumps(SIZES)}")
    app.root.destroy()


def cmd_run(a):
    url = cfgmod.load()["comfyui"]["url"]
    host, port = url.split("//")[-1].split(":")[0], int(url.rsplit(":", 1)[-1].strip("/"))
    if not a.dry:
        try:
            socket.create_connection((host, port), timeout=2).close()
        except OSError:
            sys.exit(f"ComfyUI is not running ({url}). Start it first.")
    out = Path(a.into) if a.into else BASE / time.strftime("%Y%m%d-%H%M%S")
    (out / "bilder").mkdir(parents=True, exist_ok=True)
    old = json.load(open(out / "records.json", encoding="utf-8")) if a.into else []
    comfy = ComfyUI(url)
    b = Bridge(base._NoPhotoCraft(), comfy, out / "xch")
    app = base.make_app(url)
    inv = None if a.dry else inventory.fetch(comfy, cfgmod.model_map())
    seeds = list(SEEDS[: max(1, a.seeds)])
    records, t_start, n = [r for r in old if r["variant"] not in (a.only or [])], time.time(), 0   # --into: the named variants are redone
    for mk in a.models:
        if inv is not None and inv.tab_status(mk).state != "ready":
            print(f"SKIPPED {mk}: its files are not all there", flush=True)
            continue
        for vname, req, label, lora in variants(app, mk):
            if a.only and vname not in a.only:
                continue
            wf = req.workflow
            tpl = workflows.load_template(wf)
            needs_image = any(isinstance(nd, dict) and nd.get("_meta", {}).get("title") == "pc:image" for nd in tpl.values())
            print(f"== {label} / {vname}: steps {req.params.steps}, cfg {req.params.cfg}, Turbo LoRA {lora}", flush=True)
            for pname, prompt in PROMPTS.items():
                for sname, by_prompt in SIZES.items():
                    gw, gh = by_prompt[pname]
                    for seed in seeds:
                        n += 1
                        p = replace(req.params, prompt=prompt, seed=seed, width=gw, height=gh)
                        image_name = None
                        if needs_image:       # Qwen Edit as Text to image: an empty white canvas of the result's size (as the bridge does)
                            image_name = "dry.png" if a.dry else comfy.upload_image(Image.new("RGB", (gw, gh), "white"), f"pcc-t2i-size-{n}.png")
                        graph, out_node = b._graph(req, p, image_name, None, wf)
                        name = f"{mk}_{vname}_{pname}_{sname}_s{seed}"
                        rec = {"file": name + ".png", "model_key": mk, "model": label, "variant": vname, "prompt": pname, "size": sname,
                               "seed": seed, "steps": req.params.steps, "cfg": req.params.cfg, "lora": lora, "asked": [gw, gh]}
                        if not a.dry:
                            t0 = time.time()
                            hist = b._wait(comfy.queue(graph), graph, str(wf), 0, 1, "", lambda *x, **k: None)
                            im = comfy.output_images(hist, out_node)[0].convert("RGB")
                            if req.sharpen:
                                im = imaging.sharpen(im, req.sharpen)
                            im.save(out / "bilder" / rec["file"])
                            rec.update(seconds=round(time.time() - t0, 1), got=list(im.size))
                            print(f"{n} {name}: {rec['seconds']:.0f} s, {im.size[0]}x{im.size[1]}", flush=True)
                        records.append(rec)
                        json.dump(records, open(out / "records.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"\n{'DRY RUN (nothing queued)' if a.dry else 'DONE'} in {(time.time() - t_start) / 60:.1f} min: {len(records)} pictures in {out}\n"
          f"Next: python tests\\live_t2i_size_test.py sheets", flush=True)
    app.root.destroy()


def latest(folder):
    if folder:
        return Path(folder)
    runs = sorted(p for p in BASE.iterdir() if (p / "records.json").exists())
    if not runs:
        sys.exit(f"No round in {BASE}")
    return runs[-1]


def cmd_sheets(a):
    """One sheet per model and prompt: the columns are the sizes, the rows are variant x seed; every row and cell carries its name."""
    out = latest(a.folder)
    recs = json.load(open(out / "records.json", encoding="utf-8"))
    th, head, side = 360, 20, 150
    font = ImageFont.load_default(size=13)
    for mk in dict.fromkeys(r["model_key"] for r in recs):
        for pname in PROMPTS:
            rows = [r for r in recs if r["model_key"] == mk and r["prompt"] == pname]
            if not rows:
                continue
            keys = list(dict.fromkeys((r["variant"], r["seed"]) for r in rows))
            sheet = Image.new("RGB", (side + len(SIZES) * th, head + len(keys) * (th + head)), "#282828")
            d = ImageDraw.Draw(sheet)
            first = rows[0]
            d.text((4, 3), f"{first['model']} - {pname}", fill="#ffffff", font=font)
            for x, sname in enumerate(SIZES):
                d.text((side + x * th + 4, 3), sname, fill="#e6e6e6", font=font)
            for y, (vname, seed) in enumerate(keys):
                top = head + y * (th + head)
                v = next(r for r in rows if r["variant"] == vname)
                d.text((4, top + 24), f"{vname}\n{v['steps']} steps, cfg {v['cfg']}\nTurbo LoRA: {v['lora']}\nseed {seed}",
                       fill="#e6e6e6", font=font)
                for x, sname in enumerate(SIZES):
                    r = next((q for q in rows if q["variant"] == vname and q["seed"] == seed and q["size"] == sname), None)
                    f = out / "bilder" / r["file"] if r else None
                    if f and f.exists():
                        im = Image.open(f).convert("RGB")
                        w, h = im.size
                        im.thumbnail((th, th))
                        sheet.paste(im, (side + x * th, top + head))
                        d.text((side + x * th + 4, top + 2), f"{w}x{h}, {r['seconds']:.0f} s", fill="#bbbbbb", font=font)
            sheet.save(out / f"blatt-{mk}-{pname}.png")
            print(f"blatt-{mk}-{pname}.png")


PAGE_CSS = """
:root{color-scheme:dark light;--bg:#1e1e1e;--fg:#e8e8e8;--mut:#a0a0a0;--card:#2a2a2a;--line:#444;--acc:#6aa6ff}
@media (prefers-color-scheme:light){:root{--bg:#f4f4f4;--fg:#1a1a1a;--mut:#666;--card:#fff;--line:#ccc;--acc:#1a5fd0}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
header h1{font-size:17px;margin:0 12px 0 0}
button,select{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer}
button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
main{padding:12px 16px;overflow-x:auto}
section{display:none}section.act{display:block}
.grid{display:grid;grid-template-columns:150px repeat(3,minmax(0,1fr));gap:10px;align-items:start}
.full .grid{grid-template-columns:150px repeat(3,max-content)}
.colh{font-weight:600;padding:4px 0}
.rowh{font-size:13px;color:var(--mut);padding-top:4px}.rowh b{color:var(--fg)}
.cell{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}
.cell img{display:block;width:100%;height:auto;border-radius:4px;cursor:zoom-in}
.full .cell img{width:auto;max-width:none}
.meta{display:flex;justify-content:space-between;gap:8px;font-size:12px;color:var(--mut);margin:4px 0}
.rate{display:flex;gap:6px;flex-wrap:wrap}
dialog{border:none;background:#000;padding:0;max-width:96vw;max-height:96vh}dialog img{display:block;max-width:96vw;max-height:96vh}
textarea{width:100%;height:16em;background:var(--card);color:var(--fg);border:1px solid var(--line)}
"""
PAGE_JS = """
const KEY=document.body.dataset.key,secs=[...document.querySelectorAll('section')];let R={};
try{R=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(R))}catch(e){}};
function paint(){document.querySelectorAll('.cell').forEach(c=>c.querySelectorAll('.rate button').forEach(b=>b.classList.toggle('on',R[c.dataset.f]===b.dataset.v)));
 secs.forEach(s=>{const n=[...s.querySelectorAll('.cell')].filter(c=>R[c.dataset.f]).length,t=s.querySelectorAll('.cell').length;
  document.querySelector('[data-go="'+s.id+'"]').textContent=s.dataset.label+' ('+n+'/'+t+')'})}
function show(id){let i=secs.findIndex(s=>s.id===id);if(i<0)i=0;secs.forEach((s,j)=>s.classList.toggle('act',j===i));
 document.getElementById('sel').value=secs[i].id;try{history.replaceState(null,'','#'+secs[i].id)}catch(e){}window.scrollTo(0,0)}
function step(d){const i=secs.findIndex(s=>s.classList.contains('act'));show(secs[(i+d+secs.length)%secs.length].id)}
document.addEventListener('click',e=>{const b=e.target.closest('.rate button');
 if(b){const f=b.closest('.cell').dataset.f;if(R[f]===b.dataset.v)delete R[f];else R[f]=b.dataset.v;save();paint();return}
 const i=e.target.closest('.cell img');if(i){const d=document.getElementById('zoom');d.querySelector('img').src=i.src;d.showModal();return}
 if(e.target.closest('#zoom')){document.getElementById('zoom').close();return}
 const g=e.target.closest('[data-go]');if(g)show(g.dataset.go)});
document.addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT')return;if(e.key==='ArrowRight')step(1);if(e.key==='ArrowLeft')step(-1)});
document.getElementById('sel').onchange=function(){show(this.value)};
document.getElementById('size').onclick=function(){document.body.classList.toggle('full');this.classList.toggle('on')};
document.getElementById('exp').onclick=()=>{const t=document.getElementById('out'),tal={};
 Object.entries(R).forEach(([f,v])=>{const p=f.replace('.png','').split('_'),k=p[0]+' / '+p[1];(tal[k]=tal[k]||{gut:0,ok:0,schlecht:0})[v]++});
 t.hidden=false;t.value='Je Modell und Variante (gut / ok / schlecht):\\n'+Object.entries(tal).sort().map(([k,c])=>k+': '+c.gut+' / '+c.ok+' / '+c.schlecht).join('\\n')
  +'\\n\\nEinzeln:\\n'+Object.entries(R).sort().map(x=>x[0]+': '+x[1]).join('\\n');t.select()};
document.getElementById('clr').onclick=()=>{if(confirm('Alle Bewertungen löschen?')){R={};save();paint()}};
paint();show(location.hash.slice(1)||secs[0].id);
"""


def cmd_pages(a):
    """One bewerten.html with every sheet as a page inside it (tabs, arrow keys): the pictures at full size, scaled by the browser."""
    out = latest(a.folder)
    recs = json.load(open(out / "records.json", encoding="utf-8"))
    secs, tabs = [], []
    for mk in dict.fromkeys(r["model_key"] for r in recs):
        for pname in PROMPTS:
            rows = [r for r in recs if r["model_key"] == mk and r["prompt"] == pname]
            if not rows:
                continue
            sid, label = f"{mk}-{pname}", f"{rows[0]['model']} {pname}"
            tabs.append((sid, label))
            keys = list(dict.fromkeys((r["variant"], r["seed"]) for r in rows))
            cells = ['<div class="colh"></div>' + "".join(f'<div class="colh">{html.escape(s)}</div>' for s in SIZES)]
            for vname, seed in keys:
                v = next(r for r in rows if r["variant"] == vname)
                cells.append(f'<div class="rowh"><b>{vname}</b><br>{v["steps"]} steps, cfg {v["cfg"]}<br>Turbo LoRA: {v["lora"]}<br>seed {seed}</div>')
                for sname in SIZES:
                    r = next((q for q in rows if q["variant"] == vname and q["seed"] == seed and q["size"] == sname), None)
                    if r is None:
                        cells.append("<div></div>")
                        continue
                    f = html.escape(r["file"])
                    got = "x".join(map(str, r.get("got", r["asked"])))
                    cells.append(f'<div class="cell" data-f="{f}"><img src="bilder/{f}" loading="lazy" alt="{f}">'
                                 f'<div class="meta"><span>{html.escape(r["file"][:-4])}</span><span>{got}, {r.get("seconds", 0):.0f} s</span></div>'
                                 f'<div class="rate"><button data-v="gut">gut</button><button data-v="ok">ok</button><button data-v="schlecht">schlecht</button></div></div>')
            secs.append(f'<section id="{sid}" data-label="{html.escape(label)}"><h2>{html.escape(label)}</h2><div class="grid">{"".join(cells)}</div></section>')
    nav = "".join(f'<button data-go="{i}">{html.escape(l)}</button>' for i, l in tabs)
    sel = "".join(f'<option value="{i}">{html.escape(l)}</option>' for i, l in tabs)
    (out / "bewerten.html").write_text(
        f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Text to image: Größen und Steps</title><style>{PAGE_CSS}</style></head><body data-key="t2i-{out.name}">'
        f'<header><h1>Text to image: Größen und Steps</h1>{nav}</header>'
        f'<header style="top:auto;position:static"><select id="sel">{sel}</select><button onclick="step(-1)">&larr; zurück</button><button onclick="step(1)">weiter &rarr;</button>'
        f'<button id="size">Originalgröße (100 %)</button><button id="exp">Bewertung als Text</button><button id="clr">Löschen</button>'
        f'<span style="color:var(--mut);font-size:13px">Pfeiltasten blättern, Klick auf ein Bild = Vollbild, Bewertung bleibt im Browser</span></header>'
        f'<main>{"".join(secs)}<textarea id="out" hidden></textarea></main><dialog id="zoom"><img alt=""></dialog><script>{PAGE_JS}</script></body></html>',
        encoding="utf-8")
    print(out / "bewerten.html")


CMP_ORDER = ("turbo", "standard", "steps75")          # left to right on a comparison page
CMP_CSS = """
:root{color-scheme:dark light;--bg:#1e1e1e;--fg:#e8e8e8;--mut:#a0a0a0;--card:#2a2a2a;--line:#444;--acc:#6aa6ff}
@media (prefers-color-scheme:light){:root{--bg:#f4f4f4;--fg:#1a1a1a;--mut:#666;--card:#fff;--line:#ccc;--acc:#1a5fd0}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.4 system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 16px;display:flex;flex-wrap:wrap;gap:8px;align-items:center}
header h1{font-size:17px;margin:0 12px 0 0}
button,select{font:inherit;color:var(--fg);background:var(--card);border:1px solid var(--line);border-radius:6px;padding:3px 10px;cursor:pointer}
button.on{background:var(--acc);color:#fff;border-color:var(--acc)}
main{padding:12px 16px}
section{display:none}section.act{display:block}
h2{font-size:16px;margin:0 0 10px}
.row{display:grid;grid-template-columns:repeat(var(--n),minmax(0,1fr));gap:12px;align-items:start}
.cell{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}
.box{overflow:hidden}.cell img{display:block;width:100%;height:auto;border-radius:4px;cursor:zoom-in}
.full .box{overflow:auto;max-height:78vh}.full .cell img{width:auto;max-width:none;cursor:zoom-in}
.meta{font-size:13px;color:var(--mut);margin:4px 0}.meta b{color:var(--fg)}
.pick{display:flex;gap:8px;margin-top:12px;align-items:center;flex-wrap:wrap}
dialog{border:none;background:#000;padding:0;max-width:96vw;max-height:96vh}dialog img{display:block;max-width:96vw;max-height:96vh}
textarea{width:100%;height:18em;background:var(--card);color:var(--fg);border:1px solid var(--line)}
"""
CMP_JS = """
const KEY=document.body.dataset.key,secs=[...document.querySelectorAll('section')];let R={};
try{R=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(R))}catch(e){}};
let cur=0;
function paint(){secs.forEach(s=>s.querySelectorAll('.pick button').forEach(b=>b.classList.toggle('on',R[s.id]===b.dataset.v)));
 const n=Object.keys(R).length;document.getElementById('cnt').textContent='bewertet: '+n+' / '+secs.length;
 document.querySelectorAll('#sel option').forEach((o,i)=>{o.textContent=(R[secs[i].id]?'✓ ':'')+secs[i].dataset.label})}
function show(i){cur=(i+secs.length)%secs.length;secs.forEach((s,j)=>s.classList.toggle('act',j===cur));
 document.getElementById('sel').value=cur;document.querySelectorAll('[data-m]').forEach(b=>b.classList.toggle('on',b.dataset.m===secs[cur].dataset.m));
 try{history.replaceState(null,'','#'+secs[cur].id)}catch(e){}window.scrollTo(0,0)}
document.addEventListener('click',e=>{const b=e.target.closest('.pick button');
 if(b){const id=b.closest('section').id;if(R[id]===b.dataset.v)delete R[id];else R[id]=b.dataset.v;save();paint();return}
 const m=e.target.closest('[data-m]');if(m){show(secs.findIndex(s=>s.dataset.m===m.dataset.m));return}
 const i=e.target.closest('.cell img');if(i){const d=document.getElementById('zoom');d.querySelector('img').src=i.src;d.showModal();return}
 if(e.target.closest('#zoom'))document.getElementById('zoom').close()});
document.addEventListener('keydown',e=>{if(e.target.tagName==='TEXTAREA'||e.target.tagName==='SELECT')return;
 if(e.key==='ArrowRight')show(cur+1);if(e.key==='ArrowLeft')show(cur-1)});
document.addEventListener('scroll',e=>{const t=e.target;if(!t.classList||!t.classList.contains('box')||t.dataset.lock)return;
 t.parentElement.parentElement.querySelectorAll('.box').forEach(o=>{if(o!==t){o.dataset.lock=1;o.scrollLeft=t.scrollLeft;o.scrollTop=t.scrollTop;requestAnimationFrame(()=>delete o.dataset.lock)}})},true);
document.getElementById('sel').onchange=function(){show(+this.value)};
document.getElementById('size').onclick=function(){document.body.classList.toggle('full');this.classList.toggle('on')};
document.getElementById('exp').onclick=()=>{const t=document.getElementById('out'),tal={};
 secs.forEach(s=>{const v=R[s.id];if(!v)return;const k=s.dataset.m+' ('+s.dataset.s+')',c=tal[k]=tal[k]||{};c[v]=(c[v]||0)+1});
 t.hidden=false;t.value='Beste Variante je Modell und Größe (Anzahl Seiten):\\n'+Object.entries(tal).sort().map(([k,c])=>k+': '+Object.entries(c).map(x=>x[0]+' '+x[1]).join(', ')).join('\\n')
  +'\\n\\nEinzeln:\\n'+secs.filter(s=>R[s.id]).map(s=>s.dataset.label+': '+R[s.id]).join('\\n');t.select()};
document.getElementById('clr').onclick=()=>{if(confirm('Alle Bewertungen löschen?')){R={};save();paint()}};
paint();const h=secs.findIndex(s=>s.id===location.hash.slice(1));show(h<0?0:h);
"""


def cmd_compare(a):
    """vergleich.html: a page per model, prompt, size and seed with the variants side by side (turbo, standard, 75 % steps)."""
    out = latest(a.folder)
    recs = json.load(open(out / "records.json", encoding="utf-8"))
    secs, models_seen = [], {}
    for mk in dict.fromkeys(r["model_key"] for r in recs):
        for pname in PROMPTS:
            for sname in SIZES:
                for seed in dict.fromkeys(r["seed"] for r in recs):
                    row = {r["variant"]: r for r in recs if r["model_key"] == mk and r["prompt"] == pname and r["size"] == sname and r["seed"] == seed}
                    vs = [v for v in CMP_ORDER if v in row]
                    if len(vs) < 2:
                        continue
                    label0 = row[vs[0]]["model"]
                    models_seen[mk] = label0
                    sid = f"{mk}-{pname}-{sname}-s{seed}"
                    label = f"{label0} - {pname} - {sname} - seed {seed}"
                    cells = []
                    for v in vs:
                        r = row[v]
                        f = html.escape(r["file"])
                        lora = {"on": "Turbo-LoRA an", "off": "Turbo-LoRA aus", "n/a": "ohne Turbo-Schalter"}[r["lora"]]
                        got = "x".join(map(str, r.get("got", r["asked"])))
                        cells.append(f'<div class="cell"><div class="meta"><b>{v}</b>: {r["steps"]} steps, cfg {r["cfg"]}, {lora}</div>'
                                     f'<div class="box"><img src="bilder/{f}" loading="lazy" alt="{f}"></div>'
                                     f'<div class="meta">{got}, {r.get("seconds", 0):.0f} s</div></div>')
                    picks = "".join(f'<button data-v="{v}">{v} ist am besten</button>' for v in vs) + '<button data-v="gleich">gleich gut</button>'
                    secs.append(f'<section id="{sid}" data-label="{html.escape(label)}" data-m="{mk}" data-s="{sname}"><h2>{html.escape(label)}</h2>'
                                f'<div class="row" style="--n:{len(vs)}">{"".join(cells)}</div><div class="pick">{picks}</div></section>')
    mbtn = "".join(f'<button data-m="{k}">{html.escape(l)}</button>' for k, l in models_seen.items())
    sel = "".join(f'<option value="{i}"></option>' for i in range(len(secs)))
    (out / "vergleich.html").write_text(
        f'<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>Text to image: Variantenvergleich</title><style>{CMP_CSS}</style></head><body data-key="t2i-cmp-{out.name}">'
        f'<header><h1>Variantenvergleich</h1>{mbtn}</header>'
        f'<header style="position:static"><select id="sel">{sel}</select><button onclick="show(cur-1)">&larr; zurück</button><button onclick="show(cur+1)">weiter &rarr;</button>'
        f'<button id="size">Originalgröße (100 %, gemeinsam scrollen)</button><button id="exp">Bewertung als Text</button><button id="clr">Löschen</button>'
        f'<span id="cnt" style="color:var(--mut)"></span></header>'
        f'<main>{"".join(secs)}<textarea id="out" hidden></textarea></main><dialog id="zoom"><img alt=""></dialog><script>{CMP_JS}</script></body></html>',
        encoding="utf-8")
    print(out / "vergleich.html", f"({len(secs)} Seiten)")


def cmd_summary(a):
    out = latest(a.folder)
    recs = json.load(open(out / "records.json", encoding="utf-8"))
    lines = [f"# Text-to-image-Größen {out.name}", "", "Median der Sekunden pro Bild (Seeds und Prompts; der Median fängt die Ladezeit des ersten Bildes ab):", "",
             "| Modell | Variante | Steps | " + " | ".join(SIZES) + " |", "|---|---|---|" + "---|" * len(SIZES)]
    for mk in dict.fromkeys(r["model_key"] for r in recs):
        for vname in dict.fromkeys(r["variant"] for r in recs if r["model_key"] == mk):
            sel = [r for r in recs if r["model_key"] == mk and r["variant"] == vname]
            cells = []
            for sname in SIZES:
                t = [r["seconds"] for r in sel if r["size"] == sname and "seconds" in r]
                cells.append(f"{statistics.median(t):.0f} s" if t else "-")
            lines.append(f"| {sel[0]['model']} | {vname} | {sel[0]['steps']} | " + " | ".join(cells) + " |")
    off = [r for r in recs if "got" in r and r["got"] != r["asked"]]
    lines += ["", f"Bilder mit anderer Größe als verlangt: {len(off)}"] + [f"- {r['file']}: verlangt {r['asked']}, bekommen {r['got']}" for r in off]
    text = "\n".join(lines) + "\n"
    (out / "zeiten.md").write_text(text, encoding="utf-8")
    print(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "run"):
        r = sub.add_parser(name)
        r.add_argument("--seeds", type=int, default=2, help="seeds per prompt and size (1 or 2)")
        r.add_argument("--models", nargs="+", default=list(MODELS), choices=MODELS)
        r.add_argument("--dry", action="store_true", help="build all graphs, queue nothing")
        r.add_argument("--only", nargs="+", choices=("standard", "turbo", "steps75"), help="only these variants")
        r.add_argument("--into", help="redo the --only variants inside this existing round's folder")
    for name in ("sheets", "summary", "pages", "compare"):
        s = sub.add_parser(name)
        s.add_argument("folder", nargs="?", help="the round's folder (default: the newest)")
    a = ap.parse_args()
    {"plan": cmd_plan, "run": cmd_run, "sheets": cmd_sheets, "summary": cmd_summary, "pages": cmd_pages, "compare": cmd_compare}[a.cmd](a)


if __name__ == "__main__":
    main()
