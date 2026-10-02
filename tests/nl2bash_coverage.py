#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SheLLM syntax coverage of the NL2Bash reference commands.

The expert-written Bash commands in the NL2Bash corpus (Lin et al., 2018) serve
as a representative sample of the commands a language model is expected to
produce for natural language requests. For each command the script determines:
  * syntax_issue: whether it contains an unsupported syntax element, according
    to the --check mode of the SheLLM core (v2),
  * expansion requirement: whether it uses an unquoted ~ or *, ?, [
    (v1 does not expand these, so such a command does not behave as in Bash).
It also computes the share of commands that need an "evet" ("yes")
confirmation according to risk_reason.
"""
import collections
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
import sys  # noqa: E402
sys.path.insert(0, HERE)
from paths import V2_BIN as SHELLM, NL2BASH_CM as DATA  # noqa: E402


def needs_expansion(cmd):
    """Is there, outside quotes, a ~ at the start of a word or a *, ? or [?"""
    q = None
    word_start = True
    for i, ch in enumerate(cmd):
        if q:
            if ch == q:
                q = None
            continue
        if ch in "'\"":
            q = ch
            word_start = False
            continue
        if ch == "~" and word_start and (i + 1 == len(cmd) or cmd[i + 1] in "/ \t|<>"):
            return True
        if ch in "*?[":
            return True
        word_start = ch in " \t|<>"
    return False


def check(cmd):
    p = subprocess.run([SHELLM, "--check", cmd], capture_output=True, text=True)
    risk = syn = None
    for line in p.stdout.splitlines():
        k, _, v = line.partition("\t")
        if k == "risk":
            risk = None if v == "-" else v
        elif k == "syntax":
            syn = None if v == "-" else v
    return cmd, risk, syn


def main():
    cmds = [l.rstrip("\n") for l in open(DATA, encoding="utf-8", errors="replace")]
    uniq = sorted(set(c for c in cmds if c.strip()))
    with ThreadPoolExecutor(max_workers=16) as ex:
        rows = list(ex.map(check, uniq))
    n = len(rows)
    syn_ok = [r for r in rows if r[2] is None]
    exp = [r for r in syn_ok if needs_expansion(r[0])]
    risky = [r for r in rows if r[1]]
    by_issue = collections.Counter(r[2] for r in rows if r[2])
    by_risk = collections.Counter(r[1] for r in risky)
    res = {
        "unique_commands": n,
        "syntax_supported": len(syn_ok),
        "syntax_supported_pct": round(100 * len(syn_ok) / n, 1),
        "needs_tilde_or_glob_among_supported": len(exp),
        "v1_executable": len(syn_ok) - len(exp),
        "v1_executable_pct": round(100 * (len(syn_ok) - len(exp)) / n, 1),
        "v2_executable": len(syn_ok),
        "v2_executable_pct": round(100 * len(syn_ok) / n, 1),
        "unsupported_by_first_issue": by_issue.most_common(),
        "risky": len(risky),
        "risky_pct": round(100 * len(risky) / n, 1),
        "risky_by_reason": by_risk.most_common(),
        "examples_unsupported": [r[0] for r in rows if r[2]][:15],
        "examples_needs_expansion": [r[0] for r in exp][:15],
    }
    json.dump(res, open(os.path.join(HERE, "results", "nl2bash_coverage.json"), "w"),
              ensure_ascii=False, indent=1)
    for k, v in res.items():
        if isinstance(v, list):
            print(k)
            for x in v[:12]:
                print("   ", x)
        else:
            print(k, v)


if __name__ == "__main__":
    main()
