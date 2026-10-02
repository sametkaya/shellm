#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E6 — Evaluation of language model suggestions (real Gemini API).

Phases (run in order; each phase writes its results under results/):
  prepare  generates the tasks; for sets A and B runs the reference commands
           in Bash and records the expected results      -> llm_items.json
  query    asks the model with two prompts per task (v1 prompt, v2 prompt);
           resumes where it left off after an interruption -> llm_responses.jsonl
  score    runs the suggestions in SheLLM v2 and in Bash, each time in a
           freshly built experiment directory; functional correctness for A/B,
           NLC2CMD score for C; plus syntax and risk checks -> llm_scores.json
  summary  prints the summary tables                       -> llm_summary.json

Requirements: root privileges (suggestions are run under the unprivileged
'kullanici' account), GEMINI_API_KEY (query only), bashlex (pip), the SheLLM v2
binary. Model: SHELLM_MODEL (default gemini-flash-lite-latest).
"""
import argparse
import collections
import itertools
import json
import os
import pwd
import random
import re
import shlex
import statistics as st
import subprocess
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import V2_DIR, V2_BIN, RESULTS, NL2BASH_CM  # noqa: E402
import llm_fixture as fx  # noqa: E402
import llm_tasks  # noqa: E402

sys.path.insert(0, V2_DIR)
os.environ.setdefault("SHELLM_MODEL", "gemini-flash-lite-latest")
import ai_helper  # noqa: E402  (source of the v2 prompt, context and reply cleaning)

MODEL = ai_helper.MODEL
ITEMS = os.path.join(RESULTS, "llm_items.json")
RESP = os.path.join(RESULTS, "llm_responses.jsonl")
SCORES = os.path.join(RESULTS, "llm_scores.json")
SUMMARY = os.path.join(RESULTS, "llm_summary.json")
EVAL_USER = "kullanici"                               # unprivileged account ("user")
RUNUSER = __import__("shutil").which("runuser") or "/usr/sbin/runuser"
SHELLM_EXEC = os.environ.get("SHELLM_EVAL_BIN", "/usr/local/bin/shellm_v2_eval")
CM_PATH = NL2BASH_CM                                   # NL2Bash commands (all.cm)
NL_PATH = os.path.join(os.path.dirname(CM_PATH), "all.nl")  # descriptions in the same directory

V1_PROMPT = ("You are a Linux Terminal Assistant. The user typed '{inp}' and got "
             "'command not found'. Suggest ONLY the correct bash command. "
             "No explanation, no markdown.")


# ================================================================= execution
def _user():
    p = pwd.getpwnam(EVAL_USER)
    return p.pw_uid, p.pw_gid


def _limits():
    import resource
    resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
    resource.setrlimit(resource.RLIMIT_FSIZE, (50 << 20, 50 << 20))
    os.setsid()


def execute(shell, cmd, probe=None, timeout=10):
    """Runs cmd (and the probe command, if any) as the unprivileged user in a
    fresh experiment directory; returns stdout, exit status and a file system snapshot."""
    uid, gid = _user()
    fx.create(uid, gid)
    script = cmd + "\n" + (probe + "\n" if probe else "")
    argv = ([SHELLM_EXEC] if shell == "shellm" else ["bash", "--norc", "--noprofile"])
    env = {"HOME": fx.HOME, "PATH": "/usr/local/bin:/usr/bin:/bin", "USER": EVAL_USER,
           "LOGNAME": EVAL_USER, "LC_ALL": "C.UTF-8", "TERM": "dumb", "SHELLM_AI": "0"}
    full = [RUNUSER, "-u", EVAL_USER, "--"] + argv
    import tempfile
    with tempfile.TemporaryFile() as fo:    # output goes to a file: unbounded output
        try:                                 # (e.g. yes) cannot exhaust memory; RLIMIT_FSIZE cuts it off
            p = subprocess.run(full, input=script.encode(), cwd=fx.LAB, env=env,
                               stdout=fo, stderr=subprocess.DEVNULL, timeout=timeout,
                               preexec_fn=_limits)
            rc, to = p.returncode, False
        except subprocess.TimeoutExpired:
            subprocess.run(["pkill", "-9", "-u", EVAL_USER], capture_output=True)
            rc, to = None, True
        fo.seek(0)
        out = fo.read(1 << 20).decode("utf-8", "replace")
    subprocess.run(["pkill", "-9", "-u", EVAL_USER], capture_output=True)
    snap = json.loads(json.dumps(fx.snapshot(fx.HOME)))   # same form as after a JSON round trip, so comparable
    return {"out": out, "rc": rc, "timeout": to, "fs": snap}


# ============================================================= normalization
NAMES = None


def _names():
    global NAMES
    if NAMES is None:
        fx.create()
        NAMES = fx.names(fx.HOME)
    return NAMES


def _lines(s):
    ls = [l.rstrip() for l in s.split("\n")]
    while ls and not ls[-1]:
        ls.pop()
    return ls


GREP_PREFIX = re.compile(r"^(?:\./)?(?:[\w.\-]+/)*[\w.\-]+\.(?:log|c|h|py|txt|csv|md|1):|^(?:\./)?(?:[\w.\-]+/)*Makefile:")
LINENO = re.compile(r"^\d+:")


def normalize(kind, out, ref_out=None):
    if kind in (None, "pwd"):
        ls = [l for l in _lines(out) if l.strip()]
        return ls[-1] if (kind == "pwd" and ls) else None
    if kind == "text":
        return _lines(out)
    if kind == "ws":
        return " ".join(out.split())
    if kind == "lines":
        return _lines(out)
    if kind == "lines_nonempty":
        return [l for l in _lines(out) if l.strip()]
    if kind == "lines_nohdr":
        return [l for l in _lines(out) if l.strip() and l.strip() != "ad,sehir,yas"]
    if kind == "set":   # the CSV header (ad,sehir,yas / sehir) is left out of the result
        return sorted({l.strip() for l in out.split("\n") if l.strip()} - {"ad,sehir,yas", "sehir"})
    if kind == "ws_set":
        return sorted({" ".join(l.split()) for l in out.split("\n") if l.strip()})
    if kind == "names":
        toks = set()
        for t in out.split():
            t = t.strip("'\"`,;:*@/").rstrip("/")
            b = os.path.basename(t)
            if b in _names():
                toks.add(b)
        return sorted(toks)
    if kind == "grep":
        res = set()
        for l in out.split("\n"):
            if not l.strip():
                continue
            l = GREP_PREFIX.sub("", l, count=1)
            l = LINENO.sub("", l, count=1)
            res.add(l.strip())
        return sorted(res)
    if kind == "diff":
        res = set()
        for l in out.split("\n"):
            if l.startswith(("+++", "---", "@@")):
                continue
            if l[:1] in "<>+-" and l[:1]:
                res.add(l[1:].strip())
        return sorted(res)
    if kind == "int":
        return re.findall(r"(?<![\w.])-?\d+(?![\w.])", out), len([l for l in out.split("\n") if l.strip()])
    raise ValueError(kind)


def output_ok(kind, cand_out, ref_out):
    if kind is None:
        return True
    if kind.startswith("contains:"):
        return kind.split(":", 1)[1] in cand_out
    if kind == "int":
        exp = re.findall(r"-?\d+", ref_out)[0]
        nums, nlines = normalize("int", cand_out)
        return exp in nums and nlines <= 2
    return normalize(kind, cand_out) == normalize(kind, ref_out)


def judge(item, ref, cand):
    if cand is None:
        return False
    return (not cand["timeout"]) and cand["fs"] == ref["fs"] and \
        output_ok(item["check"], cand["out"], ref["out"])


# ================================================================ NLC2CMD score
def _utilities(cmd):
    """List of (utility, set of flags); parsed with bashlex, falling back to shlex."""
    try:
        import bashlex
        trees = bashlex.parse(cmd)
        out = []

        class V(bashlex.ast.nodevisitor):
            def visitcommand(self, node, parts):
                words = [p.word for p in parts if p.kind == "word"]
                words = [w for w in words if not re.match(r"^\w+=", w)] or words
                if words:
                    util = os.path.basename(words[0]).lower()
                    flags = {w.split("=", 1)[0] for w in words[1:] if w.startswith("-") and w not in ("-", "--")}
                    out.append((util, flags))
        for t in trees:
            V().visit(t)
        return out
    except Exception:
        out = []
        for seg in re.split(r"\|\||&&|[|;]", cmd):
            try:
                w = shlex.split(seg)
            except ValueError:
                w = seg.split()
            if w:
                out.append((os.path.basename(w[0]).lower(),
                            {x.split("=", 1)[0] for x in w[1:] if x.startswith("-")}))
        return out


def nlc2cmd_score(pred, ref):
    """NLC2CMD competition metric (confidence = 1), in the range [-1, 1]."""
    if not pred:
        return 0.0
    up, ur = _utilities(pred), _utilities(ref)
    scores = []
    for a, b in itertools.zip_longest(ur, up):
        if a is None or b is None or a[0] != b[0]:
            scores.append(-1.0)
            continue
        fr, fp = a[1], b[1]
        if not fr and not fp:
            fs = 1.0
        else:
            z = max(1, len(fp), len(fr))
            fs = (2 * len(fr & fp) - len(fr | fp)) / z
        scores.append(0.5 * (1 + fs))
    return sum(scores) / len(scores) if scores else 0.0


# ===================================================================== checks
def check(cmd):
    """SheLLM v2 --check: (risk reason, syntax issue)."""
    p = subprocess.run([V2_BIN, "--check", cmd], capture_output=True, text=True, timeout=5)
    risk = syn = ""
    for line in p.stdout.splitlines():
        k, _, v = line.partition("\t")
        v = "" if v.strip() == "-" else v.strip()      # "-" = no issue
        if k == "risk":
            risk = v
        elif k == "syntax":
            syn = v
    return risk, syn


def first_word_is_command(inp):
    w = inp.strip().split()
    return bool(w) and llm_tasks._is_command(w[0])


# ===================================================================== phases
def prepare():
    items = llm_tasks.build_all(NL_PATH, CM_PATH)
    bad = []
    for it in items:
        it["first_word_is_command"] = first_word_is_command(it["input"])
        if it["set"] == "C":
            it["ref_syntax"] = check(it["ref"])[1]
            continue
        r = execute("bash", it["ref"], it.get("probe"))
        it["ref_result"] = {"out": r["out"], "rc": r["rc"], "fs": r["fs"]}
        empty = it["check"] not in (None, "pwd") and not r["out"].strip()
        if r["rc"] not in (0, 1) or r["timeout"] or empty:
            bad.append((it["id"], it["ref"], r["rc"], r["out"][:80]))
        # the reference command should give the same result in SheLLM v2 too (syntax coverage)
        s = execute("shellm", it["ref"], it.get("probe"))
        it["ref_ok_in_shellm"] = judge(it, r, s)
    json.dump(items, open(ITEMS, "w"), ensure_ascii=False, indent=1)
    print("tasks:", collections.Counter(i["set"] for i in items))
    print("reference problems:", bad)
    print("tasks whose reference does not run correctly in SheLLM:",
          [i["id"] for i in items if i["set"] != "C" and not i["ref_ok_in_shellm"]])


class DailyQuota(Exception):
    pass


def call_gemini(system, text, max_attempts=6):
    key = os.environ.get("GEMINI_API_KEY")
    body = {"contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    url = "%s/models/%s:generateContent" % (ai_helper.BASE_URL, MODEL)
    data = json.dumps(body).encode("utf-8")
    attempts, waits = [], [2, 4, 8, 16, 30]
    n = 0
    while n < max_attempts:
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json", "x-goog-api-key": key})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            dt = time.perf_counter() - t0
            attempts.append({"code": 200, "t": round(dt, 3)})
            parts = d["candidates"][0]["content"]["parts"]
            txt = "".join(p.get("text", "") for p in parts)
            return {"status": "OK", "raw": txt, "attempts": attempts,
                    "modelVersion": d.get("modelVersion"), "usage": d.get("usageMetadata")}
        except urllib.error.HTTPError as e:
            dt = time.perf_counter() - t0
            try:
                err = json.loads(e.read().decode("utf-8"))
            except Exception:
                err = {}
            attempts.append({"code": e.code, "t": round(dt, 3)})
            if e.code == 429:
                msg = json.dumps(err)
                if "PerDay" in msg:
                    raise DailyQuota(msg[:300])
                m = re.search(r'"retryDelay":\s*"(\d+)', msg)
                time.sleep(int(m.group(1)) + 1 if m else 15)
                continue          # per-minute quota: not counted as an attempt
            if e.code not in (500, 502, 503, 504):
                return {"status": "ERR", "raw": "HTTP %d" % e.code, "attempts": attempts}
        except (KeyError, IndexError, TypeError):
            # "raw" error texts are stored in llm_responses.jsonl, so they stay in
            return {"status": "ERR", "raw": "unexpected response", "attempts": attempts}
        except Exception as e:
            attempts.append({"code": type(e).__name__, "t": round(time.perf_counter() - t0, 3)})
        n += 1
        if n < max_attempts:
            time.sleep(waits[min(n - 1, len(waits) - 1)])
    return {"status": "ERR", "raw": "retries exhausted", "attempts": attempts}


def query(limit=None):
    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set")
    items = json.load(open(ITEMS))
    done = set()
    if os.path.exists(RESP):
        for l in open(RESP):
            r = json.loads(l)
            if r["status"] == "OK":
                done.add((r["id"], r["prompt"]))
    order = items[:]
    random.Random(7).shuffle(order)
    fx.create()                     # the v2 prompt's context is read from this directory
    n = 0
    with open(RESP, "a") as f:
        for it in order:
            prompts = ["v2", "v1"] if int(it["id"][1:]) % 2 else ["v1", "v2"]
            for pr in prompts:
                if (it["id"], pr) in done:
                    continue
                if limit is not None and n >= limit:
                    return
                if pr == "v2":
                    req = {"input": it["input"], "cwd": fx.LAB, "exit_code": 127}
                    res = call_gemini(ai_helper.SYSTEM_PROMPT, ai_helper.user_message(req))
                else:
                    res = call_gemini(None, V1_PROMPT.format(inp=it["input"]))
                res["cmd"] = ai_helper.clean_reply(res["raw"]) if res["status"] == "OK" else None
                res.update({"id": it["id"], "prompt": pr, "time": time.strftime("%Y-%m-%dT%H:%M:%S")})
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
                f.flush()
                n += 1
                print(it["id"], pr, res["status"], repr(res.get("cmd"))[:70],
                      [a["code"] for a in res["attempts"]], flush=True)
                time.sleep(1.0)


def load_responses():
    last = {}
    for l in open(RESP):
        r = json.loads(l)
        k = (r["id"], r["prompt"])
        if k not in last or r["status"] == "OK":
            last[k] = r
    return last


def score():
    items = {i["id"]: i for i in json.load(open(ITEMS))}
    resp = load_responses()
    out = []
    for (iid, pr), r in sorted(resp.items()):
        it = items[iid]
        cmd = r.get("cmd")
        row = {"id": iid, "set": it["set"], "prompt": pr, "cmd": cmd, "status": r["status"],
               "raw_multiline": bool(r.get("raw")) and len([x for x in r["raw"].strip().splitlines() if x.strip()]) > 1,
               "raw_fence": "```" in (r.get("raw") or "")}
        if cmd:
            row["risk"], row["syntax"] = check(cmd)
        if it["set"] == "C":
            row["nlc2cmd"] = nlc2cmd_score(cmd, it["ref"])
            row["utility_match"] = bool(cmd) and bool(_utilities(cmd)) and \
                _utilities(cmd)[0][0] == (_utilities(it["ref"]) or [("", set())])[0][0]
        else:
            ref = it["ref_result"]
            ref["timeout"] = False
            if cmd:
                cs = execute("shellm", cmd, it.get("probe"))
                cb = execute("bash", cmd, it.get("probe"))
                row["ok_shellm"] = judge(it, ref, cs)
                row["ok_bash"] = judge(it, ref, cb)
                row["exact"] = " ".join(cmd.split()) == " ".join(it["ref"].split())
            else:
                row["ok_shellm"] = row["ok_bash"] = row["exact"] = False
        out.append(row)
        print(iid, pr, row.get("ok_shellm", row.get("nlc2cmd")), repr(cmd)[:60], flush=True)
    json.dump(out, open(SCORES, "w"), ensure_ascii=False, indent=1)


def _pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def summary():
    items = {i["id"]: i for i in json.load(open(ITEMS))}
    rows = json.load(open(SCORES))
    resp = load_responses()
    # only tasks answered under both prompts (paired comparison)
    by = collections.defaultdict(set)
    for r in rows:
        by[r["id"]].add(r["prompt"])
    complete = {i for i, ps in by.items() if ps == {"v1", "v2"}}
    rows = [r for r in rows if r["id"] in complete]
    items = {i: v for i, v in items.items() if i in complete}
    res = {"model": MODEL, "complete_items": len(complete), "model_versions": sorted({r.get("modelVersion") for r in resp.values() if r.get("modelVersion")}),
           "sets": {}, "latency": {}}
    for s in "ABC":
        for pr in ("v1", "v2"):
            R = [r for r in rows if r["set"] == s and r["prompt"] == pr]
            n = len(R)
            d = {"n": n,
                 "none": sum(1 for r in R if not r["cmd"]),
                 "syntax_ok": _pct(sum(1 for r in R if r["cmd"] and not r.get("syntax")), n),
                 "risky": _pct(sum(1 for r in R if r.get("risk")), n),
                 "multiline": sum(1 for r in R if r["raw_multiline"]),
                 "fence": sum(1 for r in R if r["raw_fence"])}
            if s == "C":
                d["nlc2cmd_mean"] = round(st.mean(r["nlc2cmd"] for r in R), 3) if R else None
                d["utility_match"] = _pct(sum(1 for r in R if r["utility_match"]), n)
            else:
                d["acc_shellm"] = _pct(sum(1 for r in R if r["ok_shellm"]), n)
                d["acc_bash"] = _pct(sum(1 for r in R if r["ok_bash"]), n)
                d["exact"] = _pct(sum(1 for r in R if r["exact"]), n)
            res["sets"]["%s_%s" % (s, pr)] = d
        if s != "C":
            ids = [i for i in items if items[i]["set"] == s]
            res["sets"][s + "_ref_ok_in_shellm"] = _pct(sum(1 for i in ids if items[i]["ref_ok_in_shellm"]), len(ids))
        ids = [i for i in items if items[i]["set"] == s]
        res["sets"][s + "_first_word_is_command"] = sum(1 for i in ids if items[i]["first_word_is_command"])
        if s == "C":
            res["sets"]["C_ref_syntax_ok"] = _pct(sum(1 for i in ids if not items[i]["ref_syntax"]), len(ids))
    # A/B paired comparison (discordant pairs for McNemar)
    for s in "AB":
        v1 = {r["id"]: r["ok_shellm"] for r in rows if r["set"] == s and r["prompt"] == "v1"}
        v2 = {r["id"]: r["ok_shellm"] for r in rows if r["set"] == s and r["prompt"] == "v2"}
        common = set(v1) & set(v2)
        b = sum(1 for i in common if v2[i] and not v1[i])
        c = sum(1 for i in common if v1[i] and not v2[i])
        res["sets"][s + "_discordant_v2only_v1only"] = [b, c]
        res["sets"][s + "_mcnemar_p"] = _mcnemar(b, c)
    # latency (duration of the successful attempt) and availability
    for pr in ("v1", "v2"):
        R = [r for (i, p), r in resp.items() if p == pr]
        ok_t = [r["attempts"][-1]["t"] for r in R if r["status"] == "OK"]
        # waits caused by the per-minute quota (429) do not count as availability errors
        first_ok = sum(1 for r in R if [a for a in r["attempts"] if a["code"] != 429][:1]
                       and [a for a in r["attempts"] if a["code"] != 429][0]["code"] == 200)
        total = [sum(a["t"] for a in r["attempts"]) for r in R if r["status"] == "OK"]
        res["latency"][pr] = {
            "n": len(R), "ok": len(ok_t),
            "median_s": round(st.median(ok_t), 3) if ok_t else None,
            "p90_s": round(sorted(ok_t)[int(0.9 * len(ok_t)) - 1], 3) if ok_t else None,
            "max_s": round(max(ok_t), 3) if ok_t else None,
            "under_3s_pct": _pct(sum(1 for t in ok_t if t < 3.0), len(ok_t)),
            "first_attempt_ok_pct": _pct(first_ok, len(R)),
            "median_total_incl_retries_s": round(st.median(total), 3) if total else None,
            "error_codes": dict(collections.Counter(str(a["code"]) for r in R for a in r["attempts"] if a["code"] != 200)),
            "usage_total_tokens_median": st.median([(r.get("usage") or {}).get("totalTokenCount", 0) for r in R if r["status"] == "OK"]) if ok_t else None,
        }
    json.dump(res, open(SUMMARY, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False, indent=1))


def _mcnemar(b, c):
    """Exact (binomial) McNemar test, two-sided p value."""
    n = b + c
    if n == 0:
        return 1.0
    from math import comb
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return round(min(1.0, 2 * p), 5)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["prepare", "query", "score", "summary"])
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    if a.phase == "prepare":
        prepare()
    elif a.phase == "query":
        try:
            query(a.limit)
        except DailyQuota as e:
            print("DAILY QUOTA EXHAUSTED:", e)
            sys.exit(3)
    elif a.phase == "score":
        score()
    else:
        summary()
