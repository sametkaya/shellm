#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E9 — Trigger coverage: which inputs actually reach the helper?

Every input in sets A (typos), B (Turkish requests), E (English requests) and
C (NL2Bash) is typed into SheLLM in a real terminal (pexpect), and whether the
suggestion box opens is recorded. A mock backend that returns a fixed reply is
used instead of a model; only the shell's trigger decision is measured.

Variants:
  old     triggers when the exit status is 127 (previous version)
  new     the shell's own "command not found" decision + an unmatched apostrophe
  prefix  new + "# " prepended to the line (explicit request path)

Because the inputs are really executed, they are run under the unprivileged
'kullanici' account, in the experiment directory.
Usage (root):  python3 trigger_coverage.py
"""
import collections
import json
import os
import sys
import time

import pexpect

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import V2_DIR, RESULTS  # noqa: E402
import llm_fixture as fx  # noqa: E402
import llm_eval as E  # noqa: E402

OUT = os.path.join(RESULTS, "trigger_coverage.json")
# The "old" variant is the release before the review-driven revision, which
# triggered on exit status 127. It is not built from this tree; set
# SHELLM_OLD_BIN to such a build to replay it (otherwise it is skipped).
OLD_BIN = os.environ.get("SHELLM_OLD_BIN", "")
NEW_BIN = os.environ.get("SHELLM_NEW_BIN", os.path.join(V2_DIR, "SheLLM"))
BOX = "shellm suggestion"   # title of the suggestion box (English interface)


def spawn(binary):
    env = {"HOME": fx.HOME, "PATH": "/usr/local/bin:/usr/bin:/bin", "USER": E.EVAL_USER,
           "LOGNAME": E.EVAL_USER, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TERM": "xterm",
           "SHELLM_BACKEND": "mock", "SHELLM_MOCK_FIXED": "echo MOCKOK",
           "SHELLM_HELPER": os.path.join(V2_DIR, "ai_helper.py"),
           # This env does not inherit os.environ, so pass the interface
           # language explicitly: BOX is matched in the English interface.
           "SHELLM_LANG": "en", "SHELLM_NO_SETUP": "1"}
    c = pexpect.spawn(E.RUNUSER, ["-u", E.EVAL_USER, "--", binary], env=env, cwd=fx.LAB,
                      encoding="utf-8", timeout=10)
    c.expect("sheLLM ")
    return c


def probe(c, line):
    """Types the line; declines the suggestion box if it opens. Returns (fired, hung)."""
    c.sendline(line)
    i = c.expect([BOX, "sheLLM ", pexpect.TIMEOUT], timeout=6)
    if i == 0:
        c.sendline("h")
        c.expect("sheLLM ", timeout=6)
        return True, False
    if i == 2:
        c.sendintr()
        c.expect("sheLLM ", timeout=6)
        return False, True
    return False, False


def main():
    items = [i for i in json.load(open(os.path.join(RESULTS, "llm2_items.json")))
             if i["set"] in "ABEC"]
    uid, gid = E._user()
    res = []
    variants = [("new", NEW_BIN, ""), ("prefix", NEW_BIN, "# ")]
    if OLD_BIN and os.path.exists(OLD_BIN):
        variants.insert(0, ("old", OLD_BIN, ""))
    else:
        print("note: SHELLM_OLD_BIN not set; skipping the old-rule variant")
    for variant, binary, pre in variants:
        fx.create(uid, gid)
        c = spawn(binary)
        for n, it in enumerate(items):
            if n and n % 50 == 0:          # rebuild the directory every now and then
                c.sendline("exit"); c.expect(pexpect.EOF)
                fx.create(uid, gid)
                c = spawn(binary)
            try:
                fired, hung = probe(c, pre + it["input"])
            except (pexpect.TIMEOUT, pexpect.EOF):
                fired, hung = False, True
                c.terminate(force=True)
                fx.create(uid, gid)
                c = spawn(binary)
            res.append({"id": it["id"], "set": it["set"], "variant": variant,
                        "fired": fired, "hung": hung})
            print(variant, it["id"], fired, repr(it["input"])[:60], flush=True)
        c.sendline("exit")
        c.expect(pexpect.EOF)
    json.dump(res, open(OUT, "w"), ensure_ascii=False, indent=1)
    summary(res, items)


def summary(res=None, items=None):
    res = res or json.load(open(OUT))
    items = items or [i for i in json.load(open(os.path.join(RESULTS, "llm2_items.json")))
                      if i["set"] in "ABEC"]
    info = {i["id"]: i for i in items}
    tab = collections.defaultdict(lambda: [0, 0])
    for r in res:
        k = (r["set"], r["variant"])
        tab[k][1] += 1
        tab[k][0] += r["fired"]
    out = {"%s_%s" % k: "%d/%d" % tuple(v) for k, v in sorted(tab.items())}
    # inputs with an odd number of apostrophes, and inputs starting with a command name
    for s in "BEC":
        ids = [i for i in info if info[i]["set"] == s]
        odd = [i for i in ids if info[i]["input"].count("'") % 2 == 1]
        out[s + "_odd_apostrophe"] = len(odd)
        out[s + "_first_word_is_command"] = sum(1 for i in ids if info[i].get("first_word_is_command"))
        for v in ("old", "new"):
            out["%s_odd_apostrophe_fired_%s" % (s, v)] = sum(
                1 for r in res if r["id"] in odd and r["variant"] == v and r["fired"])
    out["hung"] = sum(r["hung"] for r in res)
    json.dump(out, open(OUT.replace(".json", "_summary.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    summary() if sys.argv[1:] == ["summary"] else main()
