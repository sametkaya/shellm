#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E7c — Testing the four model-free baselines on natural language requests (B, E)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import llm_eval as E  # noqa: E402
import baselines as B  # noqa: E402
import baselines2 as B2  # noqa: E402

OUT = os.path.join(E.RESULTS, "baselines_nl_scores.json")


def main():
    os.environ["PATH"] = B.EVAL_PATH
    from thefuck.conf import settings
    settings.init()
    exes = B._executables()
    freq = B2.nl2bash_freq()
    items = [i for i in json.load(open(os.path.join(E.RESULTS, "llm2_items.json"))) if i["set"] in "BE"]
    rows = []
    for it in items:
        for name in ("nearest", "thefuck", "zsh", "freq"):
            if name == "nearest":
                cmd = B.nearest(it["input"], exes)
            elif name == "thefuck":
                cmd = B.thefuck_suggest(it["input"])
            elif name == "zsh":
                fix = B2.zsh_correct(it["input"])
                cmd = " ".join([fix] + it["input"].split(" ", 1)[1:]) if fix else None
            else:
                cmd = B2.freq_nearest(it["input"], exes, freq)
            ok = False
            if cmd:
                ref = dict(it["ref_result"], timeout=False)
                ok = E.judge(it, ref, E.execute("shellm", cmd, it.get("probe")))
            rows.append({"id": it["id"], "set": it["set"], "method": name, "cmd": cmd, "ok_shellm": ok})
            print(it["id"], name, ok, repr(cmd)[:70], flush=True)
    json.dump(rows, open(OUT, "w"), ensure_ascii=False, indent=1)
    for s in "BE":
        for m in ("nearest", "thefuck", "zsh", "freq"):
            R = [r for r in rows if r["set"] == s and r["method"] == m]
            print(s, m, "correct", sum(r["ok_shellm"] for r in R), "/", len(R), "suggestions", sum(1 for r in R if r["cmd"]))


if __name__ == "__main__":
    main()
