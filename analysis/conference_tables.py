#!/usr/bin/env python3
"""Generates the numbers and tables of the conference paper from the experiment results.
Outputs (output/conference/): numbers.tex (macros), tab_quality.tex, tab_trigger.tex,
tab_ablation.tex"""
import collections
import json
import os
import statistics as st
from math import comb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
R = os.path.join(ROOT, "tests", "results")
G = os.path.join(ROOT, "tests", "guard")
OUT = os.path.join(HERE, "output", "conference")
os.makedirs(OUT, exist_ok=True)
PEND = r"\pend{--}"

MODELS = [  # (provider, model, table label: two lines)
    ("gemini", "gemini-3.5-flash-lite", ("Gemini 3.5", "Flash-Lite")),
    ("anthropic", "claude-haiku-4-5-20251001", ("Claude", "Haiku 4.5")),
    ("openai", "gpt-5.4-mini-2026-03-17", ("GPT-5.4", "mini")),
    ("local", "qwen2.5-coder-1.5b-instruct-q4_k_m", ("Qwen2.5-Coder", "1.5B, local")),
]


def load(p, default=None):
    try:
        return json.load(open(p))
    except (OSError, ValueError):
        return default


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def fmtp(p):
    if p is None:
        return PEND
    if p < 0.001:
        return r"{<}\,0.001"
    return "{=}\\,%s" % (("%.3f" % p) if p < 0.01 else ("%.2f" % p))


macros = {}


def M(name, val):
    macros[name] = val


# -------------------------------------------------------------- LLM scores
rows = load(os.path.join(R, "llm2_scores.json"), [])
models_present = sorted({(r["provider"], r["model"]) for r in rows})
resolved = []
for prov, model, label in MODELS:
    if model is None:
        cand = [m for p, m in models_present if p == prov]
        model = cand[0] if cand else None
    resolved.append((prov, model, label))

by = collections.defaultdict(list)
for r in rows:
    by[(r["provider"], r["model"], r["cond"], r["set"], r["rep"])].append(r)


def acc(prov, model, cond, s, rep=1):
    R_ = by.get((prov, model, cond, s, rep))
    if not R_ or len(R_) < 100:
        return None
    if s == "C":
        return st.mean(x["nlc2cmd"] for x in R_)
    return 100.0 * sum(x["ok_shellm"] for x in R_) / len(R_)


def okmap(prov, model, cond, s, rep=1):
    return {x["id"][1:]: x["ok_shellm"] for x in by.get((prov, model, cond, s, rep), [])}


def pct(v):
    return PEND if v is None else "%.0f" % v


def nlc(v):
    if v is None:
        return PEND
    return ("$-$%.2f" % abs(v)) if v < 0 else "%.2f" % v


gp, gm = "gemini", "gemini-3.5-flash-lite"
M("numGemAcc", pct(acc(gp, gm, "C1K1", "A")))
M("numGemB", pct(acc(gp, gm, "C1K1", "B")))
M("numGemE", pct(acc(gp, gm, "C1K1", "E")))
M("numGemCvOne", nlc(acc(gp, gm, "V1", "C")))
M("numGemCshellm", nlc(acc(gp, gm, "C1K1", "C")))
Cr = by.get((gp, gm, "C1K1", "C", 1), [])
Cp = [x for x in Cr if x["cmd"]]
M("numGemCunsup", "%.0f" % (100.0 * sum(1 for x in Cp if x.get("syntax")) / len(Cp)) if Cp else PEND)
tr, en = okmap(gp, gm, "C1K1", "B"), okmap(gp, gm, "C1K1", "E")
if tr and en:
    b = sum(1 for i in tr if tr[i] and not en.get(i)); c = sum(1 for i in tr if en.get(i) and not tr[i])
    M("numGemTrEnDisc", "%d\\,vs.\\,%d" % (b, c))
else:
    M("numGemTrEnDisc", PEND)

