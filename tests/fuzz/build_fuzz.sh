#!/bin/sh
# Builds and runs the libFuzzer target (requires clang and libclang-rt).
#   sh build_fuzz.sh            # 90-minute campaign
# Runs in an empty directory because glob expansion touches the real file
# system; timeouts are ignored because inputs such as "/*/*/*/*" are slow in
# Bash too.
set -e
cd "$(dirname "$0")"
ROOT=../..
SRCS=$(cd $ROOT && ls *.c */*.c | grep -v '^main.c$')
INC="-I$ROOT -I$ROOT/libft -I$ROOT/ast -I$ROOT/builtins -I$ROOT/env -I$ROOT/redir -I$ROOT/signal -I$ROOT/tokens"
clang -g -O1 -fsanitize=fuzzer,address,undefined -fno-sanitize-recover=undefined $INC \
    -o fuzz_parse fuzz_parse.c $(for f in $SRCS; do echo $ROOT/$f; done) -lreadline
mkdir -p corpus empty
python3 - <<'PY'
import json, os, sys
sys.path.insert(0, "..")
import cases, cases_holdout
seeds = set()
for C in (cases.CASES, cases_holdout.CASES):
    for c in C:
        seeds.update(l for l in c["script"].splitlines() if l.strip())
p = "../results/llm2_items.json"
if os.path.exists(p):
    for i in json.load(open(p)):
        seeds.add(i["input"]); seeds.add(i["ref"])
for n, s in enumerate(sorted(seeds)):
    open("corpus/s%04d" % n, "w").write(s)
PY
cd empty && HOME=/tmp ../fuzz_parse -fork=1 -ignore_timeouts=1 -max_total_time=5400 \
    -max_len=512 -timeout=10 -close_fd_mask=3 -artifact_prefix=../crash- ../corpus
