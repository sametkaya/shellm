#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Performance measurements.

E3a  Execution time per command (Bash, v1, v2):
     computed as (T(N) - T(0)) / N from the run time T(N) of an N-line script
     and the run time T(0) of an empty script, so start-up cost is excluded.
E3b  Time from interactive start-up to the first prompt (v1, v2).
E3c  AI path overhead: time from sending a faulty command until the suggestion
     box appears; measured with a mock backend that has zero model latency
     (shell + inter-process communication only).
"""
import json
import os
import shutil
import statistics as st
import subprocess
import sys
import time

import pexpect


def _dfl():
    # Scripts started in the background may inherit SIGINT/SIGQUIT as ignored;
    # restore the default handlers, as in a real terminal.
    import signal as _s
    _s.signal(_s.SIGINT, _s.SIG_DFL)
    _s.signal(_s.SIGQUIT, _s.SIG_DFL)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import V1_BIN, V2_BIN, V1_MOCK_DIR, RESULTS  # noqa: E402
BIN = {"bash": ["bash", "--norc", "--noprofile"], "v1": [V1_BIN], "v2": [V2_BIN]}
FIX = "/tmp/bench_fix"
REPS = 5
# The keys are the labels stored in results/bench.json.
CMDS = {
    "builtin (echo x)": "echo x",
    "external (/bin/true)": "/bin/true",
    "pipeline (echo x | cat | cat)": "echo x | cat | cat",
    "redirection (echo x > /dev/null)": "echo x > /dev/null",
    "glob (echo *.txt)": "echo *.txt",
}


def fixture():
    shutil.rmtree(FIX, ignore_errors=True)
    os.makedirs(FIX)
    for i in range(20):
        open(os.path.join(FIX, "f%02d.txt" % i), "w").write("x\n")


def run_script(impl, script):
    env = {"PATH": "/usr/bin:/bin", "HOME": FIX, "TERM": "dumb", "LC_ALL": "C"}
    t0 = time.perf_counter()
    subprocess.run(BIN[impl], input=script.encode(), cwd=FIX, env=env,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return time.perf_counter() - t0


def per_command(impl, cmd, n):
    t0s, tns = [], []
    for _ in range(REPS):
        t0s.append(run_script(impl, ""))
        tns.append(run_script(impl, (cmd + "\n") * n))
    return (st.median(tns) - st.median(t0s)) / n * 1000.0, st.median(t0s) * 1000.0


def e3a():
    fixture()
    out = {}
    for label, cmd in CMDS.items():
        out[label] = {}
        for impl in ("bash", "v1", "v2"):
            n = 400
            ms, startup = per_command(impl, cmd, n)
            out[label][impl] = round(ms, 3)
            out.setdefault("_startup_noninteractive_ms", {})[impl] = round(startup, 1)
        print(label, out[label], flush=True)
    return out


# ---------------------------------------------------------------- interactive
def spawn(impl, cwd):
    env = dict(os.environ, TERM="xterm", HOME="/tmp", PATH="/usr/bin:/bin")
    env.pop("GEMINI_API_KEY", None)
    if impl == "v2":
        env["SHELLM_BACKEND"] = "mock"
    env["SHELLM_MOCK_FIXED"] = env["MOCK_FIXED"] = "mkdir a"
    c = pexpect.spawn(BIN[impl][0], env=env, encoding="utf-8", timeout=15, cwd=cwd, preexec_fn=_dfl)
    c.delaybeforesend = None  # disable pexpect's default 50 ms send delay
    return c


def kill_helpers():
    subprocess.run(["pkill", "-f", "ai_helper.py"], capture_output=True)
    time.sleep(0.2)


def e3b_e3c(runs=20):
    res = {"startup_ms": {}, "ai_path_ms": {}}
    # text in the suggestion box (v2: English interface, SHELLM_LANG=en set by
    # paths.py and inherited through os.environ)
    marker = {"v1": "calistir", "v2": "shellm suggestion"}
    os.makedirs("/tmp/v1other", exist_ok=True)
    cwd = {"v1": V1_MOCK_DIR, "v2": "/tmp/v1other"}
    for impl in ("v1", "v2"):
        su, ai = [], []
        for _ in range(runs):
            kill_helpers()
            t0 = time.perf_counter()
            c = spawn(impl, cwd[impl])
            c.expect("sheLLM ")
            su.append((time.perf_counter() - t0) * 1000)
            for _ in range(3):
                t1 = time.perf_counter()
                c.sendline("mkdr a")
                c.expect(marker[impl])
                ai.append((time.perf_counter() - t1) * 1000)
                c.sendline("h")
                c.expect("sheLLM ")
            c.sendline("exit")
            try:
                c.expect(pexpect.EOF, timeout=3)
            except pexpect.TIMEOUT:
                c.terminate(force=True)
        kill_helpers()
        res["startup_ms"][impl] = {"median": round(st.median(su), 1),
                                   "p90": round(sorted(su)[int(0.9 * len(su)) - 1], 1),
                                   "n": len(su)}
        res["ai_path_ms"][impl] = {"median": round(st.median(ai), 1),
                                   "p90": round(sorted(ai)[int(0.9 * len(ai)) - 1], 1),
                                   "n": len(ai)}
        print(impl, res["startup_ms"][impl], res["ai_path_ms"][impl], flush=True)
    return res


if __name__ == "__main__":
    which = sys.argv[1:] or ["e3a", "e3bc"]
    path = os.path.join(RESULTS, "bench.json")
    out = json.load(open(path)) if os.path.exists(path) else {}
    if "e3a" in which:
        out["per_command_ms"] = e3a()
    if "e3bc" in which:
        out.update(e3b_e3c())
    json.dump(out, open(path, "w"), ensure_ascii=False, indent=1)