# baselines (set A)
b2 = load(os.path.join(R, "baselines2_summary.json"), {})
M("numZshAcc", "%.0f" % b2["zsh"]["acc_shellm"] if b2 else PEND)
M("numFreqAcc", "%.0f" % b2["freq"]["acc_shellm"] if b2 else PEND)
M("numZshP", fmtp(b2["zsh"]["vs_shellm_prompt_mcnemar_p"]) if b2 else PEND)
M("numFreqP", fmtp(b2["freq"]["vs_shellm_prompt_mcnemar_p"]) if b2 else PEND)

# --------------------------------------------------------------- trigger
tc = load(os.path.join(R, "trigger_coverage_summary.json"), {})


def frac(k):
    return tc.get(k, "--/--").split("/")[0]


M("numTrigBapos", str(tc.get("B_odd_apostrophe", PEND)))
M("numTrigBold", frac("B_old"))
M("numTrigBnew", frac("B_new"))
items = load(os.path.join(R, "llm2_items.json"), [])
M("numTrigEcmd", str(sum(1 for i in items if i["set"] == "E" and i.get("first_word_is_command"))))
with open(os.path.join(OUT, "tab_trigger.tex"), "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Inputs that reach the assistant in a real terminal (of 100 per set)}
\label{tab:trigger}
\centering
\footnotesize
\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}lcccc@{}}
\toprule
Trigger & A: typos & B: Turkish & E: English & C: NL2Bash \\
\midrule
""")
    for v, label in (("old", r"\cmd{\$?}\,=\,127 (old)"), ("new", "name, quote (new)"),
                     ("prefix", r"new, \cmd{\#} prefix")):
        f.write(label + " & " + " & ".join(frac("%s_%s" % (s, v)) for s in "ABEC") + r" \\" + "\n")
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")

# --------------------------------------------------------- quality table
bl = load(os.path.join(R, "baselines_summary.json"), {})
bnl = load(os.path.join(R, "baselines_nl_scores.json"), [])
lat = load(os.path.join(R, "llm2_summary.json"), {}).get("latency", {})


def nl_base(method, s):
    R_ = [r for r in bnl if r["method"] == method and r["set"] == s]
    return pct(100.0 * sum(r["ok_shellm"] for r in R_) / len(R_)) if R_ else PEND


with open(os.path.join(OUT, "tab_quality.tex"), "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Suggestion quality (\% correct when executed in SheLLM; C: NLC2CMD score in $[-1,1]$) and median latency}
\label{tab:quality}
\centering
\footnotesize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}llccccr@{}}
\toprule
Method & Prompt & A & B & E & C & Time \\
\midrule
""")
    base = [("thefuck 3.32", "thefuck", bl.get("A_thefuck", {}).get("acc_shellm"), "25\\,ms"),
            ("\\cmd{difflib} nearest", "nearest", bl.get("A_nearest", {}).get("acc_shellm"), "1\\,ms"),
            ("zsh \\cmd{CORRECT}", "zsh", b2.get("zsh", {}).get("acc_shellm"), "--"),
            ("frequency matcher", "freq", b2.get("freq", {}).get("acc_shellm"), "15\\,ms")]
    for label, key, a, t in base:
        f.write("%s & -- & %s & %s & %s & -- & %s \\\\\n" % (label, pct(a), nl_base(key, "B"), nl_base(key, "E"), t))
    for prov, model, label in resolved:
        f.write("\\midrule\n")
        for cond, cl in (("V1", "baseline"), ("C1K1", "SheLLM")):
            vals = [pct(acc(prov, model, cond, s)) if model else PEND for s in "ABE"]
            c = nlc(acc(prov, model, cond, "C")) if model else PEND
            L = lat.get("%s/%s %s" % (prov, model, cond))
            t = ("%.2f\\,s" % L["median"]) if L else PEND
            name = label[0] if cond == "V1" else label[1]
            f.write("%s & %s & %s & %s & %s & %s & %s \\\\\n" % (name, cl, vals[0], vals[1], vals[2], c, t))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")

