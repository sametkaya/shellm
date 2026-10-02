#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E7 — Comparison with correction tools that do not use a model.

On the same A (typo) and B (Turkish natural language) tasks, two baselines are
tested with the same execution-based evaluation as in E6:
  thefuck  — rule-based command corrector (nvbn/thefuck), first suggestion (top-1);
             its input is Bash's "command not found" message.
  nearest  — simple matcher that replaces the first word with the closest
             command name on PATH (difflib, cutoff 0.6); same as SheLLM's mock backend.
For both methods the candidate commands are those on the PATH of the environment
where suggestions are executed (/usr/local/bin:/usr/bin:/bin) plus SheLLM's builtins.

Usage (root):  python3 baselines.py run && python3 baselines.py summary
Prerequisite: llm_eval.py prepare has been run (results/llm_items.json).
"""
import difflib
import json
import os
import statistics as st
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm_eval as E  # noqa: E402

EVAL_PATH = "/usr/local/bin:/usr/bin:/bin"
OUT = os.path.join(E.RESULTS, "baselines_scores.json")
SUMMARY = os.path.join(E.RESULTS, "baselines_summary.json")


def _executables():
    names = set(E.llm_tasks.BUILTINS)
    for d in EVAL_PATH.split(":"):
        try:
            for n in os.listdir(d):
                if os.access(os.path.join(d, n), os.X_OK):
                    names.add(n)
        except OSError:
            pass
    return sorted(names)


def nearest(inp, exes):
    words = inp.split(" ", 1)
    m = difflib.get_close_matches(words[0], exes, n=1, cutoff=0.6)
    return " ".join([m[0]] + words[1:]) if m else None


def thefuck_suggest(inp):
    from thefuck.types import Command
    from thefuck.corrector import get_corrected_commands
    first = inp.split()[0] if inp.split() else inp
    out = "bash: %s: command not found\n" % first
    for c in get_corrected_commands(Command(inp, out)):
        return c.script
    return None


def run():
    os.environ["PATH"] = EVAL_PATH
    from thefuck.conf import settings
    settings.init()
    exes = _executables()
    items = [i for i in json.load(open(E.ITEMS)) if i["set"] in "AB"]
    rows = []
    for it in items:
        for name in ("thefuck", "nearest"):
            t0 = time.perf_counter()
            cmd = thefuck_suggest(it["input"]) if name == "thefuck" else nearest(it["input"], exes)
            dt = (time.perf_counter() - t0) * 1000
            row = {"id": it["id"], "set": it["set"], "method": name, "cmd": cmd, "ms": round(dt, 2)}
            ref = dict(it["ref_result"], timeout=False)
            if cmd:
                row["ok_shellm"] = E.judge(it, ref, E.execute("shellm", cmd, it.get("probe")))
                row["ok_bash"] = E.judge(it, ref, E.execute("bash", cmd, it.get("probe")))
                row["risk"], row["syntax"] = E.check(cmd)
            else:
                row["ok_shellm"] = row["ok_bash"] = False
                row["risk"] = row["syntax"] = ""
            rows.append(row)
            print(it["id"], name, row["ok_shellm"], repr(cmd)[:60], flush=True)
    json.dump(rows, open(OUT, "w"), ensure_ascii=False, indent=1)


def summary():
    rows = json.load(open(OUT))
    llm = {(r["id"], r["prompt"]): r for r in json.load(open(E.SCORES))}
    res = {}
    for s in "AB":
        for m in ("thefuck", "nearest"):
            R = [r for r in rows if r["set"] == s and r["method"] == m]
            res["%s_%s" % (s, m)] = {
                "n": len(R),
                "none": sum(1 for r in R if not r["cmd"]),
                "acc_shellm": E._pct(sum(1 for r in R if r["ok_shellm"]), len(R)),
                "acc_bash": E._pct(sum(1 for r in R if r["ok_bash"]), len(R)),
                "risky": E._pct(sum(1 for r in R if r.get("risk")), len(R)),
                "median_ms": round(st.median(r["ms"] for r in R), 2),
            }
            # paired comparison with the SheLLM prompt (exact McNemar test)
            b = sum(1 for r in R if llm[(r["id"], "v2")]["ok_shellm"] and not r["ok_shellm"])
            c = sum(1 for r in R if r["ok_shellm"] and not llm[(r["id"], "v2")]["ok_shellm"])
            res["%s_%s" % (s, m)]["vs_shellm_prompt_discordant"] = [b, c]
            res["%s_%s" % (s, m)]["vs_shellm_prompt_mcnemar_p"] = E._mcnemar(b, c)
    json.dump(res, open(SUMMARY, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"run": run, "summary": summary}[sys.argv[1]]()
