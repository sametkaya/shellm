#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E10 — Testing the secret filter.

Positives: command lines containing common access key and password formats,
generated with random values (fixed seed). The formats are of kinds that tools
such as gitleaks recognize; the values are not real.
Negatives: all inputs of the experiment (A, B, E, C) and all commands in the
NL2Bash corpus. Lines flagged in NL2Bash are also listed (some of them really
contain passwords; these are reviewed by hand).
"""
import json
import os
import random
import string
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from paths import V2_BIN, RESULTS, NL2BASH_CM  # noqa: E402

rng = random.Random(4242)


def rnd(n, alphabet=string.ascii_letters + string.digits):
    return "".join(rng.choice(alphabet) for _ in range(n))


def positives():
    up, al = string.ascii_uppercase + string.digits, string.ascii_letters + string.digits
    gen = [
        ("aws", lambda: "aws configure set aws_access_key_id AKIA%s" % rnd(16, up)),
        ("aws_env", lambda: "export AWS_SECRET_ACCESS_KEY=%s" % rnd(40, al + "/+")),
        ("github", lambda: "git clone https://oauth2:ghp_%s@github.com/team/repo.git" % rnd(36)),
        ("github_pat", lambda: "gh auth login --with-token github_pat_%s" % rnd(60, al + "_")),
        ("gitlab", lambda: "curl -H 'PRIVATE-TOKEN: glpat-%s' https://gitlab.com/api/v4/projects" % rnd(20, al + "-_")),
        ("slack", lambda: "curl -X POST -H 'Authorization: Bearer xoxb-%s-%s-%s' https://slack.com/api/chat.postMessage"
         % (rnd(12, string.digits), rnd(12, string.digits), rnd(24))),
        ("openai", lambda: "export OPENAI_API_KEY=sk-proj-%s" % rnd(48, al + "-_")),
        ("google", lambda: "curl 'https://maps.googleapis.com/maps/api/geocode/json?key=AIza%s'" % rnd(35, al + "-_")),
        ("jwt", lambda: "curl -H 'Authorization: Bearer eyJ%s.%s.%s' https://api.example.com/v1/me"
         % (rnd(30, al), rnd(40, al), rnd(40, al + "-_"))),
        ("private_key", lambda: "echo '-----BEGIN OPENSSH PRIVATE KEY-----' > key"),
        ("mysql", lambda: "mysql -u root -p%s database" % rnd(14, al + "!#%")),
        ("password_env", lambda: "export DB_PASSWORD=%s" % rnd(12, al)),
        ("token_arg", lambda: "npm config set //registry.npmjs.org/:_authToken=%s" % rnd(36, al)),
        ("bearer", lambda: "curl -H 'Authorization: Bearer %s' https://api.example.com" % rnd(40, al)),
        ("typo_secret", lambda: "exprot API_KEY=%s" % rnd(32, al)),
    ]
    out = []
    for name, g in gen:
        for _ in range(4):
            out.append((name, g()))
    return out


def secret(line):
    p = subprocess.run([V2_BIN, "--check", line], capture_output=True, text=True, timeout=5)
    for l in p.stdout.splitlines():
        k, _, v = l.partition("\t")
        if k == "secret":
            return "" if v.strip() == "-" else v.strip()
    return ""


def main():
    pos = positives()
    tp = [(n, l, secret(l)) for n, l in pos]
    items = json.load(open(os.path.join(RESULTS, "llm2_items.json")))
    task_fp = [(i["id"], i["input"]) for i in items if secret(i["input"])]
    cms = sorted({c.strip() for c in open(NL2BASH_CM, encoding="utf-8", errors="replace") if c.strip()})
    nl_flag = [(c, secret(c)) for c in cms]
    nl_flag = [(c, r) for c, r in nl_flag if r]
    res = {"positives": len(pos), "detected": sum(1 for *_, r in tp if r),
           "missed": [(n, l) for n, l, r in tp if not r],
           "task_inputs": len(items), "task_inputs_flagged": task_fp,
           "nl2bash_commands": len(cms), "nl2bash_flagged": len(nl_flag),
           "nl2bash_flagged_lines": nl_flag}
    json.dump(res, open(os.path.join(RESULTS, "secret_eval.json"), "w"), ensure_ascii=False, indent=1)
    print("positives %d/%d" % (res["detected"], res["positives"]), "missed:", res["missed"])
    print("flagged in task inputs:", task_fp)
    print("NL2Bash flagged: %d/%d" % (len(nl_flag), len(cms)))
    for c, r in nl_flag:
        print("   ", r, "|", c[:110])


if __name__ == "__main__":
    main()