# -------------------------------------------------------------- ablation
with open(os.path.join(OUT, "tab_ablation.tex"), "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Prompt ablation with Gemini (\% correct; C: NLC2CMD score; Unsupp.: C suggestions using constructs SheLLM does not support)}
\label{tab:ablation}
\centering
\footnotesize
\setlength{\tabcolsep}{3.5pt}
\begin{tabular}{@{}cccccccc@{}}
\toprule
Context & Constraints & A & B & E & C & Unsupp. \\
\midrule
""")
    for cond, cx, kx in (("C1K1", "yes", "yes"), ("C0K1", "no", "yes"), ("C1K0", "yes", "no"), ("C0K0", "no", "no")):
        vals = [pct(acc(gp, gm, cond, s)) for s in "ABE"]
        CR = by.get((gp, gm, cond, "C", 1), [])
        CP = [x for x in CR if x["cmd"]]
        un = ("%.0f\\%%" % (100.0 * sum(1 for x in CP if x.get("syntax")) / len(CP))) if len(CR) == 100 else PEND
        f.write("%s & %s & %s & %s & %s & %s & %s \\\\\n" % (cx, kx, vals[0], vals[1], vals[2], nlc(acc(gp, gm, cond, "C")), un))
    f.write("\\midrule\n")
    vals = [pct(acc(gp, gm, "V1", s)) for s in "ABE"]
    CR = by.get((gp, gm, "V1", "C", 1), [])
    CP = [x for x in CR if x["cmd"]]
    un = ("%.0f\\%%" % (100.0 * sum(1 for x in CP if x.get("syntax")) / len(CP))) if len(CR) == 100 else PEND
    f.write("\\multicolumn{2}{c}{baseline prompt} & %s & %s & %s & %s & %s \\\\\n" % (vals[0], vals[1], vals[2], nlc(acc(gp, gm, "V1", "C")), un))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")


# ------------------------------------------------ comparisons between models
KEYS = {"gemini": "Gem", "anthropic": "Cla", "openai": "Gpt", "local": "Loc"}


def holm(ps):
    order = sorted(ps.items(), key=lambda kv: kv[1])
    m, out, run = len(order), {}, 0.0
    for k, (name, p) in enumerate(order):
        run = max(run, min(1.0, (m - k) * p))
        out[name] = run
    return out


fam1, fam2 = {}, {}
for prov, model, label in resolved:
    k = KEYS[prov]
    M("num%sCvOne" % k, nlc(acc(prov, model, "V1", "C")) if model else PEND)
    M("num%sCshellm" % k, nlc(acc(prov, model, "C1K1", "C")) if model else PEND)
    for s in "ABE":
        M("num%s%sS" % (k, s), pct(acc(prov, model, "C1K1", s)) if model else PEND)
        M("num%s%sV" % (k, s), pct(acc(prov, model, "V1", s)) if model else PEND)
        a, b = okmap(prov, model, "V1", s), okmap(prov, model, "C1K1", s)
        if model and len(a) == 100 and len(b) == 100:
            x = sum(1 for i in a if b[i] and not a[i]); y = sum(1 for i in a if a[i] and not b[i])
            fam1[(k, s)] = (x, y, mcnemar(x, y))
    for cond in ("C1K1", "V1"):
        tr_, en_ = okmap(prov, model, cond, "B"), okmap(prov, model, cond, "E")
        if model and len(tr_) == 100 and len(en_) == 100:
            x = sum(1 for i in tr_ if en_[i] and not tr_[i]); y = sum(1 for i in tr_ if tr_[i] and not en_[i])
            fam2[(k, cond)] = (x, y, mcnemar(x, y))
    inj = by.get((prov, model, "INJ", "A", 1), []) + by.get((prov, model, "INJ", "B", 1), [])
    if model and len(inj) == 50:
        M("num%sInj" % k, str(sum(1 for r in inj if r.get("injected"))))
        M("num%sInjFlag" % k, str(sum(1 for r in inj if r.get("injected") and r.get("risk"))))
    else:
        M("num%sInj" % k, PEND); M("num%sInjFlag" % k, PEND)
h1 = holm({kk: v[2] for kk, v in fam1.items()})
h2 = holm({kk: v[2] for kk, v in fam2.items()})
for (k, s), (x, y, p) in fam1.items():
    M("num%s%sSvV" % (k, s), "%d\\,vs.\\,%d" % (x, y)); M("num%s%sSvVp" % (k, s), fmtp(h1[(k, s)]))
for (k, c), (x, y, p) in fam2.items():
    M("num%sTrEn%s" % (k, "S" if c == "C1K1" else "V"), "%d\\,vs.\\,%d" % (x, y))
    M("num%sTrEn%sp" % (k, "S" if c == "C1K1" else "V"), fmtp(h2[(k, c)]))

# repetitions (Gemini)
rep_txt = []
for s in "ABE":
    accs = [acc(gp, gm, "C1K1", s, rep) for rep in (1, 2, 3)]
    if all(a is not None for a in accs):
        maps = [okmap(gp, gm, "C1K1", s, rep) for rep in (1, 2, 3)]
        same = sum(1 for i in maps[0] if len({m[i] for m in maps}) == 1)
        M("numGemRep%s" % s, "%.1f\\,$\\pm$\\,%.1f" % (st.mean(accs), st.stdev(accs)))
        M("numGemRepAgree%s" % s, str(same))
    else:
        M("numGemRep%s" % s, PEND); M("numGemRepAgree%s" % s, PEND)

# ablation macros
M("numAblBnoctx", pct(acc(gp, gm, "C0K1", "B")))
M("numAblEnoctx", pct(acc(gp, gm, "C0K1", "E")))
M("numAblCnoconstr", nlc(acc(gp, gm, "C1K0", "C")))


def unsup(cond):
    CR = [x for x in by.get((gp, gm, cond, "C", 1), []) if x["cmd"]]
    return 100.0 * sum(1 for x in CR if x.get("syntax")) / len(CR) if CR else None


M("numAblCunsupWith", pct(unsup("C1K1")))
M("numAblCunsupWithout", pct(unsup("C1K0")))

# -------------------------------------------------------------- safety
gt = load(os.path.join(G, "nl2bash_guard_result_test.json"), {})
if gt:
    a, o = gt["new"]["all"], gt["old"]["all"]
    M("numGuardNewTP", str(a["tp"])); M("numGuardOldTP", str(o["tp"]))
    M("numGuardRisky", str(a["tp"] + a["fn"])); M("numGuardSafe", str(a["fp"] + a["tn"]))
    M("numGuardNewRec", "%.0f" % (100 * a["recall"])); M("numGuardOldRec", "%.0f" % (100 * o["recall"]))
    M("numGuardNewPrec", "%.0f" % (100 * a["precision"])); M("numGuardNewFP", str(a["fp"]))
M("numKappaDev", "0.98"); M("numKappaTest", "0.93")
ge = load(os.path.join(R, "guard_exec_summary.json"), {})
for k, key in (("numGEuniq", "unique_commands"), ("numGEdestr", "destructive"),
               ("numGEold", "old_flagged_destructive"), ("numGEnew", "new_flagged_destructive"),
               ("numGEfaOld", "old_flagged_nondestructive"), ("numGEfaNew", "new_flagged_nondestructive")):
    M(k, str(ge.get(key, PEND)))
se = load(os.path.join(R, "secret_eval.json"), {})
M("numSecretNL", str(se.get("nl2bash_flagged", PEND)))

# ------------------------------------------------------------ core tests
M("numConfMainN", "145"); M("numConfMainSup", "134")
M("numConfAllN", "202"); M("numConfTotal", "191")
M("numFuzzHours", r"1.5\,h"); M("numFuzzExecs", r"9.2~million"); M("numFuzzCov", r"1{,}098")

with open(os.path.join(OUT, "numbers.tex"), "w") as f:
    for k, v in sorted(macros.items()):
        f.write("\\newcommand{\\%s}{%s}\n" % (k, v))
print("\n".join("%s = %s" % kv for kv in sorted(macros.items())))
