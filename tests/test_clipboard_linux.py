"""The Linux clipboard (pccomfy/clipboard.py, "the Linux part"): choosing a format, file lists, reading and writing through a
fake clipboard program, the backend choice. Runs on any system; no real clipboard is touched.

    python tests/test_clipboard_linux.py
"""
import io
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from PIL import Image  # noqa: E402

from pccomfy import clipboard as cb  # noqa: E402


def png_bytes(color=(10, 200, 30), size=(7, 5)):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def main():
    # choosing a format: PNG first, then any picture, then copied files
    assert cb.pick_target(["text/plain", "image/png", "image/bmp"]) == ("image", "image/png")
    assert cb.pick_target(["image/bmp", "text/plain"]) == ("image", "image/bmp")
    assert cb.pick_target(["TARGETS", "text/uri-list"]) == ("files", "text/uri-list")
    assert cb.pick_target(["x-special/gnome-copied-files", "text/plain"]) == ("files", "x-special/gnome-copied-files")
    assert cb.pick_target(["text/plain", "UTF8_STRING"]) is None and cb.pick_target([]) is None and cb.pick_target(None) is None

    # file lists: file:// lines only, percent-decoded, no remote hosts, the "copy" line of gnome-copied-files skipped
    text = "copy\nfile:///home/user/My%20Pics/a.png\n# comment\nfile://localhost/tmp/b.jpg\nfile://otherhost/x.png\nhttps://x/y.png\n"
    assert cb.paths_from_uri_list(text) == [Path("/home/user/My Pics/a.png"), Path("/tmp/b.jpg")]
    assert cb.paths_from_uri_list("") == [] and cb.paths_from_uri_list(None) == []

    # the backend: Wayland with wl-clipboard, X11 with xclip, else nothing
    import os
    real = (cb.sys.platform, dict(os.environ), cb.shutil.which)
    try:
        cb.sys.platform = "linux"
        have = {"wl-paste", "wl-copy", "xclip"}
        cb.shutil.which = lambda n: "/usr/bin/" + n if n in have else None
        os.environ["WAYLAND_DISPLAY"], os.environ["DISPLAY"] = "wayland-0", ":0"
        assert cb._linux_backend() == "wl" and cb.available()
        del os.environ["WAYLAND_DISPLAY"]
        assert cb._linux_backend() == "xclip"
        have.discard("xclip")
        assert cb._linux_backend() is None and not cb.available()
        cb.sys.platform = "win32"
        assert cb._linux_backend() is None and cb.available()
    finally:
        cb.sys.platform = real[0]
        os.environ.clear()
        os.environ.update(real[1])
        cb.shutil.which = real[2]

    # reading and writing through a fake program
    calls = []
    clip = {"types": ["text/plain", "image/png"], "data": {"image/png": png_bytes()}}

    def fake_run(args, data=None):
        calls.append((list(args), data))
        if data is not None:                                    # a write
            clip["written"] = data
            return b""
        if "--list-types" in args or "TARGETS" in args:
            return "\n".join(clip["types"]).encode()
        mime = args[args.index("--type") + 1] if "--type" in args else args[args.index("-t") + 1]
        return clip["data"].get(mime)
    real_run, real_backend = cb._linux_run, cb._linux_backend
    cb._linux_run = fake_run
    try:
        for backend in ("wl", "xclip"):
            cb._linux_backend = lambda b=backend: b
            calls.clear()
            img = cb.read_image()
            assert img is not None and img.size == (7, 5) and img.getpixel((0, 0)) == (10, 200, 30), backend
            assert calls[0][0][0] == ("wl-paste" if backend == "wl" else "xclip")
            assert "image/png" in calls[1][0]

            assert cb.write_image(Image.new("RGBA", (4, 3), (1, 2, 3, 128))) is True
            assert calls[-1][0][0] == ("wl-copy" if backend == "wl" else "xclip") and "image/png" in calls[-1][0]
            back = Image.open(io.BytesIO(clip["written"]))
            assert back.size == (4, 3) and back.mode == "RGBA" and back.getpixel((0, 0))[3] == 128      # transparency kept

        # copied files: the first picture in the list
        if os.name != "nt":                 # a POSIX path in a file:// URI
            with tempfile.TemporaryDirectory() as tmp:
                pic = Path(tmp) / "pic one.png"
                Image.new("RGB", (3, 2), (5, 6, 7)).save(pic)
                clip["types"] = ["text/uri-list"]
                clip["data"] = {"text/uri-list": (pic.as_uri() + "\r\n").encode()}
                img = cb.read_image()
                assert img is not None and img.size == (3, 2)

        # nothing usable: None, no exception
        clip["types"], clip["data"] = ["text/plain"], {}
        assert cb.read_image() is None
        clip["types"], clip["data"] = ["image/png"], {"image/png": b"not a picture"}
        assert cb.read_image() is None
        cb._linux_run = lambda args, data=None: None            # the program fails
        assert cb.read_image() is None and cb.write_image(Image.new("RGB", (2, 2))) is False
    finally:
        cb._linux_run, cb._linux_backend = real_run, real_backend

    print("clipboard linux ok")


if __name__ == "__main__":
    main()
