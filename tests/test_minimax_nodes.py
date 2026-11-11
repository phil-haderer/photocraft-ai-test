"""MiniMax H3 Image's prompt writer is a chain of three nodes (PLAN 2.0b, step 2): the pc:prompt node is a StringReplace
that puts the typed text into the official task prompt (`pc_prompt_key` "replace"), a TextGenerateV2 writes JSON, a
JsonExtractString (`pc_prompt_out`) takes "expanded_caption" out for MiniMaxH3ImageConditioning. The plugin treats the
chain as one writer: the typed text lands in "replace", "Enhance prompt" off drops the whole chain and the conditioning
gets the typed text, the progress display counts the chain as prompt writing, the conditioning's width / height take the
size (pc:size). Writers of one node (Qwen's TextGenerate) work as before. Run: python tests/test_minimax_nodes.py"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import workflows
from pccomfy.bridge import after_prompt_nodes, prompt_phase_nodes
from pccomfy.workflows import GenParams

G = {
    "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "u.safetensors", "weight_dtype": "default"}},
    "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "enc.safetensors", "type": "minimax", "device": "default"}},
    "3": {"class_type": "VAELoader", "inputs": {"vae_name": "vae.safetensors"}},
    "5": {"class_type": "MiniMaxH3ImageConditioning", "_meta": {"title": "pc:size Conditioning"},
          "inputs": {"clip": ["2", 0], "vae": ["3", 0], "prompt": ["26", 0], "width": 2048, "height": 2048}},
    "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
    "7": {"class_type": "KSampler", "_meta": {"title": "pc:sampler"},
          "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["5", 1], "seed": 1,
                     "steps": 6, "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
    "9": {"class_type": "PreviewImage", "_meta": {"title": "pc:output"}, "inputs": {"images": ["8", 0]}},
    "15": {"class_type": "TextGenerateV2", "inputs": {"clip": ["16", 0], "system_prompt": ["17", 0], "prompt": ["19", 0],
                                                      "max_length": 8192, "sampling_mode": "on", "thinking": True}},
    "16": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3.5_9b_w4a8_gptq.safetensors", "type": "minimax", "device": "default"}},
    "17": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "system"}},
    "18": {"class_type": "PreviewAny", "_meta": {"title": "pc:vgl"}, "inputs": {"source": ["26", 0]}},
    "19": {"class_type": "StringReplace",
           "_meta": {"title": "pc:prompt", "pc_prompt_key": "replace", "pc_prompt_out": "26", "pc_llm_name": "Qwen 3.5 9B"},
           "inputs": {"string": ["20", 0], "find": "{input text}", "replace": ""}},
    "20": {"class_type": "PrimitiveStringMultiline", "inputs": {"value": "task ... input_text: {input text}"}},
    "26": {"class_type": "JsonExtractString", "inputs": {"json_string": ["15", 0], "key": "expanded_caption"}},
}

# the typed text goes into "replace" of the StringReplace (not into a new "prompt" field); the size into the conditioning
g, out = workflows.apply_template(G, GenParams(prompt="a red fox", seed=7, width=3072, height=2048), None, None)
assert g["19"]["inputs"]["replace"] == "a red fox" and "prompt" not in g["19"]["inputs"], g["19"]
assert g["19"]["inputs"]["string"] == ["20", 0] and g["5"]["inputs"]["prompt"] == ["26", 0]
assert (g["5"]["inputs"]["width"], g["5"]["inputs"]["height"]) == (3072, 2048) and out == "9"
assert g["7"]["inputs"]["seed"] == 7

# the chain: StringReplace, TextGenerateV2, JsonExtractString (not the loaders or the task prompt above it)
assert workflows.prompt_writers(G) == ["19"] and workflows.writer_end(G, "19") == "26"
assert workflows.writer_chain(G) == {"19", "15", "26"}, workflows.writer_chain(G)
assert workflows.writer_name(G) == "Qwen 3.5 9B"

# Enhance off: the conditioning gets the typed text, the chain and the pc:vgl preview drop out
off = workflows.bypass_prompt_writer(g, "a red fox")
assert off["5"]["inputs"]["prompt"] == "a red fox", off["5"]
assert not {"15", "18", "19", "26"} & set(off), sorted(off)
assert all(not (isinstance(v, list) and v and str(v[0]) not in off)
           for n in off.values() for v in n["inputs"].values()), "a link to a removed node is left"

# progress display: the whole chain and what feeds it is "prompt", the conditioning onwards is "image"
assert prompt_phase_nodes(G) >= {"15", "16", "17", "19", "20", "26"}, prompt_phase_nodes(G)
assert {"5", "6", "7", "8", "9"} <= after_prompt_nodes(G) and not {"15", "26"} & after_prompt_nodes(G)

# a one-node writer (Qwen Image 2.1: TextGenerate titled pc:prompt) works as before
ROOT = Path(__file__).resolve().parent.parent
q = json.loads((ROOT / "workflows" / "qwen-image-21-t2i.json").read_text(encoding="utf-8"))
assert workflows.writer_chain(q) == {"15"}
qg, _ = workflows.apply_template(q, GenParams(prompt="a cat"), None, None)
assert qg["15"]["inputs"]["prompt"] == "a cat"
qoff = workflows.bypass_prompt_writer(qg, "a cat")
assert "15" not in qoff and "17" not in qoff and qoff["8"]["inputs"]["prompt"] == "a cat"
assert prompt_phase_nodes(q) >= {"14", "15", "16"} and "10" in after_prompt_nodes(q)
print("ALL OK (MiniMax writer chain, one-node writers unchanged)")
