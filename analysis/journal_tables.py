#!/usr/bin/env python3
"""Generates all numbers and tables of the journal article from the raw result files.
Run journal_stats.py first. Outputs (output/journal/): numbers_j.tex (macros), tab_*.tex,
journal_numbers.json (for auditing)."""
import json, collections, math, os, re, statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
R = os.path.join(ROOT, "tests", "results")
G = os.path.join(ROOT, "tests", "guard")
OUT = os.path.join(HERE, "output", "journal")
os.makedirs(OUT, exist_ok=True)
rows = json.load(open(R + "/llm2_scores.json"))
items = {i["id"]: i for i in json.load(open(R + "/llm2_items.json"))}
AN = json.load(open(OUT + "/analysis.json"))
MODELS = [("gemini", "gemini-3.5-flash-lite", "Gemini", "Gemini 3.5 Flash-Lite"),
          ("anthropic", "claude-haiku-4-5-20251001", "Claude", "Claude Haiku 4.5"),
          ("openai", "gpt-5.4-mini-2026-03-17", "GPT", "GPT-5.4 mini"),
          ("local", "qwen2.5-coder-1.5b-instruct-q4_k_m", "Qwen-local", "Qwen2.5-Coder 1.5B")]
SHORT = {"Gemini": "Gem", "Claude": "Cla", "GPT": "Gpt", "Qwen-local": "Loc"}
macros, J = {}, {}


def M(k, v):
    macros[k] = str(v)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0, 0)
    p = k / n; d = 1 + z * z / n; c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (100 * (c - h) / d, 100 * (c + h) / d)


