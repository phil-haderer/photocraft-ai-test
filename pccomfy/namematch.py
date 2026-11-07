"""Which of your files is probably a missing model file under another name: a similarity of file names that knows model families.

No Tk, no ComfyUI. The idea and the rules (fp8 / bf16 / Q4_K_M are the same model in another precision, a 4B is not an 8B, qwen2 is
not qwen3) are adapted from the matcher of ComfyUI Model Linker by kianxyzw (MIT, Copyright (c) 2025 kianxyzw, licence text in
``pccomfy/assets/LICENSE-model-linker.txt``), rewritten here with ``difflib`` only (no extra package).

A suggestion is only a hint ("a file with a similar name"): the user checks it and links it with the chain symbol."""
from __future__ import annotations

import os
import re
from difflib import SequenceMatcher

# precision / quant tokens: fp8, bf16, int8, q4, iq3, nvfp4, e4m3fn ...
_VARIANT_TOKEN = re.compile(r"^(?:(?:bf|bfloat|fp|float|int|uint|f|i)\d+(?:mixed|scaled)?|(?:i?q|tq)\d+|(?:mxfp|nvfp)\d+|e\d+m\d+(?:fnuz|fn)?|bnb\d+)$")
_VARIANT_WORDS = {"gguf", "ggml", "gptq", "awq", "exl2", "hqq", "aqlm", "nf4", "mixed", "scaled", "pruned", "ema", "emaonly", "quant",
                  "quantized", "converted", "compressed", "convrot", "w4a8"}
_QUANT_HEAD = re.compile(r"^(?:i?q|tq)\d+$")
_QUANT_TAIL = {"0", "1", "4", "8", "k", "m", "s", "l", "xl", "xs", "xxs", "nl"}
_CAPACITY_TOKEN = re.compile(r"^\d+(?:\.\d+)?[bmk]$")        # parameter count: 4b, 8b, 1.5b

SAME_FAMILY_SCORE = 0.94           # same model, other precision
SAME_SIGNATURE_SUBSET_SCORE = 0.90
SAME_SIGNATURE_SCORE = 0.84
CONFLICT_CAP = 0.69                # other size or generation of one architecture
SUGGEST_MIN = 0.85                 # below this nothing is suggested


def basename(name: str) -> str:
    return name.replace("\\", "/").rstrip("/").rpartition("/")[2]


def normalize(name: str) -> str:
    """File name without folder and extension, lower case, ``_ - .`` and spaces as single spaces."""
    base = os.path.splitext(basename(name))[0].lower()
    return re.sub(r"[_\-.\s]+", " ", base).strip()


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def family_tokens(normalized: str) -> list[str]:
    """The tokens of a normalized name without precision / quant tokens: 'flux1 dev fp8 e4m3fn' -> ['flux1', 'dev']."""
    normalized = re.sub(r"\bema only\b", "emaonly", normalized)
    out, in_tail = [], False
    for tok in normalized.split():
        if in_tail and tok in _QUANT_TAIL:
            continue
        in_tail = bool(_QUANT_HEAD.match(tok))
        if tok in _VARIANT_WORDS or _VARIANT_TOKEN.match(tok):
            continue
        out.append(tok)
    return out


def _signature(tokens: list[str]):
    """(architecture, size) from family tokens: ['qwen3', '4b', 'it'] -> ('qwen3', '4b'); None without a parameter count."""
    for i, tok in enumerate(tokens):
        if _CAPACITY_TOKEN.match(tok):
            arch = "".join(tokens[:i])
            return (arch, tok) if len(arch) >= 3 and re.search(r"[a-z]", arch) else None
    return None


def _numeric_conflict(a: str, b: str) -> bool:
    """The same name apart from version digits: qwen2 against qwen3."""
    return re.sub(r"\d", "", a) == re.sub(r"\d", "", b) and re.findall(r"\d+", a) != re.findall(r"\d+", b)


def confidence(target: str, candidate: str) -> float:
    """How likely ``candidate`` is the file ``target`` under another name (0..1). 1.0 only when equal after normalizing."""
    t, c = normalize(target), normalize(candidate)
    if t == c:
        return 1.0
    best = max(_ratio(t, c), _ratio(" ".join(sorted(t.split())), " ".join(sorted(c.split()))))
    tf, cf = family_tokens(t), family_tokens(c)
    if tf and cf:
        if tf == cf:
            best = max(best, SAME_FAMILY_SCORE)
        else:
            best = max(best, _ratio(" ".join(tf), " ".join(cf)))
            ts, cs = _signature(tf), _signature(cf)
            if ts and cs:
                if ts == cs:
                    sub = set(tf) <= set(cf) or set(cf) <= set(tf)
                    best = max(best, SAME_SIGNATURE_SUBSET_SCORE if sub else SAME_SIGNATURE_SCORE)
                elif ts[0] == cs[0]:
                    best = min(best, CONFLICT_CAP)
                elif ts[1] == cs[1] and _numeric_conflict(ts[0], cs[0]):
                    best = min(best, CONFLICT_CAP)
    return min(best, 0.999)


def suggest(expected: str, candidates, exclude=(), minimum: float = SUGGEST_MIN) -> str:
    """The candidate most like ``expected`` (at least ``minimum``), or "". Candidates whose bare name equals one of ``exclude`` (the other
    files the plugin knows: a flux2-vae_small is no stand-in for flux2-vae) are skipped. Ties: the shorter name, then alphabetical."""
    skip = {normalize(n) for n in exclude}
    best, best_score = "", minimum
    for n in sorted(candidates, key=lambda x: (len(x), x.lower())):
        if normalize(n) in skip:
            continue
        s = confidence(expected, n)
        if s > best_score or (s == best_score and not best and s >= minimum):
            best, best_score = n, s
    return best
