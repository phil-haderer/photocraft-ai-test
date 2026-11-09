"""Scribble on photo (Sketch, docs/sketch-plan.md, decisions of 9.11. evening): find the scribble, cut the crop around it, and
put the result back only there. No Tk, no PhotoCraft: the bridge hands in pictures and gets pictures back.

The settings are the ones the blind test rounds 5 to 7 rated best (docs/tests/sketch-ergebnis.md):
- the scribble is found on its own layer (the top layer, mostly transparent, one colour), else by colour: bright green
  first, then pure red (round 7: on a red neon wall the wall outweighed a green scribble when the larger area won);
  a scribble covers at least MIN_SHARE of the picture (clean photos had red specks of 107 and 314 pixels, the smallest
  real scribble 2410);
- only a crop around it is generated: the box (+ 8 %) grown by CONTEXT (40 %; 100 % gave twice the faults);
- the result is shifted to the photo's colours in the ring around the scribble (mean and spread per channel, spread
  held to 0.7 .. 1.4) and comes back opaque over the box, fading to 0 at the crop's sides (as Fill with Qwen and Fibo).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageFilter

from . import fillmask, imaging

RED = (252, 2, 2)          # as measured on the user's scribbles
GREEN = (0, 255, 0)        # bright pure green (user 9.11.: for photos with much red)
PAD = 0.08                 # the box around the strokes, a little larger
MIN_SHARE = 0.0005         # 0.05 % of the picture (about 1000 pixels at 2 MP)
CONTEXT = 0.4              # the crop around the box, as Remove with Flux and Qwen
RING_PAD = 0.20            # the colour match leaves out the box + 20 % (where the new object may reach)
FEATHER_PCT = 10.0         # soft edge in % of the box's shorter side
LAYER_MAX_SHARE = 0.5      # a scribble layer covers at most half of the canvas
LAYER_ONE_COLOUR = 0.9     # ... and at least 90 % of its solid pixels are near its main colour
LAYER_THIN_PX = 0.004      # ... and it is thin: shrunk by 0.4 % of the shorter canvas side (at least 4 px) ...
LAYER_THIN_LEFT = 0.5      # ... at most half of it is left


@dataclass
class Found:
    box: imaging.Box       # the strokes' box, PAD larger, in canvas pixels
    box20: imaging.Box     # the same with RING_PAD (the part the colour match leaves out)
    how: str               # "layer", "green" or "red"


def colour_pixels(a: np.ndarray, colour) -> np.ndarray:
    """Where an RGB array is the scribble's pure colour: its strongest channel above 200 and 140 above both others."""
    c = int(np.argmax(colour))
    o = [i for i in range(3) if i != c]
    return (a[..., c] > 200) & (a[..., c] - a[..., o[0]] > 140) & (a[..., c] - a[..., o[1]] > 140)


def _pad(x0: int, y0: int, x1: int, y1: int, size: tuple[int, int], pad: float) -> imaging.Box:
    W, H = size
    dx, dy = round((x1 - x0) * pad), round((y1 - y0) * pad)
    x0, y0, x1, y1 = max(0, x0 - dx), max(0, y0 - dy), min(W - 1, x1 + dx), min(H - 1, y1 + dy)
    return imaging.Box(int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1))


