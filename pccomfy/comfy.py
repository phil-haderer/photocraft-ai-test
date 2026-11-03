"""Minimal ComfyUI API client (standard library + Pillow only).

Endpoints used:
  GET  /system_stats, /object_info/<Node>   – connection check, model/sampler lists
  POST /upload/image                         – upload image and mask (land in input/)
  POST /prompt                               – queue an API-format graph
  WS   /ws?clientId=…                        – progress and live preview frames (optional, needs websocket-client)
  GET  /history/<prompt_id>, /view           – fetch results
  POST /interrupt, /queue                    – cancel
"""

from __future__ import annotations

import http.client
import io
import json
import os
import socket
import sys
import struct
import threading
import time
from pathlib import Path
import uuid
import urllib.parse
from typing import Callable

from PIL import Image

try:  # `websocket-client` package (Arch: python-websocket-client) – only for the progress bar
    import websocket  # type: ignore
except Exception:  # pragma: no cover
    websocket = None


LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1", "[::1]", "0.0.0.0")


def real_comfy_blocked(host: str, port: int) -> bool:
    """True when a test script (`python tests/<name>.py`, not a `live_*.py` check) would talk to the ComfyUI of this PC (port 8188).
    A test run did that on 3.11.2026 and ended the listening socket of the user's ComfyUI three times (a client that drops
    in the middle of the connection: WinError 64 in asyncio's accept, ComfyUI alive but nothing listens). Tests use ports of
    their own; PCCOMFY_ALLOW_REAL_COMFY=1 lifts the block."""
    if port != 8188 or host not in LOCAL_HOSTS or os.environ.get("PCCOMFY_ALLOW_REAL_COMFY"):
        return False
    try:
        script = Path(sys.argv[0]).resolve()
    except (IndexError, OSError, ValueError):
        return False
    return script.parent.name == "tests" and not script.name.startswith("live_")


class ComfyError(RuntimeError):
    pass


class Cancelled(Exception):
    pass


WS_HANDSHAKE_S = 10.0       # the websocket handshake (see ComfyUI.open_events)
PREVIEW_IMAGE, PREVIEW_IMAGE_WITH_METADATA = 1, 4      # ComfyUI's binary websocket events (protocol.py BinaryEventTypes)


def preview_image(data: bytes, prompt_id: str | None = None) -> Image.Image | None:
    """A live preview frame from a binary websocket message: event 1 = image type (1 JPEG, 2 PNG) + image; event 4 =
    length + JSON metadata (with the prompt id) + image. None for anything else or a frame of another prompt."""
    try:
        if len(data) < 8:
            return None
        event, head = struct.unpack(">II", data[:8])
        if event == PREVIEW_IMAGE:
            body = data[8:]
        elif event == PREVIEW_IMAGE_WITH_METADATA:
            meta = json.loads(data[8:8 + head].decode("utf-8"))
            if prompt_id and meta.get("prompt_id") not in (None, prompt_id):
                return None
            body = data[8 + head:]
        else:
            return None
        im = Image.open(io.BytesIO(body))
        im.load()
        return im.convert("RGB")
    except Exception:
        return None


class NodeProbe:
    """Which node classes ComfyUI has, asked one class at a time (GET /object_info/<class>, an empty answer = not installed) and
    remembered. ``cls in probe`` works like a set. A class that cannot be asked counts as installed: no false alarm."""

    def __init__(self, comfy, classes=()):
        self._comfy, self._known = comfy, {}
        for c in classes:
            c in self

    def __contains__(self, cls) -> bool:
        if cls not in self._known:
            try:
                self._known[cls] = bool(self._comfy.object_info(cls))
            except (ComfyError, ValueError, AttributeError, TypeError):
                self._known[cls] = True
        return self._known[cls]


