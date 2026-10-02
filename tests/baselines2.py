#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E7b — Stronger baselines that do not use a model (set A).

  zsh    zsh 5.9's CORRECT option: the faulty line is typed into an interactive
         zsh, y is taken from the "zsh: correct 'x' to 'y' [nyae]?" question and
         the first word of the line is replaced with y (zsh only corrects the
         command name).
  freq   frequency-weighted nearest name: smallest Damerau–Levenshtein distance
         (≤ 2) among the commands on PATH; ties go to the command used more often
         in the NL2Bash corpus (a rough proxy for real-world usage frequency).

Evaluation is the same as in E6/E8 (same experiment directory, same judge).
Usage (root):  python3 baselines2.py run && python3 baselines2.py summary
"""
import collections
import json
import os
import re
import sys
import time

import pexpect

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm_eval as E  # noqa: E402
import baselines as B  # noqa: E402

OUT = os.path.join(E.RESULTS, "baselines2_scores.json")
SUMMARY = os.path.join(E.RESULTS, "baselines2_summary.json")
ZENV = {"HOME": "/tmp", "PATH": B.EVAL_PATH, "TERM": "dumb", "LANG": "C.UTF-8"}


def zsh_correct(line):
    c = pexpect.spawn("/usr/bin/zsh", ["-f", "-i"], env=ZENV, encoding="utf-8", timeout=5,
                      cwd="/tmp")
    try:
        c.sendline("PS1='ZP> '; setopt CORRECT; echo SYNC1")
        c.expect("SYNC1\r\n")
        c.expect("ZP> ")
        c.sendline(line)
        i = c.expect([r"zsh: correct '(.*?)' to '(.*?)' \[nyae\]\? ", "ZP> ",
                       r"[a-z]+> "])   # quote> dquote>: line is incomplete
        return c.match.group(2) if i == 0 else None
    finally:
        c.terminate(force=True)


def osa(a, b):
    """Damerau–Levenshtein (optimal string alignment) distance."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def nl2bash_freq():
    cnt = collections.Counter()
    for cm in open(E.CM_PATH, encoding="utf-8", errors="replace"):
        for seg in re.split(r"\|\||&&|[|;]|\$\(|`", cm):
            w = seg.strip().split()
            if w:
                cnt[os.path.basename(w[0])] += 1
    return cnt


def freq_nearest(inp, exes, freq):
    words = inp.split(" ", 1)
    best = None
    for e in exes:
        d = osa(words[0], e)
        if d <= 2:
            key = (d, -freq.get(e, 0), e)
            if best is None or key < best:
                best = key
    return " ".join([best[2]] + words[1:]) if best else None


def run():
    os.environ["PATH"] = B.EVAL_PATH
    exes = B._executables()
    freq = nl2bash_freq()
    items = [i for i in json.load(open(E.ITEMS)) if i["set"] == "A"]
    rows = []
    for it in items:
        for name in ("zsh", "freq"):
            t0 = time.perf_counter()
            if name == "zsh":
                fix = zsh_correct(it["input"])
                cmd = None
                if fix:
                    w = it["input"].split(" ", 1)
                    cmd = " ".join([fix] + w[1:])
            else:
                cmd = freq_nearest(it["input"], exes, freq)
            dt = (time.perf_counter() - t0) * 1000
            row = {"id": it["id"], "set": "A", "method": name, "cmd": cmd, "ms": round(dt, 2)}
            ref = dict(it["ref_result"], timeout=False)
            if cmd:
                row["ok_shellm"] = E.judge(it, ref, E.execute("shellm", cmd, it.get("probe")))
                row["ok_bash"] = E.judge(it, ref, E.execute("bash", cmd, it.get("probe")))
            else:
                row["ok_shellm"] = row["ok_bash"] = False
            rows.append(row)
            print(it["id"], name, row["ok_shellm"], repr(it["input"]), "->", repr(cmd), flush=True)
    json.dump(rows, open(OUT, "w"), ensure_ascii=False, indent=1)


def summary():
    rows = json.load(open(OUT))
    llm = {(r["id"], r["prompt"]): r for r in json.load(open(E.SCORES))}
    res = {}
    for m in ("zsh", "freq"):
        R = [r for r in rows if r["method"] == m]
        b = sum(1 for r in R if llm[(r["id"], "v2")]["ok_shellm"] and not r["ok_shellm"])
        c = sum(1 for r in R if r["ok_shellm"] and not llm[(r["id"], "v2")]["ok_shellm"])
        res[m] = {"n": len(R), "none": sum(1 for r in R if not r["cmd"]),
                  "acc_shellm": E._pct(sum(1 for r in R if r["ok_shellm"]), len(R)),
                  "acc_bash": E._pct(sum(1 for r in R if r["ok_bash"]), len(R)),
                  "same_cmd_as_ref": sum(1 for r in R if r["cmd"] and r["cmd"].split()[0] ==
                                         next(i for i in json.load(open(E.ITEMS)) if i["id"] == r["id"])["ref"].split()[0]),
                  "median_ms": sorted(r["ms"] for r in R)[len(R) // 2],
                  "vs_shellm_prompt_discordant": [b, c], "vs_shellm_prompt_mcnemar_p": E._mcnemar(b, c)}
    json.dump(res, open(SUMMARY, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"run": run, "summary": summary}[sys.argv[1]]()