def _largest_area(hit: np.ndarray) -> tuple[int, tuple | None]:
    """(pixels, (x0, y0, x1, y1)) of the largest connected area of `hit`; connected on a grid 8 times smaller with the
    lines thickened, so a scribble drawn in several strokes stays one area (as tests/live_sketch.py scribble_box)."""
    if hit.sum() < 1:
        return 0, None
    H, W = hit.shape
    k = 8
    small = Image.fromarray((hit * 255).astype("uint8")).resize((max(1, W // k), max(1, H // k)), Image.BOX)
    grid = np.asarray(small.point(lambda v: 255 if v > 0 else 0).filter(ImageFilter.MaxFilter(7))) > 0
    seen = np.zeros_like(grid, dtype=bool)
    best = (0, None)
    for y0, x0 in zip(*np.nonzero(grid)):
        if seen[y0, x0]:
            continue
        stack, comp = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            comp.append((y, x))
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < grid.shape[0] and 0 <= xx < grid.shape[1] and grid[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    stack.append((yy, xx))
        cy0, cy1 = min(c[0] for c in comp) * k, (max(c[0] for c in comp) + 1) * k
        cx0, cx1 = min(c[1] for c in comp) * k, (max(c[1] for c in comp) + 1) * k
        part = hit[cy0:cy1, cx0:cx1]
        n = int(part.sum())
        if n > best[0]:
            ys, xs = np.nonzero(part)
            best = (n, (int(xs.min() + cx0), int(ys.min() + cy0), int(xs.max() + cx0), int(ys.max() + cy0)))
    return best


def colour_area(im: Image.Image, colour) -> tuple[int, imaging.Box | None]:
    """(pixels of `colour` in its largest connected area, its box + PAD); (0, None) when there is none."""
    a = np.asarray(im.convert("RGB")).astype(int)
    n, xy = _largest_area(colour_pixels(a, colour))
    return (n, _pad(*xy, im.size, PAD)) if xy else (0, None)


def _found(xy: tuple, size: tuple[int, int], how: str) -> Found:
    return Found(_pad(*xy, size, PAD), _pad(*xy, size, RING_PAD), how)


def find_by_colour(im: Image.Image) -> Found | None:
    """Green first, then red; None when neither has a scribble of at least MIN_SHARE of the picture."""
    a = np.asarray(im.convert("RGB")).astype(int)
    least = MIN_SHARE * im.width * im.height
    for colour, how in ((GREEN, "green"), (RED, "red")):
        n, xy = _largest_area(colour_pixels(a, colour))
        if xy and n >= least:
            return _found(xy, im.size, how)
    return None


def is_scribble_layer(layer: Image.Image) -> bool:
    """A layer (RGBA, canvas size) that looks like strokes on an empty layer: at least MIN_SHARE and at most LAYER_MAX_SHARE
    of the canvas visible, its solid pixels nearly all of one colour, and thin (a cut-out person or object on its own layer
    is many colours and solid, a photo layer covers the canvas). A solidly filled blob on its own layer does not count:
    then the colour search decides."""
    rgba = np.asarray(layer.convert("RGBA")).astype(int)
    alpha = rgba[..., 3]
    seen = alpha > 8
    share = seen.mean()
    if not (MIN_SHARE <= share <= LAYER_MAX_SHARE):
        return False
    solid = rgba[..., :3][alpha > 200]
    if len(solid) < 20:
        return False
    main = np.median(solid, axis=0)
    near = np.abs(solid - main).sum(-1) < 90
    if near.mean() < LAYER_ONE_COLOUR:
        return False
    # strokes are thin: shrunk by a few pixels, little of them is left (the user's round 6 scribbles: at most 10 %; a cut-out,
    # even of a plain one-coloured area: at least 81 %)
    r = max(4, round(LAYER_THIN_PX * min(layer.size)))
    m = Image.fromarray((seen * 255).astype(np.uint8)).filter(ImageFilter.MinFilter(2 * r + 1))
    return bool((np.asarray(m) > 0).sum() <= LAYER_THIN_LEFT * seen.sum())


def find_on_layer(layer: Image.Image) -> Found | None:
    """The scribble on its own layer (any colour): the box of its largest connected area (a stray dot elsewhere on the
    layer does not count); None when it is no scribble layer."""
    if not is_scribble_layer(layer):
        return None
    _n, xy = _largest_area(np.asarray(layer.convert("RGBA"))[..., 3] > 8)
    return _found(xy, layer.size, "layer") if xy else None


def find(picture: Image.Image, top_layer: Image.Image | None = None) -> Found | None:
    """The decided order (9d): the top layer when it is a scribble layer, else the colours of the whole picture."""
    if top_layer is not None:
        hit = find_on_layer(top_layer)
        if hit:
            return hit
    return find_by_colour(picture)


def region(found: Found, size: tuple[int, int]) -> imaging.Box:
    """The crop the model gets: the box grown by CONTEXT, inside the canvas."""
    return imaging.grow_box(found.box, size, CONTEXT)


def box_mask(size: tuple[int, int], box: imaging.Box, feather_pct: float = FEATHER_PCT) -> Image.Image:
    """Opaque over `box`, soft outwards by feather_pct of its shorter side (the rectangle grown by the radius, then
    blurred); canvas size. Used for the ring the colour match leaves out."""
    r = imaging.feather_radius(box.w, box.h, feather_pct)
    m = Image.new("L", size, 0)
    m.paste(255, (max(0, box.x - r), max(0, box.y - r), min(size[0], box.x + box.w + r), min(size[1], box.y + box.h + r)))
    return m.filter(ImageFilter.GaussianBlur(r / 2.0)) if r > 0 else m


def fade_mask(size: tuple[int, int], box: imaging.Box, reg: imaging.Box, feather_pct: float = FEATHER_PCT) -> Image.Image:
    """The layer mask: opaque over the box, then a smooth fade that reaches 0 exactly at the crop's sides inside the
    picture (fillmask.crop_fade, as Fill with Qwen and Fibo); canvas size, 0 outside the crop."""
    W, H = size
    m = Image.new("L", (reg.w, reg.h), 0)
    m.paste(255, (box.x - reg.x, box.y - reg.y, box.x - reg.x + box.w, box.y - reg.y + box.h))
    inner = (reg.x > 0, reg.y > 0, reg.x + reg.w < W, reg.y + reg.h < H)
    soft = fillmask.crop_fade(m, imaging.feather_radius(box.w, box.h, feather_pct), inner)
    full = Image.new("L", (W, H), 0)
    full.paste(soft, (reg.x, reg.y))
    return full


def colour_match(result: Image.Image, photo: Image.Image, ring: np.ndarray) -> Image.Image:
    """`result` (same size as `photo`) shifted per channel to the mean and spread of `photo` where `ring` is True; the
    spread change held to 0.7 .. 1.4. Unchanged when the ring is under 100 pixels."""
    r = np.asarray(result.convert("RGB")).astype(float)
    p = np.asarray(photo.convert("RGB")).astype(float)
    if ring.sum() < 100:
        return result.convert("RGB")
    out = r.copy()
    for c in range(3):
        mr, sr = r[..., c][ring].mean(), r[..., c][ring].std() + 1e-6
        mp, sp = p[..., c][ring].mean(), p[..., c][ring].std()
        out[..., c] = (r[..., c] - mr) * min(1.4, max(0.7, sp / sr)) + mp
    return Image.fromarray(np.clip(np.round(out), 0, 255).astype(np.uint8))


def context_ring(size: tuple[int, int], reg: imaging.Box, leave_out: Image.Image) -> np.ndarray:
    """True inside the crop `reg` where `leave_out` is 0: the photo around the scribble the model should have kept."""
    W, H = size
    ring = np.zeros((H, W), bool)
    ring[reg.y:reg.y + reg.h, reg.x:reg.x + reg.w] = True
    return ring & (np.asarray(leave_out) == 0)


def put_back(photo: Image.Image, result: Image.Image, found: Found, reg: imaging.Box) -> tuple[Image.Image, Image.Image]:
    """The new layer (canvas size: the photo with the model's crop pasted at `reg`, colour matched) and its layer mask
    (fade_mask). Where the mask is 0 the layer shows the photo unchanged."""
    size = photo.size
    layer = photo.convert("RGB").copy()
    layer.paste(result.convert("RGB").resize((reg.w, reg.h), Image.LANCZOS), (reg.x, reg.y))
    ring = context_ring(size, reg, box_mask(size, found.box20))
    return colour_match(layer, photo, ring), fade_mask(size, found.box, reg)
