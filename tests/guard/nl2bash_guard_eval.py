# -*- coding: utf-8 -*-
"""Evaluation of the risk checker on the NL2Bash sample.
Labels: two independent annotators + the author's decision on 3 disagreements (nl2bash_gold.json).
Checks run in an empty temporary directory (so the existing-file rule does not apply).
Usage: python3 nl2bash_guard_eval.py <SheLLM binary> [gold JSON]"""
import json, os, subprocess, sys, tempfile, collections
# The shell's interface is bilingual (English by default, Turkish when
# SHELLM_LANG=tr). The scripts match English interface text and store English
# risk reasons, so pin the language to English regardless of the locale.
os.environ.setdefault("SHELLM_LANG", "en")
# Old (pre-revision) rules: "make legacy-guard" builds this binary from
# tests/guard/ai_guard_old.c; SHELLM_OLD_BIN overrides it.
OLD_BIN = os.environ.get("SHELLM_OLD_BIN", os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "shellm_old_guard"))
GOLD = sys.argv[2] if len(sys.argv) > 2 else "nl2bash_gold.json"
gold = json.load(open(GOLD))
def check(binary, cmd, d):
    out = subprocess.run([binary, "--check", cmd], capture_output=True, text=True, cwd=d,
                         env=dict(os.environ, HOME=d), timeout=5).stdout
    for l in out.splitlines():
        k, _, v = l.partition("\t")
        if k == "risk":
            return "" if v.strip() == "-" else v.strip()
    return ""
d = tempfile.mkdtemp()
res = {}
for name, b in (("old", OLD_BIN), ("new", sys.argv[1])):
    rows = [(g, check(b, g["cmd"], d)) for g in gold]
    def pr(sub):
        tp = sum(1 for g, f in sub if g["label"] and f); fn = sum(1 for g, f in sub if g["label"] and not f)
        fp = sum(1 for g, f in sub if not g["label"] and f); tn = sum(1 for g, f in sub if not g["label"] and not f)
        return {"tp": tp, "fn": fn, "fp": fp, "tn": tn,
                "recall": round(tp / (tp + fn), 3) if tp + fn else None,
                "precision": round(tp / (tp + fp), 3) if tp + fp else None,
                "fpr": round(fp / (fp + tn), 3) if fp + tn else None}
    res[name] = {"all": pr(rows), "random": pr([r for r in rows if r[0]["stratum"] == "random"]),
                 "enriched": pr([r for r in rows if r[0]["stratum"] == "enriched"]),
                 "by_cat_recall": {c: "%d/%d" % (sum(1 for g, f in rows if g["cat"] == c and f),
                                                 sum(1 for g, f in rows if g["cat"] == c))
                                   for c in ("DEL", "OVW", "PRIV", "SYS", "NET")},
                 "misses": [(g["pid"], g["cat"], g["cmd"]) for g, f in rows if g["label"] and not f],
                 "false_alarms": [(g["pid"], g["cmd"], f) for g, f in rows if not g["label"] and f]}
    print(name, res[name]["all"], res[name]["by_cat_recall"])
    print("  random", res[name]["random"], " enriched", res[name]["enriched"])
json.dump(res, open(GOLD.replace("gold", "guard_result"), "w"), ensure_ascii=False, indent=1)
print("\nMISSED (new):"); [print("  ", m) for m in res["new"]["misses"]]
print("FALSE ALARMS (new):"); [print("  ", m) for m in res["new"]["false_alarms"]]
