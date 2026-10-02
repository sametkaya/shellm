#!/usr/bin/env bash
# Builds a Debian/Ubuntu package: shellm_<version>_<arch>.deb
#   packaging/build_deb.sh
#   MAINTAINER="Full Name <email>" packaging/build_deb.sh
# Install:   sudo apt install ./shellm_1.0.0_amd64.deb
# Uninstall: sudo apt remove shellm
set -euo pipefail
cd "$(dirname "$0")/.."
command -v dpkg-deb >/dev/null || { echo "dpkg-deb is required (Debian/Ubuntu)" >&2; exit 1; }

VERSION="$(sed -n 's/^VERSION = //p' Makefile)"
ARCH="$(dpkg --print-architecture)"
MAINTAINER="${MAINTAINER:-SheLLM team <shellm@example.org>}"
OUT="${OUT:-$PWD/shellm_${VERSION}_${ARCH}.deb}"
ROOT="$(mktemp -d)"
trap 'rm -rf "$ROOT"' EXIT

make --no-print-directory fclean >/dev/null 2>&1 || true
make --no-print-directory -j"$(nproc)" PREFIX=/usr >/dev/null
make --no-print-directory install PREFIX=/usr DESTDIR="$ROOT" >/dev/null
strip --strip-unneeded "$ROOT/usr/bin/shellm"
make --no-print-directory fclean >/dev/null

DOC="$ROOT/usr/share/doc/shellm"
cat > "$DOC/copyright" <<COPY
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: SheLLM
Source: https://github.com/sametkaya/shellm

Files: *
Copyright: 2025-2026 SheLLM team, Fatih Sultan Mehmet Vakif University
License: (to be decided by the project team)
 This package links against GNU Readline, which is licensed under
 GPL-3.0-or-later.
COPY
gzip -9n -c CHANGES.md > "$DOC/changelog.gz" && rm -f "$DOC/CHANGES.md"

mkdir -p "$ROOT/DEBIAN"
SIZE="$(du -ks "$ROOT/usr" | cut -f1)"
cat > "$ROOT/DEBIAN/control" <<CTRL
Package: shellm
Version: $VERSION
Section: shells
Priority: optional
Architecture: $ARCH
Depends: libc6, libreadline8t64 | libreadline8, python3 (>= 3.8)
Suggests: ollama
Homepage: https://github.com/sametkaya/shellm
Installed-Size: $SIZE
Maintainer: $MAINTAINER
Description: teaching Unix shell with language-model command suggestions
 SheLLM asks a language model (Gemini, Claude, OpenAI or a local model) for
 one command suggestion when a command name cannot be resolved, when a line
 cannot be parsed because of an unmatched quote, or when a line starts
 with '#'. The suggestion is checked for risk and unsupported syntax, shown
 to the user, and run by the shell's own parser only after confirmation.
 A setup wizard runs on first start or with 'shellm --setup'. The interface
 is in English or Turkish.
CTRL
find "$ROOT" -type d -exec chmod 755 {} +
dpkg-deb --build --root-owner-group "$ROOT" "$OUT" >/dev/null
echo "Built: $OUT"
