#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Summarizes the Valgrind logs per test."""
import glob
import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_log(path):
    t = open(path, errors="replace").read()
    errs = 0
    m = re.search(r"ERROR SUMMARY: (\d+) errors", t)
    if m:
        errs = int(m.group(1))
    invalid = len(re.findall(r"Invalid (?:read|write|free)", t))
    uninit = len(re.findall(r"uninitialised value", t))
    lost = 0
    m = re.search(r"definitely lost: ([\d,]+) bytes", t)
    if m:
        lost = int(m.group(1).replace(",", ""))
    # Descriptors the shell opened and did not close (excluding inherited ones and log files)
    fds = 0
    for block in re.findall(r"Open (?:file descriptor|AF_UNIX socket) (\d+):([^\n]*)\n==\d+==\s+(.*)", t):
        fd, what, where = block
        if "inherited from parent" in where or what.strip().endswith(".log"):
            continue
        if int(fd) <= 2:
            continue
        fds += 1
    return errs, invalid, uninit, lost, fds


def summarize(impl):
    d = os.path.join(HERE, "results", "vg_" + impl)
    per = defaultdict(lambda: [0, 0, 0, 0, 0])
    for p in glob.glob(os.path.join(d, "*.log")):
        tid = os.path.basename(p).split(".")[0]
        r = parse_log(p)
        for i in range(5):
            per[tid][i] += r[i]
    return per


if __name__ == "__main__":
    out = {}
    for impl in sys.argv[1:] or ["v1", "v2"]:
        per = summarize(impl)
        n = len(per)
        with_err = [t for t, v in per.items() if v[0] > 0]
        with_invalid = [t for t, v in per.items() if v[1] > 0]
        with_lost = [t for t, v in per.items() if v[3] > 0]
        with_fd = [t for t, v in per.items() if v[4] > 0]
        total_lost = sum(v[3] for v in per.values())
        out[impl] = dict(tests=n, tests_with_errors=len(with_err),
                         tests_with_invalid_access=len(with_invalid),
                         tests_with_definite_leak=len(with_lost),
                         definitely_lost_bytes=total_lost,
                         tests_with_fd_leak=len(with_fd),
                         error_tests=sorted(with_err), leak_tests=sorted(with_lost),
                         fd_tests=sorted(with_fd))
        print("== %s: %d tests" % (impl, n))
        for k in ("tests_with_errors", "tests_with_invalid_access",
                  "tests_with_definite_leak", "definitely_lost_bytes", "tests_with_fd_leak"):
            print("  %-28s %s" % (k, out[impl][k]))
        print("  errors:", " ".join(sorted(with_err)))
        print("  leaks:", " ".join(sorted(with_lost)))
        print("  fd:", " ".join(sorted(with_fd)))
    json.dump(out, open(os.path.join(HERE, "results", "valgrind_summary.json"), "w"),
              ensure_ascii=False, indent=1)
