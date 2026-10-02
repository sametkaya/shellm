#!/bin/sh
# Creates the AddressSanitizer builds of v1 and v2 (Section 7.3).
# v1: -fsanitize=address ; v2: -fsanitize=address,undefined
# Usage: sh build_asan.sh   (output: ${SHELLM_ASAN_DIR:-/tmp/shellm_asan})
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
V2=${SHELLM_V2_DIR:-$HERE/..}
V1=${SHELLM_V1_DIR:-$HERE/../../SheLLM/SheLLM}
OUT=${SHELLM_ASAN_DIR:-/tmp/shellm_asan}
rm -rf "$OUT" && mkdir -p "$OUT/v1" "$OUT/v2"
(cd "$V1" && tar --exclude='*.o' --exclude='*.a' --exclude='./SheLLM' -cf - .) | (cd "$OUT/v1" && tar -xf -)
(cd "$V2" && tar --exclude='*.o' --exclude='*.a' --exclude='./SheLLM' --exclude='./tests' -cf - .) | (cd "$OUT/v2" && tar -xf -)
make -C "$OUT/v1" CC="cc -fsanitize=address -fno-omit-frame-pointer" > "$OUT/v1.log" 2>&1
make -C "$OUT/v2" CC="cc -fsanitize=address,undefined -fno-omit-frame-pointer" > "$OUT/v2.log" 2>&1
echo "ASan builds: $OUT/v1/SheLLM  $OUT/v2/SheLLM"
