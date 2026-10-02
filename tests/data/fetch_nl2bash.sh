#!/bin/sh
# Downloads the NL2Bash corpus (Lin et al., 2018; GPL-3.0) used to build task set C
# and for the syntax-coverage and secret-filter checks. The files are not
# redistributed in this repository.
set -e
cd "$(dirname "$0")"
BASE=https://raw.githubusercontent.com/TellinaTool/nl2bash/master/data/bash
for f in all.cm all.nl; do
    curl -fsSL "$BASE/$f" -o "$f"
done
# Checksums of the version used in the experiments
md5sum -c <<SUMS
b059051640a7b4b3c2c2fa18829f037f  all.cm
01886b4ea43dfe288db96edad82ea612  all.nl
SUMS