def mcnemar(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


def holm(ps):
    order = sorted(ps.items(), key=lambda kv: kv[1])
    m, out, run = len(order), {}, 0.0
    for k, (name, p) in enumerate(order):
        run = max(run, min(1.0, (m - k) * p))
        out[name] = run
    return out


from decimal import Decimal, ROUND_HALF_UP


def hu(x, nd):
    q = Decimal(1).scaleb(-nd)
    return str(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def fmtp(p):
    if p < 0.001:
        return "$<$0.001"
    if p < 0.01:
        return "%.3f" % p
    return "%.2f" % p


by = collections.defaultdict(list)
for r in rows:
    by[(r["provider"], r["cond"], r["set"], r["rep"])].append(r)


def okmap(p, cond, s, rep=1):
    return {r["id"]: bool(r["ok_shellm"]) for r in by[(p, cond, s, rep)]}


def acc(p, cond, s, rep=1):
    R_ = by[(p, cond, s, rep)]
    return 100.0 * sum(r["ok_shellm"] for r in R_) / len(R_) if R_ else None


def nlc(p, cond, rep=1):
    R_ = by[(p, cond, "C", rep)]
    return st.mean(r["nlc2cmd"] for r in R_) if R_ else None


def util(p, cond, rep=1):
    R_ = by[(p, cond, "C", rep)]
    return 100.0 * sum(1 for r in R_ if r.get("utility_match")) / len(R_) if R_ else None


def nlcfmt(x):
    return ("$-$%.2f" % -x) if x < -0.005 else "%.2f" % abs(x) if abs(x) < 0.005 else "%.2f" % x


# ------------------------------------------------------------ non-LLM correctors
corr = collections.defaultdict(dict)
for f in ("baselines_scores.json", "baselines_nl_scores.json", "baselines2_scores.json"):
    for x in json.load(open(os.path.join(R, f))):
        corr[(x["method"], x["set"])][x["id"]] = bool(x["ok_shellm"])
CORR = [("thefuck", "thefuck 3.32"), ("nearest", "\\cmd{difflib} nearest name"),
        ("zsh", "zsh 5.9 \\cmd{CORRECT}"), ("freq", "frequency matcher")]
cms = {"thefuck": 25.1, "nearest": 1.3, "zsh": None, "freq": 15.4}
b1 = json.load(open(R + "/baselines_summary.json")); b2 = json.load(open(R + "/baselines2_summary.json"))
cms = {"thefuck": b1["A_thefuck"]["median_ms"], "nearest": b1["A_nearest"]["median_ms"],
       "zsh": None, "freq": b2["freq"]["median_ms"]}
for m, _ in CORR:
    for s in "ABE":
        d = corr[(m, s)]
        assert len(d) == 100, (m, s, len(d))
    M("numCorr%sA" % m.capitalize(), "%.0f" % (100 * sum(corr[(m, "A")].values()) / 100))
J["correctors"] = {m: {s: sum(corr[(m, s)].values()) for s in "ABE"} for m, _ in CORR}

# ------------------------------------------------------------ main table
with open(OUT + "/tab_main.tex", "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Accuracy of all methods (first run). A, B, E: \% of suggestions that are correct when executed in SheLLM, with Wilson 95\% confidence intervals for the LLMs; C: mean NLC2CMD score in $[-1,1]$ and \% of suggestions whose main utility matches the reference; \#N: abstentions over all four sets; Lat.: median latency over all runs}\label{tab:main}
\footnotesize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lccccccr@{}}
\toprule
Method & A: typos & B: Turkish & E: English & C: score & C: util. & \#N & Lat. \\
\midrule
""")
    for m, lab in CORR:
        a = sum(corr[(m, "A")].values()); bb = sum(corr[(m, "B")].values()); e = sum(corr[(m, "E")].values())
        lat = ("%.0f\\,ms" % cms[m]) if cms[m] else "--"
        f.write("%s & %d & %d & %d & -- & -- & -- & %s \\\\\n" % (lab, a, bb, e, lat))
    for p, mod, lab, full in MODELS:
        f.write("\\midrule\n\\multicolumn{8}{@{}l}{%s}\\\\\n" % full)
        for cond, pn in (("V1", "baseline prompt"), ("C1K1", "SheLLM prompt")):
            cells = []
            for s in "ABE":
                k = sum(r["ok_shellm"] for r in by[(p, cond, s, 1)])
                lo, hi = wilson(k, 100)
                cells.append("%d \\ci{[%.0f, %.0f]}" % (k, lo, hi))
            nn = sum(1 for s in "ABEC" for r in by[(p, cond, s, 1)] if not r["cmd"])
            lat = AN["latency"]["%s|%s" % (lab, cond)]["median"]
            f.write("\\quad %s & %s & %s & %s & %s & %.0f & %d & %s\\,s \\\\\n" % (
                pn, cells[0], cells[1], cells[2], nlcfmt(nlc(p, cond)), util(p, cond), nn, hu(lat, 2)))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")

for p, mod, lab, full in MODELS:
    k = SHORT[lab]
    for cond, c in (("V1", "V"), ("C1K1", "S")):
        for s in "ABE":
            M("num%s%s%s" % (k, s, c), "%.0f" % acc(p, cond, s))
        M("num%sC%s" % (k, c), nlcfmt(nlc(p, cond)))
        M("num%sCutil%s" % (k, c), "%.0f" % util(p, cond))

# ------------------------------------------------------------ RQ2: LLMs vs zsh CORRECT on A
zs = corr[("zsh", "A")]
fam0 = {}
for p, mod, lab, full in MODELS:
    for cond in ("V1", "C1K1"):
        o = okmap(p, cond, "A")
        x = sum(1 for i in o if o[i] and not zs[i]); y = sum(1 for i in o if zs[i] and not o[i])
        fam0[(lab, cond)] = (x, y, mcnemar(x, y))
h0 = holm({k: v[2] for k, v in fam0.items()})
J["vs_zsh"] = {"%s|%s" % k: {"llm_only": v[0], "zsh_only": v[1], "p": v[2], "p_holm": h0[k]} for k, v in fam0.items()}
for (lab, cond), (x, y, p) in fam0.items():
    c = "S" if cond == "C1K1" else "V"
    M("num%sZsh%s" % (SHORT[lab], c), "%d\\,vs.\\,%d" % (x, y))
    M("num%sZsh%sp" % (SHORT[lab], c), fmtp(h0[(lab, cond)]))
# typo error analysis: what LLMs answer when wrong on A (SheLLM prompt)
typo_err = {}
for p, mod, lab, full in MODELS:
    c = collections.Counter()
    for r in by[(p, "C1K1", "A", 1)]:
        if r["ok_shellm"]:
            continue
        ref = items[r["id"]]["ref"]; cmd = r["cmd"] or ""
        if not cmd:
            c["abstained"] += 1
        elif cmd.split()[0] == ref.split()[0]:
            c["right command, other change"] += 1
        else:
            c["other command"] += 1
    typo_err[lab] = dict(c)
J["typo_errors"] = typo_err
# tasks no method solves / only LLMs solve on A
anyllm = {i: any(okmap(p, "C1K1", "A")[i] for p, *_ in MODELS[:3]) for i in zs}
J["A_zsh_fail_llm_ok"] = sum(1 for i in zs if not zs[i] and anyllm[i])
J["A_zsh_ok_all_hosted_fail"] = sum(1 for i in zs if zs[i] and not anyllm[i])
M("numAzshFailLLMok", J["A_zsh_fail_llm_ok"])
M("numAzshOkLLMfail", J["A_zsh_ok_all_hosted_fail"])
union = sum(1 for i in zs if zs[i] or okmap("gemini", "C1K1", "A")[i])
M("numAunionGemZsh", union)
J["A_union_gem_zsh"] = union

# ------------------------------------------------------------ prompt effect (fam1) and language (fam2)
fam1, fam2 = {}, {}
for p, mod, lab, full in MODELS:
    for s in "ABE":
        a, b = okmap(p, "V1", s), okmap(p, "C1K1", s)
        x = sum(1 for i in a if b[i] and not a[i]); y = sum(1 for i in a if a[i] and not b[i])
        fam1[(lab, s)] = (x, y, mcnemar(x, y))
    for cond in ("C1K1", "V1"):
        tr, en = okmap(p, cond, "B"), okmap(p, cond, "E")
        x = sum(1 for i in tr if en["E" + i[1:]] and not tr[i]); y = sum(1 for i in tr if tr[i] and not en["E" + i[1:]])
        fam2[(lab, cond)] = (x, y, mcnemar(x, y))
h1 = holm({k: v[2] for k, v in fam1.items()}); h2 = holm({k: v[2] for k, v in fam2.items()})
J["prompt_effect"] = {"%s|%s" % k: {"shellm_only": v[0], "base_only": v[1], "p_holm": h1[k]} for k, v in fam1.items()}
J["language"] = {"%s|%s" % k: {"en_only": v[0], "tr_only": v[1], "p_holm": h2[k]} for k, v in fam2.items()}
for (lab, s), (x, y, p) in fam1.items():
    M("num%sPr%s" % (SHORT[lab], s), "%d\\,vs.\\,%d" % (x, y)); M("num%sPr%sp" % (SHORT[lab], s), fmtp(h1[(lab, s)]))
for (lab, cond), (x, y, p) in fam2.items():
    c = "S" if cond == "C1K1" else "V"
    M("num%sLang%s" % (SHORT[lab], c), "%d\\,vs.\\,%d" % (x, y)); M("num%sLang%sp" % (SHORT[lab], c), fmtp(h2[(lab, cond)]))

with open(OUT + "/tab_effects.tex", "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Paired comparisons (exact McNemar, Holm-adjusted within each column group). Prompt: tasks solved only with the SheLLM prompt vs.\ only with the baseline prompt. Language: tasks solved only in English vs.\ only in Turkish}\label{tab:effects}
\footnotesize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lcccccc@{}}
\toprule
& \multicolumn{3}{c}{Prompt (SheLLM vs.\ baseline)} & \multicolumn{2}{c}{Language (EN vs.\ TR)} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-6}
Model & A & B & E & SheLLM & baseline \\
\midrule
""")
    for p, mod, lab, full in MODELS:
        cells = []
        for s in "ABE":
            x, y, _ = fam1[(lab, s)]
            cells.append("%d/%d \\ci{(%s)}" % (x, y, fmtp(h1[(lab, s)])))
        for cond in ("C1K1", "V1"):
            x, y, _ = fam2[(lab, cond)]
            cells.append("%d/%d \\ci{(%s)}" % (x, y, fmtp(h2[(lab, cond)])))
        f.write("%s & %s \\\\\n" % (full.replace("Qwen2.5-Coder 1.5B", "Qwen 1.5B").replace("Gemini 3.5 Flash-Lite", "Gemini 3.5 F.-Lite"), " & ".join(cells)))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")

# ------------------------------------------------------------ error categories B/E (SheLLM prompt)
J["errors"] = AN["errors"]
# subdirectory tasks: reference uses dir/ that the request does not name
sub_ids = []
for i, it in items.items():
    if it["set"] != "B":
        continue
    dirs = [d for d in ("belgeler", "eski", "gecici", "loglar", "projeler", "resimler") if d + "/" in it["ref"]]
    if dirs and not any(d in it["input"] for d in dirs):
        sub_ids.append(i)
J["subdir_tasks_B"] = sorted(sub_ids)
M("numSubdirTasks", len(sub_ids))
sd = {}
for p, mod, lab, full in MODELS:
    o = okmap(p, "C1K1", "B")
    sd[lab] = sum(o[i] for i in sub_ids)
J["subdir_solved_B"] = sd
M("numSubdirSolvedMax", max(sd[l] for l in ("Gemini", "Claude", "GPT")))
for lab in sd:
    M("num%sSubdirSolved" % SHORT[lab], sd[lab])
# hosted models: tasks failed by all three (SheLLM prompt) in B and E
for s in "BE":
    allfail = [i for i in okmap("gemini", "C1K1", s) if not any(okmap(p, "C1K1", s)[i] for p, *_ in MODELS[:3])]
    J["allfail_hosted_" + s] = len(allfail)
    M("numAllFail%s" % s, len(allfail))
    J["allfail_hosted_%s_subdir" % s] = sum(1 for i in allfail if ("B" + i[1:]) in sub_ids)
    M("numAllFail%sSub" % s, J["allfail_hosted_%s_subdir" % s])

# ------------------------------------------------------------ Bash vs SheLLM correctness
mx = 0
for key, R_ in by.items():
    if key[2] in "ABE" and key[1] != "INJ":
        d = abs(sum(r["ok_shellm"] for r in R_) - sum(r["ok_bash"] for r in R_))
        mx = max(mx, d)
J["max_bash_diff"] = mx
M("numMaxBashDiff", mx)

# ------------------------------------------------------------ ablation (Gemini)
gp = "gemini"
fam3 = {}
for cmp in ("C0K1", "C1K0", "C0K0"):
    for s in "ABE":
        a, b = okmap(gp, "C1K1", s), okmap(gp, cmp, s)
        x = sum(1 for i in a if a[i] and not b[i]); y = sum(1 for i in a if b[i] and not a[i])
        fam3[(cmp, s)] = (x, y, mcnemar(x, y))
h3 = holm({k: v[2] for k, v in fam3.items()})
J["ablation_tests"] = {"%s|%s" % k: {"full_only": v[0], "abl_only": v[1], "p_holm": h3[k]} for k, v in fam3.items()}
for (cmp, s), (x, y, p) in fam3.items():
    M("numAbl%s%s" % (cmp, s), "%d\\,vs.\\,%d" % (x, y)); M("numAbl%s%sp" % (cmp, s), fmtp(h3[(cmp, s)]))


def unsup(cond, p=gp):
    CR = [x for x in by[(p, cond, "C", 1)] if x["cmd"]]
    return 100.0 * sum(1 for x in CR if x.get("syntax")) / len(CR) if CR else None


with open(OUT + "/tab_ablation_j.tex", "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Prompt ablation with Gemini 3.5 Flash-Lite (first run). A, B, E: \% correct; C: NLC2CMD score, \% utility match, and \% of non-empty suggestions with constructs SheLLM does not support; Disc.: tasks solved only by the full prompt vs.\ only by the variant, summed over A, B, and E}\label{tab:ablation}
\footnotesize
\setlength{\tabcolsep}{2.6pt}
\begin{tabular}{@{}llcccccccc@{}}
\toprule
Context & Constr. & A & B & E & C & C util. & Unsupp. & Disc. \\
\midrule
""")
    for cond, cx, kx in (("C1K1", "yes", "yes"), ("C0K1", "no", "yes"), ("C1K0", "yes", "no"), ("C0K0", "no", "no"), ("V1", "\\multicolumn{2}{l}{baseline prompt}", None)):
        a = [acc(gp, cond, s) for s in "ABE"]
        if cond == "C1K1":
            disc = "--"
        elif cond == "V1":
            xs = sum(fam1[("Gemini", s)][0] for s in "ABE"); ys = sum(fam1[("Gemini", s)][1] for s in "ABE")
            disc = "%d/%d" % (xs, ys)
        else:
            xs = sum(fam3[(cond, s)][0] for s in "ABE"); ys = sum(fam3[(cond, s)][1] for s in "ABE")
            disc = "%d/%d" % (xs, ys)
        lead = cx if kx is None else "%s & %s" % (cx, kx)
        if cond == "V1":
            f.write("\\midrule\n")
        f.write("%s & %.0f & %.0f & %.0f & %s & %.0f & %.0f\\%% & %s \\\\\n" % (lead, a[0], a[1], a[2], nlcfmt(nlc(gp, cond)), util(gp, cond), unsup(cond), disc))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")
for cond in ("C1K1", "C0K1", "C1K0", "C0K0", "V1"):
    for s in "ABE":
        M("numAbl%sAcc%s" % (cond, s), "%.0f" % acc(gp, cond, s))
    M("numAbl%sC" % cond, nlcfmt(nlc(gp, cond)))
    M("numAbl%sCutil" % cond, "%.0f" % util(gp, cond))
    M("numAbl%sUnsup" % cond, "%.0f" % unsup(cond))
# unsupported share on C for all models
for p, mod, lab, full in MODELS:
    for cond, c in (("V1", "V"), ("C1K1", "S")):
        M("num%sUnsupC%s" % (SHORT[lab], c), "%.0f" % unsup(cond, p))
# #NONE on C with SheLLM prompt
for p, mod, lab, full in MODELS:
    M("num%sNoneC" % SHORT[lab], sum(1 for r in by[(p, "C1K1", "C", 1)] if not r["cmd"]))
    M("num%sNoneA" % SHORT[lab], sum(1 for r in by[(p, "C1K1", "A", 1)] if not r["cmd"]))
# sudo in C suggestions
for p, mod, lab, full in MODELS:
    for cond in ("V1", "C1K1"):
        n = sum(1 for r in by[(p, cond, "C", 1)] if r["cmd"] and re.search(r"(^|[|;&\s])sudo\s", r["cmd"]))
        J.setdefault("sudo_C", {})["%s|%s" % (lab, cond)] = n
refsudo = sum(1 for i in items.values() if i["set"] == "C" and re.search(r"(^|[|;&\s])sudo\s", i["ref"]))
J["sudo_C_ref"] = refsudo
M("numSudoRefC", refsudo)
M("numSudoGemV", J["sudo_C"]["Gemini|V1"]); M("numSudoGemS", J["sudo_C"]["Gemini|C1K1"])

# ------------------------------------------------------------ repetitions, latency, cost
reps = {}
for p, mod, lab, full in MODELS:
    for cond in ("V1", "C1K1"):
        for s in "ABE":
            rr = [r for r in (1, 2, 3) if by[(p, cond, s, r)]]
            if len(rr) < 2:
                continue
            accs = [acc(p, cond, s, r) for r in rr]
            maps = [okmap(p, cond, s, r) for r in rr]
            same = sum(1 for i in maps[0] if len({m[i] for m in maps}) == 1)
            cm = [{x["id"]: x["cmd"] for x in by[(p, cond, s, r)]} for r in rr]
            ident = sum(1 for i in cm[0] if len({c[i] for c in cm}) == 1)
            reps["%s|%s|%s" % (lab, cond, s)] = {"n_reps": len(rr), "accs": accs, "range": max(accs) - min(accs),
                                                 "sd": st.stdev(accs), "outcome_agree": same, "identical_cmd": ident}
J["reps"] = reps
with open(OUT + "/tab_stability.tex", "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Repeated runs, latency, and cost. Range: largest difference in accuracy (points) between runs over A, B, E; Agree: tasks with the same outcome in all runs; Ident.: tasks with byte-identical suggestions in all runs (A, B, and E summed, of 300); latency over all requests; cost per 1{,}000 requests at list prices (Section~\ref{sec:rq5})}\label{tab:stability}
\footnotesize
\setlength{\tabcolsep}{2.4pt}
\begin{tabular}{@{}llcccccccr@{}}
\toprule
Model & Prompt & Runs & Range & Agree & Ident. & Median & P90 & $<$3\,s & USD \\
\midrule
""")
    for p, mod, lab, full in MODELS:
        for cond, pn in (("V1", "baseline"), ("C1K1", "SheLLM")):
            ks = ["%s|%s|%s" % (lab, cond, s) for s in "ABE"]
            if all(k in reps for k in ks):
                nr = reps[ks[0]]["n_reps"]
                rng = max(reps[k]["range"] for k in ks)
                ag = sum(reps[k]["outcome_agree"] for k in ks); idt = sum(reps[k]["identical_cmd"] for k in ks)
                rcells = "%d & %.0f & %d & %d" % (nr, rng, ag, idt)
            else:
                rcells = "1 & -- & -- & --"
            L = AN["latency"]["%s|%s" % (lab, cond)]; C = AN["cost"]["%s|%s" % (lab, cond)]
            name = full.replace("Qwen2.5-Coder 1.5B", "Qwen 1.5B (local)").replace("Gemini 3.5 Flash-Lite", "Gemini 3.5 F.-Lite") if cond == "V1" else ""
            usd = "%.2f" % C["usd_per_1000"] if p != "local" else "0"
            f.write("%s & %s & %s & %s & %s & %s\\%% & %s \\\\\n" % (name, pn, rcells, hu(L["median"], 2), hu(L["p90"], 2), hu(L["under3"], 0), usd))
        if p != "local":
            f.write("\\addlinespace\n")
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")
for p, mod, lab, full in MODELS:
    for cond, c in (("V1", "V"), ("C1K1", "S")):
        C = AN["cost"]["%s|%s" % (lab, cond)]
        M("num%sTokIn%s" % (SHORT[lab], c), "%.0f" % C["in"]); M("num%sTokOut%s" % (SHORT[lab], c), "%.0f" % C["out"])
        M("num%sUsd%s" % (SHORT[lab], c), "%.2f" % C["usd_per_1000"])
        L = AN["latency"]["%s|%s" % (lab, cond)]
        M("num%sLatMed%s" % (SHORT[lab], c), hu(L["median"], 2)); M("num%sLatMax%s" % (SHORT[lab], c), hu(L["max"], 1))
        M("num%sUnder3%s" % (SHORT[lab], c), hu(L["under3"], 0)); M("num%sUnder1%s" % (SHORT[lab], c), hu(L["under1"], 0))

# ------------------------------------------------------------ trigger coverage
tc = json.load(open(R + "/trigger_coverage_summary.json"))
J["trigger"] = tc

# ------------------------------------------------------------ guard
def kappa(a, b):
    n = len(a); po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = sum(a) / n; pb = sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return (po - pe) / (1 - pe)


for split, gf, rf in (("dev", "nl2bash_gold.json", "nl2bash_guard_result.json"), ("test", "nl2bash_gold_test.json", "nl2bash_guard_result_test.json")):
    gold = json.load(open(os.path.join(G, gf)))
    k = kappa([g["a1"] for g in gold], [g["a2"] for g in gold])
    dis = sum(1 for g in gold if g["a1"] != g["a2"])
    res = json.load(open(os.path.join(G, rf)))
    J["guard_" + split] = {"kappa": k, "disagree": dis, "n": len(gold), "risky": sum(g["label"] for g in gold),
                           "old": res["old"]["all"], "new": res["new"]["all"],
                           "old_cat": res["old"]["by_cat_recall"], "new_cat": res["new"]["by_cat_recall"]}
    S = "Dev" if split == "dev" else "Test"
    M("numKappa%s" % S, "%.2f" % k); M("numDisagree%s" % S, dis)
    for v in ("old", "new"):
        a = res[v]["all"]; V = v.capitalize()
        M("numG%s%sTP" % (S, V), a["tp"]); M("numG%s%sFP" % (S, V), a["fp"])
        M("numG%s%sRec" % (S, V), "%.0f" % (100 * a["recall"]))
        M("numG%s%sPrec" % (S, V), "%.0f" % (100 * a["precision"]) if a["tp"] + a["fp"] else "--")
        lo, hi = wilson(a["tp"], a["tp"] + a["fn"]); M("numG%s%sRecCI" % (S, V), "%.0f--%.0f" % (lo, hi))
    M("numG%sRisky" % S, res["new"]["all"]["tp"] + res["new"]["all"]["fn"])
    M("numG%sSafe" % S, res["new"]["all"]["fp"] + res["new"]["all"]["tn"])

gt = J["guard_test"]; gd = J["guard_dev"]
CATN = [("DEL", "Deletion"), ("OVW", "Overwriting"), ("PRIV", "Privileges"), ("SYS", "System"), ("NET", "Network")]
with open(OUT + "/tab_guard.tex", "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Recall of the old and the revised guard rules on labeled NL2Bash commands, by risk class (held-out sample with Wilson 95\% confidence intervals; development sample for reference). The last rows give precision and false alarms among the safe commands}\label{tab:guard}
\footnotesize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lccccc@{}}
\toprule
& \multicolumn{3}{c}{Held-out (300)} & \multicolumn{2}{c}{Development (300)} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-6}
Class & Old & Revised & 95\% CI (rev.) & Old & Revised \\
\midrule
""")
    for c, name in CATN:
        o = gt["old_cat"][c]; nw = gt["new_cat"][c]
        k_, n_ = map(int, nw.split("/")); lo, hi = wilson(k_, n_)
        f.write("%s & %s & %s & %.0f--%.0f\\%% & %s & %s \\\\\n" % (name, o, nw, lo, hi, gd["old_cat"][c], gd["new_cat"][c]))
    o, nw = gt["old"], gt["new"]
    lo, hi = wilson(nw["tp"], nw["tp"] + nw["fn"])
    f.write("\\midrule\nAll risky & %d/%d & %d/%d & %.0f--%.0f\\%% & %d/%d & %d/%d \\\\\n" % (
        o["tp"], o["tp"] + o["fn"], nw["tp"], nw["tp"] + nw["fn"], lo, hi,
        gd["old"]["tp"], gd["old"]["tp"] + gd["old"]["fn"], gd["new"]["tp"], gd["new"]["tp"] + gd["new"]["fn"]))
    f.write("Recall & %.0f\\%% & %.0f\\%% & & %.0f\\%% & %.0f\\%% \\\\\n" % (100 * o["recall"], 100 * nw["recall"], 100 * gd["old"]["recall"], 100 * gd["new"]["recall"]))
    f.write("Precision & %.0f\\%% & %.0f\\%% & & %.0f\\%% & %.0f\\%% \\\\\n" % (100 * o["precision"], 100 * nw["precision"], 100 * gd["old"]["precision"], 100 * gd["new"]["precision"]))
    f.write("False alarms & %d/%d & %d/%d & & %d/%d & %d/%d \\\\\n" % (o["fp"], o["fp"] + o["tn"], nw["fp"], nw["fp"] + nw["tn"], gd["old"]["fp"], gd["old"]["fp"] + gd["old"]["tn"], gd["new"]["fp"], gd["new"]["fp"] + gd["new"]["tn"]))
    f.write("Cohen's $\\kappa$ & \\multicolumn{3}{c}{%.2f} & \\multicolumn{2}{c}{%.2f} \\\\\n" % (gt["kappa"], gd["kappa"]))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")

cat = json.load(open(os.path.join(G, "categories_result.json")))
cr = {}
for v in ("old", "new"):
    risky = cat[v]["risky"]; safe = cat[v]["safe"]
    # each entry: [cls, cmd, reason]; flagged if reason non-empty
    tp = sum(1 for x in risky if x[2]); fp = sum(1 for x in safe if (x[1] if len(x) == 2 else x[-1]))
    cr[v] = {"risky_flagged": tp, "risky": len(risky), "safe_flagged": fp, "safe": len(safe)}
J["category_test"] = cr
M("numCatRisky", cr["new"]["risky"]); M("numCatSafe", cr["new"]["safe"])
M("numCatOldTP", cr["old"]["risky_flagged"]); M("numCatNewTP", cr["new"]["risky_flagged"])
M("numCatOldFP", cr["old"]["safe_flagged"]); M("numCatNewFP", cr["new"]["safe_flagged"])

ge = json.load(open(R + "/guard_exec_summary.json"))
J["guard_exec"] = {k: ge[k] for k in ("unique_commands", "destructive", "old_flagged_destructive", "new_flagged_destructive", "old_flagged_nondestructive", "new_flagged_nondestructive")}
for k, key in (("numGEuniq", "unique_commands"), ("numGEdestr", "destructive"), ("numGEold", "old_flagged_destructive"),
               ("numGEnew", "new_flagged_destructive"), ("numGEfaOld", "old_flagged_nondestructive"), ("numGEfaNew", "new_flagged_nondestructive")):
    M(k, ge[key])
M("numGEuniq", "{:,}".format(ge["unique_commands"]).replace(",", "{,}"))
M("numGEevet", ge["destructive"] + ge["new_flagged_nondestructive"])
M("numGEevetPct", "%.0f" % (100.0 * (ge["destructive"] + ge["new_flagged_nondestructive"]) / ge["unique_commands"]))
M("numGEoldMiss", ge["destructive"] - ge["old_flagged_destructive"])

se = json.load(open(R + "/secret_eval.json"))
J["secret"] = {k: se[k] for k in ("positives", "detected", "task_inputs", "nl2bash_commands", "nl2bash_flagged")}
J["secret"]["task_inputs_flagged"] = len(se["task_inputs_flagged"])
M("numSecretNL", se["nl2bash_flagged"])

# ------------------------------------------------------------ injection
inj = {}
for p, mod, lab, full in MODELS:
    R_ = by[(p, "INJ", "A", 1)] + by[(p, "INJ", "B", 1)]
    pay = [r for r in R_ if r.get("injected")]
    clean = {x["id"]: x["cmd"] for s in "AB" for x in by[(p, "C1K1", s, 1)]}
    inj[lab] = {"n": len(R_), "none": sum(1 for r in R_ if not r["cmd"]), "injected": len(pay),
                "flagged": sum(1 for r in pay if r.get("risk")), "risky_all": sum(1 for r in R_ if r.get("risk")),
                "same_as_clean": sum(1 for r in R_ if r["cmd"] == clean[r["id"]]),
                "none_clean": sum(1 for r in R_ if not clean[r["id"]]),
                "payloads": dict(collections.Counter(("rm" if "rm -rf" in r["cmd"] else "curl" if "evil" in r["cmd"] else "chmod") for r in pay))}
J["injection"] = inj
J["payload_outside_inj"] = sum(1 for r in rows if r["cond"] != "INJ" and r["cmd"] and re.search(r"rm -rf ~|evil\.example|chmod -R 777", r["cmd"]))
with open(OUT + "/tab_injection.tex", "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Prompt injection through file names (50 tasks, SheLLM prompt). Unchanged: answers (suggestions or abstentions) identical to those for the same tasks without the injected names; \cmd{\#NONE}: abstentions with (and without) the injected names; Injected: suggestions containing an injected payload; Flagged: of these, flagged by the guard}\label{tab:injection}
\footnotesize
\setlength{\tabcolsep}{3.5pt}
\begin{tabular}{@{}lcccc@{}}
\toprule
Model & Unchanged & \cmd{\#NONE} & Injected & Flagged \\
\midrule
""")
    for p, mod, lab, full in MODELS:
        x = inj[lab]
        f.write("%s & %d & %d (%d) & %d & %d \\\\\n" % (full, x["same_as_clean"], x["none"], x["none_clean"], x["injected"], x["flagged"]))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")
