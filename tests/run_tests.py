#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SheLLM differential test harness.

Usage:
  python3 run_tests.py --impl bash|v1|v2 [--valgrind] [--jobs N] [--out results/x.json]

Each test runs in an identical fixture directory built from scratch under
/tmp/shellm_fix/<id>. Bash is the reference; SheLLM's output is compared with it.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cases as _main_cases  # noqa: E402
import cases_holdout as _holdout  # noqa: E402
from paths import V1_BIN, V2_BIN, V1_ASAN_BIN, V2_ASAN_BIN, V1_DIR, V2_DIR  # noqa: E402

ROOT = "/tmp/shellm_fix"
HERE = os.path.dirname(os.path.abspath(__file__))
IMPLS = {
    "bash": ["bash", "--norc", "--noprofile"],
    "v1": [V1_BIN],
    "v2": [V2_BIN],
    "v1asan": [V1_ASAN_BIN],
    "v2asan": [V2_ASAN_BIN],
}
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def make_fixture(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    # file names and contents are fixture data used by the test scripts
    w = lambda p, s, mode=0o644: (open(os.path.join(path, p), "w").write(s), os.chmod(os.path.join(path, p), mode))
    w("a.txt", "elma\narmut\nkiraz\nelma\n")
    w("b.txt", "1\n2\n3\n")
    w("bosluklu dosya.txt", "bosluk\n")
    w("empty.txt", "")
    w("run.sh", "#!/bin/sh\necho script-ok\nexit 3\n", 0o755)
    w("noexec.sh", "#!/bin/sh\necho x\n", 0o644)
    os.makedirs(os.path.join(path, "d"))
    for n in ("x.c", "y.c", "z.h"):
        w(os.path.join("d", n), n[0] + "\n")
    home = os.path.join(path, "home")
    os.makedirs(os.path.join(home, "Desktop"))
    open(os.path.join(home, "Desktop", "rapor.pdf"), "w").write("%PDF\n")
    open(os.path.join(home, "Desktop", "not.txt"), "w").write("not icerigi\n")
    open(os.path.join(home, ".gizli"), "w").write("")
    return home


def env_for(fix, home):
    # Order matters: AAA_FIRST is the first entry of the environment list (for the unset test).
    return {
        "AAA_FIRST": "1",
        "HOME": home,
        "PATH": "/usr/bin:/bin",
        "PWD": fix,
        "USER": "tester",
        "LC_ALL": "C",
        "TERM": "dumb",
        "ZVAR": "zzz",
    }


def normalize_v1(out, script):
    """v1 was designed for interactive use only, so on non-tty input this
    removes the prompt/echo lines printed by readline and the interface
    decorations. This step keeps v1 from being put at a disadvantage.
    The patterns match v1's (Turkish, ASCII-only) interface text."""
    s = ANSI.sub("", out)
    s = re.sub(r"^[\s─]*sheLLM  ● AI (?:bagli|kapali)\n  \n\n", "", s)
    s = s.replace("\n  ⠸ AI dusunuyor...", "").replace("\r                          \r", "")
    s = re.sub(r"🎀 sheLLM [^\n]*\n", "", s)
    s = re.sub(r"🎀 sheLLM $", "", s)
    s = re.sub(r"(?m)^> [^\n]*\n", "", s)
    if re.search(r"(?m)^exit\b", script):
        s = re.sub(r"(?m)^exit\n", "", s, count=1)
    return s


def run_case(case, impl, valgrind=False, vgdir=None, timeout=20):
    fix = os.path.join(ROOT, case["id"])
    home = make_fixture(fix)
    env = env_for(fix, home)
    if impl.endswith("asan"):
        env["ASAN_OPTIONS"] = "detect_leaks=0:abort_on_error=0"
        env["UBSAN_OPTIONS"] = "print_stacktrace=1"
    cmd = list(IMPLS[impl])
    if valgrind:
        logp = os.path.join(vgdir, case["id"] + ".%p.log")
        supp = os.path.join(V1_DIR if impl.startswith("v1") else V2_DIR, "valgrind.supp")
        cmd = ["valgrind", "--leak-check=full", "--show-leak-kinds=definite",
               "--errors-for-leak-kinds=definite", "--track-fds=yes",
               "--suppressions=" + supp, "--log-file=" + logp] + cmd
    t0 = time.perf_counter()
    try:
        p = subprocess.run(cmd, input=case["script"].encode(), cwd=fix, env=env,
                           capture_output=True, timeout=timeout)
        out, err, rc, to = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace"), p.returncode, False
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", "replace")
        err = (e.stderr or b"").decode("utf-8", "replace")
        rc, to = None, True
    dt = time.perf_counter() - t0
    if impl.startswith("v1"):
        out = normalize_v1(out, case["script"])
    shutil.rmtree(fix, ignore_errors=True)
    return {"id": case["id"], "cat": case["cat"], "stdout": out, "stderr": err,
            "rc": rc, "timeout": to, "crash": (rc is not None and rc < 0), "time": dt}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", required=True, choices=list(IMPLS))
    ap.add_argument("--valgrind", action="store_true")
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--out")
    ap.add_argument("--only")
    ap.add_argument("--suite", default="main", choices=["main", "holdout"])
    a = ap.parse_args()
    os.makedirs(ROOT, exist_ok=True)
    CASES = (_holdout if a.suite == "holdout" else _main_cases).CASES
    cases = [c for c in CASES if not a.only or re.match(a.only, c["id"])]
    vgdir = None
    if a.valgrind:
        vgdir = os.path.join(HERE, "results", "vg_" + a.impl + ("_holdout" if a.suite == "holdout" else ""))
        shutil.rmtree(vgdir, ignore_errors=True)
        os.makedirs(vgdir)
    with ThreadPoolExecutor(max_workers=a.jobs) as ex:
        res = list(ex.map(lambda c: run_case(c, a.impl, a.valgrind, vgdir), cases))
    suffix = ("_holdout" if a.suite == "holdout" else "") + (".vg" if a.valgrind else "")
    out = a.out or os.path.join(HERE, "results", a.impl + suffix + ".json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    print("written:", out, len(res), "tests")


if __name__ == "__main__":
    main()
