#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Heredoc temporary-file collisions between concurrent shell instances.

K shell instances run at the same time, each running a heredoc with its own
unique content (a short sleep after the content is written widens the race
window). Instances whose output does not match their own content are counted.
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paths import V1_BIN, V2_BIN, RESULTS  # noqa: E402
BIN = {"v1": V1_BIN, "v2": V2_BIN}
K = 16
ROUNDS = 5


def one(impl, i):
    d = "/tmp/hdrace/%s_%d" % (impl, i)
    os.makedirs(d, exist_ok=True)
    token = "icerik_%s_%d" % (impl, i)
    # After the heredoc is read, 'sleep' delays the command; if other instances
    # write to the same file name meanwhile, the content is corrupted.
    script = "cat << SON | (sleep 0.3; cat)\n%s\nSON\n" % token
    script = "sleep 0.1\ncat << SON > out.txt\n%s\nSON\nsleep 0.3\ncat out.txt\n" % token
    env = {"PATH": "/usr/bin:/bin", "HOME": d, "TERM": "dumb"}
    p = subprocess.run([BIN[impl]], input=script.encode(), cwd=d, env=env,
                       capture_output=True, timeout=30)
    out = p.stdout.decode(errors="replace")
    return token in out and out.count("icerik_") == 1


if __name__ == "__main__":
    res = {}
    for impl in ("v1", "v2"):
        bad = 0
        total = 0
        for r in range(ROUNDS):
            with ThreadPoolExecutor(max_workers=K) as ex:
                oks = list(ex.map(lambda i: one(impl, i), range(K)))
            bad += oks.count(False)
            total += len(oks)
        res[impl] = {"runs": total, "corrupted": bad}
        print(impl, res[impl])
    json.dump(res, open(os.path.join(RESULTS, "heredoc_race.json"), "w"), indent=1)