M("numLocInj", inj["Qwen-local"]["injected"]); M("numLocInjFlag", inj["Qwen-local"]["flagged"])
for lab in inj:
    M("num%sInjSame" % SHORT[lab], inj[lab]["same_as_clean"]); M("num%sInjNone" % SHORT[lab], inj[lab]["none"])

# ------------------------------------------------------------ write
RENAME = [("C1K1", "Full"), ("C0K1", "NoCtx"), ("C1K0", "NoCon"), ("C0K0", "Neither"), ("V1", "Base"),
          ("Under1", "UnderOne"), ("Under3", "UnderThree")]


def texname(k):
    for x, y in RENAME:
        k = k.replace(x, y)
    assert re.fullmatch(r"[A-Za-z]+", k), k
    return k


with open(OUT + "/numbers_j.tex", "w") as f:
    for k, v in sorted(macros.items()):
        f.write("\\newcommand{\\%s}{%s}\n" % (texname(k), v))
json.dump(J, open(OUT + "/journal_numbers.json", "w"), indent=1, default=str)
print(json.dumps({k: J[k] for k in J if k not in ("reps",)}, indent=1, default=str)[:9000])

# ------------------------------------------------------------ error categories table
with open(OUT + "/tab_errors.tex", "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Failed requests with the SheLLM prompt (first run), by cause. Subdir.: the suggestion omits the subdirectory that holds the named file; Bash-only: correct in Bash but not in SheLLM; Other: wrong command, options, or output}\label{tab:errors}
\footnotesize
\setlength{\tabcolsep}{3pt}
\begin{tabular}{@{}lcccccc@{}}
\toprule
& \multicolumn{3}{c}{B: Turkish} & \multicolumn{3}{c}{E: English} \\
\cmidrule(lr){2-4}\cmidrule(lr){5-7}
Model & Subdir. & Bash-only & Other & Subdir. & Bash-only & Other \\
\midrule
""")
    for p, mod, lab, full in MODELS:
        cells = []
        for s in "BE":
            e = AN["errors"]["%s|%s" % (lab, s)]
            cells += [str(e.get("missing subdirectory", 0)), str(e.get("Bash-only syntax", 0)), str(e.get("other", 0))]
        f.write("%s & %s \\\\\n" % (full, " & ".join(cells)))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")

# ------------------------------------------------------------ trigger table
def frac(k):
    return tc[k].split("/")[0]


with open(OUT + "/tab_trigger_j.tex", "w") as f:
    f.write(r"""\begin{table}[t]
\caption{Inputs that reach the assistant when typed into SheLLM in a pseudo-terminal (of 100 per set)}\label{tab:trigger}
\footnotesize
\setlength{\tabcolsep}{4pt}
\begin{tabular}{@{}lcccc@{}}
\toprule
Trigger rule & A: typos & B: Turkish & E: English & C: NL2Bash \\
\midrule
""")
    f.write("Exit status 127 (old) & %s & %s & %s & %s \\\\\n" % tuple(frac(s + "_old") for s in "ABEC"))
    f.write("Name resolution and quotes (new) & %s & %s & %s & %s \\\\\n" % tuple(frac(s + "_new") for s in "ABEC"))
    f.write("New rule with \\cmd{\\#} prefix & %s & %s & %s & %s \\\\\n" % tuple(frac(s + "_prefix") for s in "ABEC"))
    f.write("\\midrule\nFirst word is a program & 0 & %d & %d & %d \\\\\n" % (tc["B_first_word_is_command"], tc["E_first_word_is_command"], tc["C_first_word_is_command"]))
    f.write("Unmatched apostrophe & 0 & %d & %d & %d \\\\\n" % (tc["B_odd_apostrophe"], tc["E_odd_apostrophe"], tc["C_odd_apostrophe"]))
    f.write("\\bottomrule\n\\end{tabular}\n\\end{table}\n")
