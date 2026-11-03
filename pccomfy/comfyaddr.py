"""The ComfyUI address (no Tk here): check what the user typed and ask the server whether it is ComfyUI (Other settings, user 3.11.).

``check_format`` turns the text into a clean address or says what is wrong; ``probe`` asks ``/system_stats``. Plain ``http`` is
allowed (ComfyUI has no https of its own; a VM or another PC in the home network reaches it that way) but a server that is not
this computer gets a warning. Addresses with a user name, a password or a path are refused.
"""
from __future__ import annotations

import http.client
import json
import urllib.parse

from .comfy import real_comfy_blocked

DEFAULT_URL = "http://127.0.0.1:8188"
LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")
UNENCRYPTED = "unencrypted connection: pictures and prompts cross the network as plain data"
REMOTE_NOTE = ("Model downloads and file detection need ComfyUI on this computer. With another computer the download buttons "
               "ask for the models folder (for example a shared one).")


def is_local(url: str) -> bool:
    return (urllib.parse.urlsplit(url).hostname or "") in LOCAL_HOSTS


def check_format(text: str) -> tuple[str | None, str, str]:
    """(address, error, warning): the cleaned address, or None with the reason; a warning for plain http to another computer."""
    raw = (text or "").strip()
    if not raw:
        return None, "Type an address, e.g. http://127.0.0.1:8188", ""
    if "://" not in raw:
        raw = "http://" + raw
    try:
        parts = urllib.parse.urlsplit(raw)
        port = parts.port
    except ValueError:
        return None, "Invalid address", ""
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None, "Invalid address: use http://host:port", ""
    if parts.username or parts.password or "@" in parts.netloc:
        return None, "No user name or password in the address", ""
    if parts.path not in ("", "/") or parts.query or parts.fragment:
        return None, "Only host and port, no path", ""
    host = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
    url = f"{parts.scheme}://{host}" + (f":{port}" if port else "")
    warn = UNENCRYPTED if parts.scheme == "http" and not is_local(url) else ""
    return url, "", warn


def probe(url: str, timeout: float = 3.0) -> tuple[bool, str]:
    """Asks the server: (True, "ComfyUI 0.42.0") when it answers like ComfyUI, else (False, the reason)."""
    parts = urllib.parse.urlsplit(url)
    cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
    if real_comfy_blocked(parts.hostname or "", parts.port or (443 if parts.scheme == "https" else 80)):
        return False, "Blocked in tests (port 8188)"
    conn = cls(parts.hostname, parts.port or (443 if parts.scheme == "https" else 80), timeout=timeout)
    try:
        conn.request("GET", "/system_stats")
        r = conn.getresponse()
        body = r.read(200000)
    except (OSError, http.client.HTTPException) as e:
        return False, "Not reachable" + (f" ({getattr(e, 'strerror', None) or type(e).__name__})" if str(e) else "")
    finally:
        conn.close()
    try:
        info = json.loads(body)
        system = info["system"] if r.status == 200 else None
    except (ValueError, KeyError, TypeError):
        system = None
    if not isinstance(system, dict):
        return False, "Not ComfyUI (no answer to /system_stats)"
    ver = system.get("comfyui_version")
    return True, "ComfyUI found" + (f" ({ver})" if ver else "")
