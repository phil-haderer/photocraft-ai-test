"""Finding ComfyUI's folder on Linux from /proc (pccomfy/comfydir.py): the listening socket, its process, the working folder.
The /proc part runs on a fake tree (symlinks, so not on Windows); the rest runs everywhere.

    python tests/test_comfydir_linux.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pccomfy import comfydir  # noqa: E402

TCP = """  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode
   0: 0100007F:1F3E 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 424242 1 0000000000000000 100 0 0 10 0
   1: 0100007F:1F90 00000000:0000 0A 00000000:00000000 00:00000000 00000000  1000        0 777 1 0000000000000000 100 0 0 10 0
   2: 0100007F:1F3E 0100007F:D2A0 01 00000000:00000000 00:00000000 00000000  1000        0 555 1 0000000000000000 100 0 0 10 0
"""


def make_comfy(base: Path) -> Path:
    root = base / "ComfyUI"
    (root / "models").mkdir(parents=True)
    (root / "main.py").write_text("")
    return root


def main():
    # port 7998 = 0x1F3E; only the LISTEN line counts (state 0A), not the connection (01)
    assert comfydir.listen_inodes(TCP, 7998) == {"424242"}
    assert comfydir.listen_inodes(TCP, 8080) == {"777"}
    assert comfydir.listen_inodes(TCP, 1234) == set()
    assert comfydir.listen_inodes("", 7998) == set() and comfydir.listen_inodes("junk\nmore junk here", 7998) == set()

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        root = make_comfy(tmp / "home")
        # the working folder names ComfyUI (a relative "main.py" in the command line cannot)
        assert comfydir.root_from_process("/usr/bin/python3", "python main.py --port 8190", str(root)) == root
        assert comfydir.root_from_process("/usr/bin/python3", "python main.py", str(root.parent)) == root      # the folder above
        assert comfydir.root_from_process("/usr/bin/python3", "python main.py", str(tmp)) is None

        if os.name != "nt":
            proc = tmp / "proc"
            (proc / "net").mkdir(parents=True)
            (proc / "net" / "tcp").write_text(TCP)
            (proc / "net" / "tcp6").write_text("header\n")
            other = proc / "99"
            (other / "fd").mkdir(parents=True)
            os.symlink("socket:[1]", other / "fd" / "3")
            me = proc / "1234"
            (me / "fd").mkdir(parents=True)
            os.symlink("/dev/null", me / "fd" / "0")
            os.symlink("socket:[424242]", me / "fd" / "5")
            (me / "cmdline").write_bytes(b"python\0main.py\0--port\0" + b"7998\0")
            os.symlink("/usr/bin/python3", me / "exe")
            os.symlink(str(root), me / "cwd")
            assert comfydir._find_root_linux(7998, str(proc)) == root
            assert comfydir._find_root_linux(8080, str(proc)) is None      # a listener whose process has no such socket here
            assert comfydir._find_root_linux(5555, str(proc)) is None      # nobody listens
            assert comfydir._find_root_linux(7998, str(tmp / "missing")) is None
        else:
            print("(no symlinks on Windows: the fake /proc part is skipped)")

    assert comfydir.find_root("http://example.com:8188") is None      # only a local server
    print("comfydir linux ok")


if __name__ == "__main__":
    main()
