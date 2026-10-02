#!/usr/bin/env python3
"""make test: compares SheLLM with Bash (main and hold-out test suites).
Category L (unsupported syntax) is an expected failure. The fresh results are
written to a temporary directory; the recorded ones in results/ are not changed."""
import os
import shutil
import subprocess
import sys
import tempfile
import compare as C

tmp = tempfile.mkdtemp(prefix="shellm-test-")
os.environ["SHELLM_RESULTS"] = tmp
ok = True
for suite, suf in (("main", ""), ("holdout", "_holdout")):
    for impl in ("bash", "v2"):
        subprocess.run([sys.executable, "run_tests.py", "--impl", impl, "--suite", suite,
                        "--jobs", "4", "--out", os.path.join(tmp, impl + suf + ".json")],
                       check=True, stdout=subprocess.DEVNULL)
    per, fails = C.summarize("v2" + suf, ref="bash" + suf)
    sup = {k: v for k, v in per.items() if k != "L"}
    passed = sum(v[0] for v in sup.values()); total = sum(v[1] for v in sup.values())
    bad = [f if isinstance(f, str) else f[0] for f in fails]
    bad = [f for f in bad if not f.startswith("L")]
    print("%-8s supported syntax: %d/%d identical to Bash%s" % (
        suite, passed, total, ("; different: " + ", ".join(bad)) if bad else ""))
    ok &= not bad
shutil.rmtree(tmp, ignore_errors=True)
sys.exit(0 if ok else 1)
