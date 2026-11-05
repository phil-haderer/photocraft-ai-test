"""The ComfyUI address in Other settings (user 3.11.): the check of what is typed, the probe of a server (a small local one that
answers like ComfyUI, like something else, or not at all), switching the client to another server, and the settings row.

    python tests/test_comfy_address.py
"""
import http.server
import json
import os
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["PCCOMFY_HOME"] = tempfile.mkdtemp(prefix="pccomfy-ca2-")
sys.path.insert(0, str(ROOT))

from pccomfy import comfyaddr  # noqa: E402
from pccomfy.comfy import ComfyUI  # noqa: E402


class Handler(http.server.BaseHTTPRequestHandler):
    kind = "comfy"

    def do_GET(self):
        if self.kind == "comfy" and self.path == "/system_stats":
            body = json.dumps({"system": {"comfyui_version": "0.42.0"}, "devices": []}).encode()
            self.send_response(200)
        else:
            body = b"<html>hello</html>"
            self.send_response(200 if self.kind == "other" else 404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def serve(kind):
    h = type("H", (Handler,), {"kind": kind})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def format_tests():
    ok = comfyaddr.check_format
    assert ok("127.0.0.1:8188")[0] == "http://127.0.0.1:8188" and ok("  http://localhost:8188/ ")[0] == "http://localhost:8188"
    assert ok("https://gpu.example.com")[0] == "https://gpu.example.com" and ok("[::1]:8188")[0] == "http://[::1]:8188"
    assert ok("http://127.0.0.1:8188")[2] == "" and ok("https://10.0.0.5:8188")[2] == ""                  # local / encrypted: no warning
    assert ok("http://192.168.1.20:8188")[2] == comfyaddr.UNENCRYPTED and ok("10.0.2.2:8188")[2] == comfyaddr.UNENCRYPTED
    for bad in ("", "   ", "ftp://x:1", "http://", "http://user:pw@host:8188", "http://host:8188/api", "http://host:99999", "http://host:abc"):
        url, err, _w = ok(bad)
        assert url is None and err, bad


def probe_tests():
    s1, u1 = serve("comfy")
    s2, u2 = serve("other")
    s3, u3 = serve("404")
    good, msg = comfyaddr.probe(u1)
    assert good and msg == "ComfyUI found (0.42.0)", msg
    for u in (u2, u3):
        good, msg = comfyaddr.probe(u)
        assert not good and msg.startswith("Not ComfyUI"), msg
    s3.shutdown()
    s3.server_close()
    good, msg = comfyaddr.probe(u3, timeout=1.0)                                                            # nobody listens there any more
    assert not good and msg.startswith("Not reachable"), msg
    # the client follows to another server and forgets the lists of the old one
    c = ComfyUI(u1)
    assert c._json("/system_stats")["system"]["comfyui_version"] == "0.42.0"
    s4, u4 = serve("comfy")
    c.set_url(u4)
    assert c.url == u4 and c._cache == {} and c._json("/system_stats")["system"]["comfyui_version"] == "0.42.0"
    assert ComfyUI("https://example.org:8443")._https and ComfyUI("https://example.org:8443")._port == 8443
    return u1, u2


def window_tests(u_comfy, u_other):
    try:
        import tkinter
        tkinter.Tk().destroy()
    except Exception as e:
        print(f"(window part skipped: no Tk window: {e})")
        return
    from pccomfy import config as cfgmod, gui
    gui.winlink.available = lambda: False
    cfg = cfgmod.load()
    cfg["comfyui"]["url"] = "http://127.0.0.1:1"
    cfg["photocraft"]["port"] = 1
    app = gui.App(cfg)
    app.root.withdraw()
    app.refresh = lambda: None                      # the re-read itself is tested elsewhere
    for _ in range(10):
        app.root.update()
    app.open_settings()
    app.root.update()

    def pump(n=1, wait=3.0):
        end = time.time() + wait
        got = 0
        while got < n and time.time() < end:
            try:
                kind, data = app.events.get(timeout=0.1)
            except queue.Empty:
                continue
            if kind == "comfyaddr":
                app._comfy_address_done(data)
                got += 1
            app.root.update()

    pump(1)                                         # the check at opening: nothing listens on port 1
    assert app.lbl_comfy_mark["text"] == "✗" and "Not reachable" in app.lbl_comfy_msg["text"]
    app.v_comfy_url.set("not a url ://")
    app._comfy_address_check()
    assert app.lbl_comfy_mark["text"] == "✗" and app.comfy.url == "http://127.0.0.1:1"
    app.v_comfy_url.set(u_other)                    # answers, but is no ComfyUI: the old address stays
    app._comfy_address_check()
    pump()
    assert app.lbl_comfy_mark["text"] == "✗" and app.comfy.url == "http://127.0.0.1:1"
    app.v_comfy_url.set(u_comfy)
    app._comfy_address_check()
    pump()
    assert app.lbl_comfy_mark["text"] == "✓" and "ComfyUI found" in app.lbl_comfy_msg["text"]
    assert app.comfy.url == u_comfy and cfgmod.get_setting("comfyui_url") == u_comfy and app.bridge.comfy is app.comfy
    assert comfyaddr.is_local(app.comfy.url) and app.lbl_comfy_note["text"] == ""
    # a click into the field takes the keyboard (the borderless settings window is not always made the active one by Windows)
    from tkinter import ttk
    def find_entry(w):
        for c in w.winfo_children():
            if isinstance(c, ttk.Entry):
                return c
            r = find_entry(c)
            if r is not None:
                return r
    forced = []
    app._force_focus = lambda w: forced.append(w)
    ent = find_entry(app._settings_win)
    ent.event_generate("<ButtonPress-1>", x=3, y=3)
    for _ in range(5):
        app.root.update()
    assert forced and forced[0] is ent, "a click into the address field must force the keyboard focus to it"
    del app._force_focus
    app._comfy_address_reset()                      # the field gets the default back and is checked (what answers there depends on the PC)
    assert app.v_comfy_url.get() == comfyaddr.DEFAULT_URL
    app.root.destroy()


if __name__ == "__main__":
    format_tests()
    u1, u2 = probe_tests()
    window_tests(u1, u2)
    print("ALL OK (comfy address)")
