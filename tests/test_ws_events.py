"""The websocket of a run (ComfyUI.open_events / close_events / wait): the handshake gets 10 s and then recv() times out after
1 s, a socket that failed is closed, wait() works with a socket the caller opened, with its own and without websocket-client.
(A client that gives up in the middle of the handshake can kill ComfyUI's listening socket on Windows: WinError 64.)

    python tests/test_ws_events.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
import tempfile  # noqa: E402
import test_reference_mode as T  # noqa: E402
from pccomfy import comfy  # noqa: E402
from pccomfy.bridge import Request  # noqa: E402
from pccomfy import workflows  # noqa: E402


class WS:
    def __init__(self, msgs=(), fail_recv=False, fail_settimeout=False, fail_close=False):
        self.msgs, self.fail_recv, self.fail_settimeout, self.fail_close = list(msgs), fail_recv, fail_settimeout, fail_close
        self.timeouts, self.closed = [], 0

    def settimeout(self, t):
        if self.fail_settimeout:
            raise OSError("settimeout failed")
        self.timeouts.append(t)

    def recv(self):
        if self.fail_recv:
            raise OSError("connection reset")
        return self.msgs.pop(0)

    def close(self):
        self.closed += 1
        if self.fail_close:
            raise OSError("close failed")


def install(factory):
    calls = []

    def create(url, timeout=None, **kw):
        calls.append((url, timeout))
        return factory()
    comfy.websocket = type("W", (), {"create_connection": staticmethod(create), "WebSocketTimeoutException": TimeoutError})
    return calls


def done(pid="p1"):
    return json.dumps({"type": "execution_success", "data": {"prompt_id": pid}})


def bridge_checks():
    """A run opens the socket BEFORE it queues the job and closes it afterwards, also when the job fails."""
    for fail in (False, True):
        pc, _, b = T.make(tempfile.mkdtemp())
        assert b.comfy.log_file == b.exchange / "comfy-net.log"        # the connection log sits next to runs.jsonl
        b.comfy = T.FakeComfy()
        log = []
        ws = object()
        b.comfy.open_events = lambda: log.append("open") or ws
        b.comfy.close_events = lambda w: log.append(("close", w is ws))
        queue, wait = b.comfy.queue, b.comfy.wait

        def q(graph, preview=None):
            log.append("queue")
            return queue(graph, preview)

        def w(pid, *a, ws=None, **k):
            log.append(("wait", ws is not None))
            if fail:
                raise comfy.ComfyError("boom")
            return wait(pid, *a, **k)
        b.comfy.queue, b.comfy.wait = q, w
        req = Request(mode="edit", workflow=str(ROOT / "workflows" / "fibo2-edit.json"), enhance=False)
        req.params = workflows.GenParams(prompt="make it night", seed=7)
        try:
            b.run(req)
            assert not fail
        except Exception:
            assert fail
        assert log[:3] == ["open", "queue", ("wait", True)], log
        assert log[-1] == ("close", True), log


def main():
    bridge_checks()
    orig = comfy.websocket
    c = comfy.ComfyUI("http://127.0.0.1:8189")
    c.history = lambda pid: {"status": {"completed": True, "status_str": "success"}}
    try:
        # the handshake gets 10 s, the heartbeat 1 s
        made = []
        calls = install(lambda: made.append(WS()) or made[-1])
        ws = c.open_events()
        assert ws is made[0] and calls[0][1] == comfy.WS_HANDSHAKE_S == 10.0 and ws.timeouts == [1]
        assert calls[0][0].startswith("ws://127.0.0.1:8189/ws?clientId=")
        c.close_events(ws)
        assert ws.closed == 1
        c.close_events(None)                                   # nothing to close: no error
        c.close_events(WS(fail_close=True))                    # closing may fail: no error

        # a failed handshake: None, nothing raised
        def boom():
            raise OSError("handshake failed")
        install(boom)
        assert c.open_events() is None
        # a socket whose settimeout fails is closed, not left open
        made.clear()
        install(lambda: made.append(WS(fail_settimeout=True)) or made[-1])
        assert c.open_events() is None and made[0].closed == 1

        # wait() with the caller's socket: used, and left open for the caller to close
        mine = WS([done()])
        calls = install(lambda: WS())
        c.wait("p1", ws=mine)
        assert not calls and mine.closed == 0                  # no second connection, the caller closes it
        # wait() with its own socket: closed at the end
        made.clear()
        install(lambda: made.append(WS([done()])) or made[-1])
        c.wait("p1")
        assert made[0].closed == 1
        # a socket that breaks in recv() is closed at once; the wait falls back to polling /history
        bad = WS(fail_recv=True)
        c.wait("p1", ws=bad)
        assert bad.closed == 1

        # the connection log: one line per event, never raises, keeps its last part when it grows
        log = Path(tempfile.mkdtemp()) / "sub" / "comfy-net.log"
        c.log_file = log
        made.clear()
        install(lambda: made.append(WS([done()])) or made[-1])
        c.wait("p1")
        text = log.read_text(encoding="utf-8")
        for event in ("ws_open ", "wait_start", "wait_end", "ws_close "):
            assert event in text, (event, text)
        install(boom)
        c.open_events()
        assert "ws_open_failed" in log.read_text(encoding="utf-8") and "handshake failed" in log.read_text(encoding="utf-8")
        c.LOG_MAX_BYTES = 500
        for _ in range(60):
            c._log("filler", n=1)
        assert len(log.read_text(encoding="utf-8").splitlines()) < 1100
        c.log_file = log.parent / "x:y|z?"          # an unusable path: no error
        c._log("never raises")
        c.log_file = None
        c._log("no log")

        # without websocket-client: polling only
        comfy.websocket = None
        assert c.open_events() is None
        c.close_events(None)
        c.wait("p1")
    finally:
        comfy.websocket = orig
    print("ALL OK (websocket events)")


if __name__ == "__main__":
    main()
