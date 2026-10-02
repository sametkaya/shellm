#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Robustness and security scenarios for the AI bridge (v1 and v2).

Both versions run against a deterministic mock backend instead of a real model,
so what is measured is the behaviour of the shell-service bridge, not of the
model. For v1, tests/v1_mock/ai_helper.py imitates the v1 protocol (TCP 12345,
a single recv).
"""
import json
import os
import signal
import socket
import subprocess
import sys
import time

import pexpect


def _dfl():
    # Scripts started in the background may inherit SIGINT/SIGQUIT as ignored;
    # restore the defaults, as in a real terminal.
    import signal as _s
    _s.signal(_s.SIGINT, _s.SIG_DFL)
    _s.signal(_s.SIGQUIT, _s.SIG_DFL)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import V1_BIN as V1, V1_ASAN_BIN as V1ASAN, V2_BIN as V2, V1_MOCK_DIR, RESULTS  # noqa: E402
V1DIR = V1_MOCK_DIR        # the v1 helper script lives here (v1 runs it from the cwd)
OTHER = "/tmp/v1other"      # another directory without a helper script
os.makedirs(OTHER, exist_ok=True)

SUGG = {"v1": "calistir", "v2": "shellm suggestion"}   # v1 prints Turkish (ASCII); v2 in English


def kill_helpers():
    subprocess.run(["pkill", "-f", "ai_helper.py"], capture_output=True)
    time.sleep(0.3)


def spawn(impl, cwd=None, extra_env=None, binary=None, timeout=8):
    env = dict(os.environ, TERM="xterm", HOME="/tmp", PATH="/usr/bin:/bin")
    env.pop("GEMINI_API_KEY", None)
    if impl == "v2":
        env["SHELLM_BACKEND"] = "mock"
    env.update(extra_env or {})
    b = binary or (V1 if impl == "v1" else V2)
    c = pexpect.spawn(b, env=env, encoding="utf-8", timeout=timeout,
                      cwd=cwd or (V1DIR if impl == "v1" else OTHER), preexec_fn=_dfl)
    c.expect("sheLLM ")
    return c


def ask(c, impl, line, timeout=6):
    """Sends a failing command; returns True if the suggestion box appeared."""
    c.sendline(line)
    i = c.expect([SUGG[impl], "sheLLM ", pexpect.TIMEOUT], timeout=timeout)
    if i == 0:
        c.sendline("h")
        c.expect("sheLLM ")
        return True
    return False


def close(c):
    try:
        c.sendline("exit")
        c.expect(pexpect.EOF, timeout=3)
    except Exception:
        c.terminate(force=True)
    kill_helpers()


# --------------------------------------------------------------- scenarios
def s1_builtin_pipe(impl):
    c = spawn(impl)
    ok1 = ask(c, impl, "mkdr a")
    c.sendline("echo hi | cat"); c.expect("sheLLM ")
    ok2 = ask(c, impl, "mkdr b")
    close(c)
    return ok1 and ok2


def s2_heredoc(impl):
    c = spawn(impl)
    ok1 = ask(c, impl, "mkdr a")
    c.sendline("cat << EOF"); c.sendline("line"); c.sendline("EOF"); c.expect("sheLLM ")
    ok2 = ask(c, impl, "mkdr b")
    close(c)
    return ok1 and ok2


def s3_ctrl_c(impl):
    c = spawn(impl)
    ok1 = ask(c, impl, "mkdr a")
    c.sendintr(); c.expect("sheLLM ")
    time.sleep(1.0)
    ok2 = ask(c, impl, "mkdr b")
    close(c)
    return ok1 and ok2


def s4_other_cwd(impl):
    c = spawn(impl, cwd=OTHER)
    ok = ask(c, impl, "mkdr a")
    close(c)
    return ok


def s5_foreign_listener(impl):
    """Start the shell while another process listens on the same port."""
    p = subprocess.Popen([sys.executable, "-m", "http.server", "12345", "--bind", "127.0.0.1"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="/tmp")
    time.sleep(0.8)
    c = spawn(impl)
    time.sleep(0.5)
    alive = p.poll() is None
    close(c)
    if alive:
        p.terminate(); p.wait()
    return alive


def s6_exit_code(impl):
    c = spawn(impl)
    ask(c, impl, "mkdr a")
    c.sendline("echo KOD=$?")
    c.expect(r"KOD=(\d+)")
    code = int(c.match.group(1))
    c.expect("sheLLM ")
    close(c)
    return code == 127


def s7_long_reply(impl):
    """Model reply longer than 1024 bytes (AddressSanitizer build for v1)."""
    if impl == "v1":
        c = spawn(impl, extra_env={"MOCK_BIG": "1100"}, binary=V1ASAN)
    else:
        c = spawn(impl, extra_env={"SHELLM_MOCK_BIG": "5000"})
    c.sendline("mkdr a")
    i = c.expect([SUGG[impl], "AddressSanitizer", pexpect.EOF, pexpect.TIMEOUT], timeout=8)
    ok = (i == 0)
    try:
        close(c)
    except Exception:
        kill_helpers()
    return ok


def s8_cancel_slow(impl):
    """A request must be cancellable with Ctrl+C while the model is silent for 30 s."""
    env = {"SHELLM_MOCK_DELAY": "30"}
    c = spawn(impl, extra_env=env)
    c.sendline("mkdr a")
    time.sleep(1.0)
    t0 = time.time()
    c.sendintr()
    try:
        c.expect("sheLLM ", timeout=4)
        ok = (time.time() - t0) < 4
    except pexpect.TIMEOUT:
        ok = False
    c.terminate(force=True)
    kill_helpers()
    return ok


def s9_two_instances(impl):
    a = spawn(impl)
    b = spawn(impl)
    ok_b = ask(b, impl, "mkdr b")
    ok_a = ask(a, impl, "mkdr a")
    close(b); close(a)
    return ok_a and ok_b


def s10_socket_access(impl):
    """Can another local process reach the service without going through the shell?
    (v1: public TCP port; v2: Unix socket in a 0700 directory)"""
    c = spawn(impl)
    time.sleep(0.3)
    reachable = False
    if impl == "v1":
        try:
            s = socket.create_connection(("127.0.0.1", 12345), timeout=1)
            s.send(b"mkdr x"); reachable = bool(s.recv(100)); s.close()
        except OSError:
            reachable = False
    else:
        import glob, stat
        socks = glob.glob("/tmp/shellm-*/ai.sock")
        # The directory must have mode 0700: other users cannot enter it.
        reachable = any((os.stat(os.path.dirname(p)).st_mode & 0o077) != 0 for p in socks) or not socks
    close(c)
    return not reachable


# --- Scenarios added after the review (S11–S16) -----------------------------
FIXED = {"SHELLM_MOCK_FIXED": "echo MOCKOK", "MOCK_FIXED": "echo MOCKOK"}


def s11_pipeline_stage(impl):
    """An unknown command in the first or last pipeline stage triggers."""
    c = spawn(impl, extra_env=FIXED)
    first = ask(c, impl, "grpe x /etc/hostname | wc -l")
    last = ask(c, impl, "cat /etc/hostname | grpe y")
    close(c)
    return first and last


def s12_child_127(impl):
    """A 127 returned by a child of an existing program does not trigger."""
    c = spawn(impl, extra_env=FIXED)
    fired = ask(c, impl, "sh -c 'exit 127'")
    close(c)
    return not fired


def s13_apostrophe(impl):
    """A Turkish request with an apostrophe (unmatched single quote) reaches the helper."""
    c = spawn(impl, extra_env=FIXED)
    ok = ask(c, impl, "notlar.txt'yi sil")
    close(c)
    return ok


def s14_secret(impl):
    """A line containing a password or key is not sent to the model."""
    c = spawn(impl, extra_env=FIXED)
    sent = 0
    for line in ("exprot DB_PASSWORD=hunter2hunter2",
                 "crul -H 'Authorization: token ghp_a1B2c3D4e5F6g7H8i9J0kLmNoPqRsTuV' x"):
        sent += ask(c, impl, line)
    close(c)
    return sent == 0


def s15_key_env(impl):
    """The provider key is not passed to programs started by the shell."""
    c = spawn(impl, extra_env={"GEMINI_API_KEY": "DUMMY-test-key"})
    c.sendline("env | grep -c DUMMY-test-key")
    c.expect(r"\r(\d+)\r\n")
    n = int(c.match.group(1))
    c.expect("sheLLM ")
    close(c)
    return n == 0


def s16_explicit(impl):
    """A '# request' line goes to the helper without being run; a bare '#' is a comment."""
    c = spawn(impl, extra_env=FIXED)
    ok = ask(c, impl, "# find all python files")
    bare = ask(c, impl, "#")
    close(c)
    return ok and not bare


SCENARIOS = [
    ("S1", "Suggestion after a built-in in a pipeline", s1_builtin_pipe),
    ("S2", "Suggestion after a here-document", s2_heredoc),
    ("S3", "Suggestion after Ctrl+C at the prompt", s3_ctrl_c),
    ("S4", "Suggestion when started from another directory", s4_other_cwd),
    ("S5", "Unrelated process on the same port is left alone", s5_foreign_listener),
    ("S6", "$? = 127 after a skipped suggestion", s6_exit_code),
    ("S7", "Reply longer than 1024 bytes is handled safely", s7_long_reply),
    ("S8", "Slow model request can be cancelled with Ctrl+C", s8_cancel_slow),
    ("S9", "Two shell instances get suggestions at once", s9_two_instances),
    ("S10", "Service is closed to other local users", s10_socket_access),
    ("S11", "Unknown command in any pipeline stage", s11_pipeline_stage),
    ("S12", "127 from a child process does not trigger", s12_child_127),
    ("S13", "Turkish request with apostrophe reaches helper", s13_apostrophe),
    ("S14", "Line with password/key is not sent", s14_secret),
    ("S15", "API key does not reach child environment", s15_key_env),
    ("S16", "'# request' explicit path; bare '#' is a comment", s16_explicit),
]

if __name__ == "__main__":
    only = sys.argv[1:] or None
    res = {}
    for sid, name, fn in SCENARIOS:
        if only and sid not in only:
            continue
        res[sid] = {"name": name}
        for impl in (("v1", "v2") if os.path.exists(V1) else ("v2",)):
            kill_helpers()
            try:
                ok = bool(fn(impl))
            except Exception as e:
                ok = False
                res[sid][impl + "_err"] = type(e).__name__
            res[sid][impl] = ok
            kill_helpers()
        print("%-4s %-52s v1=%-5s v2=%-5s" % (sid, name, res[sid].get("v1", "-"), res[sid]["v2"]), flush=True)
    out = os.path.join(RESULTS, "scenarios.json")
    if os.path.exists(out):
        old = json.load(open(out))
        for sid, r in list(res.items()):  # keep recorded v1 results if v1 was not run
            if "v1" not in r and "v1" in old.get(sid, {}):
                res[sid] = {"name": r["name"], "v1": old[sid]["v1"],
                            **{k: v for k, v in r.items() if k != "name"}}
        if only:
            old.update(res); res = old
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