class ComfyUI:
    def __init__(self, url: str = "http://127.0.0.1:8188", timeout: float = 30.0):
        self.timeout = timeout
        self._local = threading.local()
        self._gen = 0                  # grows with every new address: an open connection of an older one is dropped
        self._set_target(url)
        self._cache: dict = {}
        self._cache_lock = threading.RLock()
        self.client_id = uuid.uuid4().hex
        self.name_fixer: Callable[[dict], object] | None = None   # called with every graph before it is queued (see inventory.apply_names)
        self.log_file: Path | None = None    # connection log (set by the Bridge: exchange/comfy-net.log); None = no log

    LOG_MAX_BYTES = 200_000

    def _log(self, event: str, **fields) -> None:
        """One line per connection event (websocket opened / closed / failed, a request that found no ComfyUI, the end of a
        wait) in comfy-net.log: to find out afterwards what the plugin was doing when ComfyUI stopped listening (WinError 64).
        Never raises; the file keeps its last half when it grows past LOG_MAX_BYTES."""
        f = self.log_file
        if f is None:
            return
        try:
            line = time.strftime("%Y-%m-%d %H:%M:%S") + f" [{threading.current_thread().name}] {event}"
            line += "".join(f" {k}={v}" for k, v in fields.items())
            f.parent.mkdir(parents=True, exist_ok=True)
            if f.exists() and f.stat().st_size > self.LOG_MAX_BYTES:
                keep = f.read_text(encoding="utf-8", errors="replace").splitlines()[-1000:]
                f.write_text("\n".join(keep) + "\n", encoding="utf-8")
            with f.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        except (OSError, ValueError):
            pass

    # ---------- HTTP ----------

    # Lists that rarely change are read at most once per CACHE_SECONDS (start, "Refresh", opening the settings window and a
    # download each ask for them; fired together they were 16 connections within a second, 30.10.). GETs share one
    # keep-alive connection per thread; a POST gets a connection of its own (a stale one must never send a job twice).
    CACHE_SECONDS = 10.0
    _CACHED = ("/system_stats", "/object_info", "/models/")

    def _set_target(self, url: str) -> None:
        self.url = url.rstrip("/")
        parts = urllib.parse.urlsplit(self.url)
        self._https = parts.scheme == "https"
        self._host, self._port = parts.hostname or "127.0.0.1", parts.port or (443 if self._https else 80)

    def set_url(self, url: str) -> None:
        """Talk to another server from now on (Other settings > ComfyUI address): the lists of the old one are forgotten."""
        with self._cache_lock:
            self._gen += 1
            self._set_target(url)
            self._cache.clear()

    def invalidate(self) -> None:
        """Forget the cached lists (a file was just added)."""
        with self._cache_lock:
            self._cache.clear()

    def _new_connection(self) -> http.client.HTTPConnection:
        cls = http.client.HTTPSConnection if self._https else http.client.HTTPConnection
        return cls(self._host, self._port, timeout=self.timeout)

    def _connection(self, fresh: bool) -> http.client.HTTPConnection:
        if fresh:
            return self._new_connection()
        conn = getattr(self._local, "conn", None)
        if conn is not None and getattr(self._local, "gen", None) != self._gen:
            conn.close()
            conn = None
        if conn is None:
            conn = self._local.conn = self._new_connection()
            self._local.gen = self._gen
        return conn

    def _request(self, path: str, data: bytes | None = None, headers: dict | None = None, method: str | None = None):
        method = method or ("POST" if data is not None else "GET")
        if real_comfy_blocked(self._host, self._port):
            raise ComfyError("Blocked: a test must not talk to the real ComfyUI on port 8188.")
        fresh = method != "GET"
        for attempt in (0, 1):
            conn = self._connection(fresh)
            reused = not fresh and getattr(conn, "sock", None) is not None
            try:
                conn.request(method, path, body=data, headers=headers or {})
                r = conn.getresponse()
                body, status = r.read(), r.status
                break
            except (http.client.HTTPException, OSError) as e:
                conn.close()
                if not fresh:
                    self._local.conn = None
                if reused and attempt == 0:       # the server closed an idle connection: once more on a new one (GET only)
                    continue
                self._log("http_failed", method=method, path=path.split("?")[0], attempt=attempt, error=repr(e)[:160])
                # never the system's own text (strerror is German on a German Windows): our English wording only
                if isinstance(e, (TimeoutError, socket.timeout)):
                    raise ComfyError(f"ComfyUI at {self.url} does not answer. Is it running? Start it, then click Refresh.") from None
                raise ComfyError(f"ComfyUI is not running at {self.url}. Start it, then click Refresh.") from None
            finally:
                if fresh:
                    conn.close()
        if status >= 400:
            raise ComfyError(self._explain(status, body.decode(errors="replace")))
        return body

    def _json(self, path: str, payload=None):
        data = None if payload is None else json.dumps(payload).encode()
        headers = {"Content-Type": "application/json"} if data else {}
        if data is None and path.startswith(self._CACHED):
            with self._cache_lock:        # one reader at a time: a second thread gets the first one's answer
                hit = self._cache.get(path)
                if hit is not None and time.monotonic() - hit[0] < self.CACHE_SECONDS:
                    return hit[1]
                raw = self._request(path, None, headers)
                out = json.loads(raw) if raw else None
                self._cache[path] = (time.monotonic(), out)
                return out
        raw = self._request(path, data, headers)
        return json.loads(raw) if raw else None

    @staticmethod
    def _explain(code: int, body: str) -> str:
        """Readable message from a graph validation error (400 from /prompt)."""
        try:
            j = json.loads(body)
        except ValueError:
            return f"ComfyUI HTTP {code}: {body[:500]}"
        lines = []
        err = j.get("error")
        if isinstance(err, dict):
            lines.append(err.get("message", ""))
            if err.get("details"):
                lines.append(err["details"])
        for node_id, ne in (j.get("node_errors") or {}).items():
            for e in ne.get("errors", []):
                lines.append(f"node {node_id} ({ne.get('class_type')}): {e.get('message')} – {e.get('details')}")
        return "ComfyUI rejected the job:\n" + "\n".join(x for x in lines if x)

    # ---------- info ----------

    def system_stats(self) -> dict:
        return self._json("/system_stats")

    def object_info(self, node: str) -> dict:
        return self._json(f"/object_info/{urllib.parse.quote(node)}").get(node, {})

    def _choices(self, node: str, field: str) -> list[str]:
        try:
            spec = self.object_info(node)["input"]["required"][field]
        except (KeyError, ComfyError):
            return []
        # old format: [[...list...], {...}], new: ["COMBO", {"options": [...]}]
        if isinstance(spec[0], list):
            return spec[0]
        if len(spec) > 1 and isinstance(spec[1], dict):
            return spec[1].get("options", [])
        return []

    def checkpoints(self) -> list[str]:
        return self._choices("CheckpointLoaderSimple", "ckpt_name")

    def clips(self) -> list[str]:
        return self._choices("CLIPLoader", "clip_name")

    def loras(self) -> list[str]:
        return self._choices("LoraLoaderModelOnly", "lora_name")

    def samplers(self) -> list[str]:
        return self._choices("KSampler", "sampler_name")

    def schedulers(self) -> list[str]:
        return self._choices("KSampler", "scheduler")

    def _folder(self, folder: str) -> list[str]:
        """The files in one of ComfyUI's model folders (GET /models/<folder>); [] when it cannot be read."""
        try:
            j = self._json("/models/" + urllib.parse.quote(folder))
        except (ComfyError, ValueError):
            return []
        return [str(x) for x in j] if isinstance(j, list) else []

    def inventory_raw(self, classes=()) -> dict:
        """Model files per loader kind (unet, clip, vae, lora) and ("nodes") a ``NodeProbe`` that answers "is this node class
        installed?" with one small /object_info/<class> call per class (``classes`` are asked up front); the full /object_info
        is 5 MB and took about 2 s. Raises ComfyError when the server cannot be reached, because the empty lists _choices
        gives then would look like "nothing is installed"."""
        self.system_stats()
        out = {
            "unet": self._choices("UNETLoader", "unet_name"),
            "clip": self._choices("CLIPLoader", "clip_name"),
            "vae": self._choices("VAELoader", "vae_name"),
            "lora": self._choices("LoraLoaderModelOnly", "lora_name"),
            "preview": self._folder("vae_approx"),      # the live preview decoders (TAESD) have no loader node
            "bg_removal": self._choices("LoadBackgroundRemovalModel", "bg_removal_name"),
            "upscale_model": self._choices("UpscaleModelLoader", "model_name"),
        }
        out["nodes"] = NodeProbe(self, classes)
        return out

    # ---------- image I/O ----------

    def upload_image(self, image: Image.Image, name: str) -> str:
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        boundary = uuid.uuid4().hex
        parts = []
        for key, value in (("overwrite", "true"), ("type", "input"), ("subfolder", "pccomfy")):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{name}"\r\n'
            f"Content-Type: image/png\r\n\r\n".encode() + buf.getvalue() + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        raw = self._request("/upload/image", b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        j = json.loads(raw)
        return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]

    def view(self, filename: str, subfolder: str = "", type_: str = "output") -> Image.Image:
        q = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": type_})
        return Image.open(io.BytesIO(self._request(f"/view?{q}")))

    # ---------- execution ----------

    def queue(self, graph: dict, preview: str | None = None) -> str:
        """preview: ComfyUI's preview method for this prompt only ("taesd" uses the TAESD file of the model when it is in
        models/vae_approx and falls back to the coarse latent2rgb colours; "none"); None = ComfyUI's start setting."""
        if self.name_fixer is not None:
            self.name_fixer(graph)
        payload = {"prompt": graph, "client_id": self.client_id}
        if preview:
            payload["extra_data"] = {"preview_method": preview}
        j = self._json("/prompt", payload)
        if j.get("node_errors"):
            raise ComfyError(self._explain(400, json.dumps(j)))
        return j["prompt_id"]

    def interrupt(self, prompt_id: str | None = None) -> None:
        try:
            if prompt_id:
                self._json("/queue", {"delete": [prompt_id]})
            self._json("/interrupt", {"prompt_id": prompt_id} if prompt_id else {})
        except ComfyError:
            pass

    def history(self, prompt_id: str) -> dict | None:
        return self._json(f"/history/{prompt_id}").get(prompt_id)

    def open_events(self):
        """The websocket for progress and preview frames, or None (no websocket-client, or ComfyUI does not answer). Open it
        BEFORE the job is queued, so no early message is lost. The handshake gets WS_HANDSHAKE_S: a busy ComfyUI (loading a
        model) must not see the client give up in the middle of it, that can kill its listening socket on Windows (WinError 64,
        asyncio accept). Afterwards recv() times out after 1 s: the heartbeat of wait()."""
        if websocket is None or real_comfy_blocked(self._host, self._port):
            return None
        ws = None
        t0 = time.monotonic()
        try:
            ws = websocket.create_connection(self.url.replace("http", "ws", 1) + f"/ws?clientId={self.client_id}",
                                             timeout=WS_HANDSHAKE_S)
            ws.settimeout(1)
            self._log("ws_open", id=id(ws) % 10000, ms=round((time.monotonic() - t0) * 1000))
            return ws
        except Exception as e:
            self._log("ws_open_failed", ms=round((time.monotonic() - t0) * 1000), error=repr(e)[:160])
            self.close_events(ws)
            return None

    def close_events(self, ws) -> None:
        """Closes a websocket, whatever its state; never raises."""
        if ws is None:
            return
        try:
            ws.close()
            self._log("ws_close", id=id(ws) % 10000)
        except Exception as e:
            self._log("ws_close_failed", id=id(ws) % 10000, error=repr(e)[:160])

    def wait(self, prompt_id: str, on_progress: Callable[..., None] | None = None,
             cancelled: Callable[[], bool] | None = None, timeout: float = 1800,
             on_preview: Callable[[Image.Image], None] | None = None, ws=None) -> dict:
        """Wait for the job to finish. Progress via websocket when available, else poll /history. on_preview gets each
        live preview frame (a PIL image) the sampler sends. `ws`: a websocket the caller opened before queueing
        (open_events; the caller closes it); without one, wait() opens its own and closes it."""
        # on_progress(fraction, message, node=<id of the node ComfyUI is executing, or None>);
        # fraction is -1 when the node reports no progress (e.g. a text model writing the prompt).
        on_progress = on_progress or (lambda f, msg, node=None: None)
        current = None
        cancelled = cancelled or (lambda: False)
        deadline = time.monotonic() + timeout
        own = ws is None
        if own:
            ws = self.open_events()
        t_wait = time.monotonic()
        self._log("wait_start", prompt=prompt_id[:8], ws="yes" if ws is not None else "no (polling)", own=own)
        try:
            while time.monotonic() < deadline:
                if cancelled():
                    self.interrupt(prompt_id)
                    raise Cancelled()
                if ws is not None:
                    try:
                        msg = ws.recv()
                    except websocket.WebSocketTimeoutException:
                        msg = None
                        on_progress(-1, "", current)  # heartbeat (~1/s): lets the UI show elapsed time
                    except Exception as e:
                        self._log("ws_recv_failed", prompt=prompt_id[:8], error=repr(e)[:160])
                        self.close_events(ws)      # a socket that failed is closed, not dropped
                        ws = None
                        msg = None
                    if isinstance(msg, (bytes, bytearray)):
                        im = preview_image(bytes(msg), prompt_id) if on_preview else None
                        if im is not None:
                            on_preview(im)
                        continue
                    if isinstance(msg, str):
                        m = json.loads(msg)
                        d = m.get("data", {})
                        if d.get("prompt_id") not in (None, prompt_id):
                            continue
                        if m["type"] == "executing" and d.get("node") is not None:
                            current = str(d["node"])
                            on_progress(-1, "", current)
                        elif m["type"] == "progress" and d.get("max"):
                            on_progress(d["value"] / d["max"], f"step {d['value']}/{d['max']}",
                                        str(d.get("node") or current or "") or None)
                        elif m["type"] == "execution_error":
                            raise ComfyError(f"Error in node {d.get('node_type')}: {d.get('exception_message')}")
                        elif m["type"] == "executing" and d.get("node") is None:
                            break
                        elif m["type"] == "execution_success":
                            break
                        continue
                else:
                    time.sleep(0.5)
                h = self.history(prompt_id)
                if h and h.get("status", {}).get("completed") is not None and (
                        h["status"].get("completed") or h["status"].get("status_str") == "error"):
                    break
                if ws is None:
                    on_progress(-1, "generating…", current)
            else:
                raise ComfyError("Timed out waiting for ComfyUI.")
        finally:
            self._log("wait_end", prompt=prompt_id[:8], secs=round(time.monotonic() - t_wait, 1))
            if own:
                self.close_events(ws)
        h = self.history(prompt_id) or {}
        status = h.get("status", {})
        if status.get("status_str") == "error":
            msgs = [m[1].get("exception_message") for m in status.get("messages", []) if m[0] == "execution_error"]
            raise ComfyError("ComfyUI reported an error: " + ("; ".join(x for x in msgs if x) or "unknown"))
        return h

    def output_images(self, hist: dict, node_id: str | None = None) -> list[Image.Image]:
        outputs = hist.get("outputs", {})
        ids = [node_id] if node_id and node_id in outputs else list(outputs)
        images = []
        for nid in ids:
            for im in outputs[nid].get("images", []):
                images.append(self.view(im["filename"], im.get("subfolder", ""), im.get("type", "output")))
            if images:
                break
        if not images:
            raise ComfyError("The job finished without output images (no SaveImage/PreviewImage node?).")
        return images
