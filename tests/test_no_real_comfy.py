"""A test script never talks to the ComfyUI of this PC (port 8188): three test runs ended the listening socket of the real ComfyUI
(WinError 64 in asyncio's accept, 3.11.2026). `comfy.real_comfy_blocked` stops it in ComfyUI._request, open_events and
comfyaddr.probe. Nothing here connects anywhere.

    python tests/test_no_real_comfy.py
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pccomfy import comfy, comfyaddr  # noqa: E402


def main():
    blocked = comfy.real_comfy_blocked
    assert Path(sys.argv[0]).resolve().parent.name == "tests"
    # in a test script: the default port of this PC is blocked, every other port is not
    for host in ("127.0.0.1", "localhost", "::1"):
        assert blocked(host, 8188), host
    assert not blocked("127.0.0.1", 8189) and not blocked("127.0.0.1", 1) and not blocked("192.168.1.20", 8188)
    assert not blocked("example.com", 8188)
    # the requests, the websocket and the address check refuse without opening a socket
    c = comfy.ComfyUI("http://127.0.0.1:8188")
    try:
        c.system_stats()
        raise SystemExit("expected a ComfyError")
    except comfy.ComfyError as e:
        assert "Blocked" in str(e), str(e)
    assert c.open_events() is None
    ok, why = comfyaddr.probe("http://localhost:8188")
    assert not ok and "Blocked" in why, why
    # the opt-out for a deliberate run, and the manual live checks are not blocked
    os.environ["PCCOMFY_ALLOW_REAL_COMFY"] = "1"
    try:
        assert not blocked("127.0.0.1", 8188)
    finally:
        del os.environ["PCCOMFY_ALLOW_REAL_COMFY"]
    old = sys.argv[0]
    try:
        sys.argv[0] = str(ROOT / "tests" / "live_fill_mask.py")
        assert not blocked("127.0.0.1", 8188)
        sys.argv[0] = str(ROOT / "pccomfy" / "__main__.py")             # the plugin itself is never blocked
        assert not blocked("127.0.0.1", 8188)
        sys.argv[:] = []                                                # no script name: not blocked, no error
        assert not blocked("127.0.0.1", 8188)
    finally:
        sys.argv[0:] = [old]
    print("ALL OK (tests never touch the real ComfyUI)")


if __name__ == "__main__":
    main()
