#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compares SheLLM results with the Bash reference results."""
import json
import os
import sys
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cases import CATEGORIES  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def load(name):
    # SHELLM_RESULTS lets "make test" compare fresh runs without touching the
    # recorded results in tests/results/.
    d = os.environ.get("SHELLM_RESULTS") or os.path.join(HERE, "results")
    return {r["id"]: r for r in json.load(open(os.path.join(d, name + ".json")))}


def judge(ref, got):
    reasons = []
    if got["timeout"]:
        reasons.append("timeout")
    if got["crash"]:
        reasons.append("crash (signal %d)" % -got["rc"])
    if got["stdout"] != ref["stdout"]:
        reasons.append("stdout")
    if got["rc"] != ref["rc"]:
        reasons.append("exit status %s≠%s" % (got["rc"], ref["rc"]))
    if bool(got["stderr"].strip()) != bool(ref["stderr"].strip()):
        reasons.append("stderr presence")
    return (len(reasons) == 0), reasons


def summarize(impl, ref="bash", verbose=True):
    R, G = load(ref), load(impl)
    per = OrderedDict((c, [0, 0]) for c in CATEGORIES)
    fails = []
    for cid in sorted(R):
        ok, why = judge(R[cid], G[cid])
        per[cid[0]][1] += 1
        if ok:
            per[cid[0]][0] += 1
        else:
            fails.append((cid, why))
    return per, fails


if __name__ == "__main__":
    args = sys.argv[1:]
    suffix = ""
    if args and args[0] == "--holdout":
        suffix = "_holdout"
        args = args[1:]
    impls = args or ["v1", "v2"]
    table = {}
    for impl in impls:
        per, fails = summarize(impl + suffix, ref="bash" + suffix)
        table[impl] = (per, fails)
    print("%-4s %-36s" % ("Cat", "Name") + "".join("%10s" % i for i in impls))
    tot = {i: [0, 0] for i in impls}
    sup = {i: [0, 0] for i in impls}
    for c, name in CATEGORIES.items():
        row = "%-4s %-36s" % (c, name)
        for i in impls:
            p, n = table[i][0][c]
            row += "%10s" % ("%d/%d" % (p, n))
            tot[i][0] += p; tot[i][1] += n
            if c != "L":
                sup[i][0] += p; sup[i][1] += n
        print(row)
    print("-" * 70)
    print("%-41s" % "Supported syntax (excluding L)" + "".join("%10s" % ("%d/%d" % tuple(sup[i])) for i in impls))
    print("%-41s" % "Total" + "".join("%10s" % ("%d/%d" % tuple(tot[i])) for i in impls))
    for i in impls:
        print("\n== %s failed tests ==" % i)
        for cid, why in table[i][1]:
            print("  %s: %s" % (cid, ", ".join(why)))
