"""Runs every tests/test_*.py in its own Python process and prints one line per file and a summary.
Run: python tests/run_all.py            (all files)
     python tests/run_all.py bars round  (only files whose name contains one of the words)
     python tests/run_all.py -j 4        (four files at a time; the files use their own temp folders and ports)
PCCOMFY_SLOW_TESTS=1 also runs the slow parts (test_scribble on the real round 6 photos, the full matrix of
test_fill_mask_variants); without it they are skipped or sampled. Only test_*.py files are collected
(tests/selfcheck_*.py and tests/live_*.py are run by hand).
Exit code 0 = all green. The tests use a stubbed Tk and a fake PhotoCraft: the real window and real generations are not covered."""
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def run_one(p: Path) -> tuple[Path, bool, str, float]:
    t0 = time.monotonic()
    try:
        # UTF-8 both ways: on Windows the console code page cannot hold the tests' "·" and "→"
        r = subprocess.run([sys.executable, "-B", str(p)], cwd=ROOT, capture_output=True, text=True, timeout=300,
                           encoding="utf-8", errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8", "PCCOMFY_NO_TIPS": "1", "PCCOMFY_NO_WATCH": "1"})
        ok, out = r.returncode == 0, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        ok, out = False, "timeout after 300 s"
    return p, ok, out, time.monotonic() - t0


def main(args: list[str]) -> int:
    jobs = 1
    if "-j" in args:
        i = args.index("-j")
        jobs = max(1, int(args[i + 1]))
        del args[i:i + 2]
    files = sorted(p for p in HERE.glob("test_*.py") if not args or any(w in p.name for w in args))
    if not files:
        print("No test file matches:", " ".join(args))
        return 2
    failed = []
    t_all = time.monotonic()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for p, ok, out, secs in pool.map(run_one, files):       # results come in file order
            print(f"{'ok  ' if ok else 'FAIL'} {p.name:<34} {secs:5.1f} s")
            if not ok:
                failed.append(p.name)
                print("     " + "\n     ".join(out.strip().splitlines()[-12:]))
    print(f"\n{len(files) - len(failed)} of {len(files)} test files green in {time.monotonic() - t_all:.0f} s"
          + (f"; FAILED: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
