#!/usr/bin/env bash
# SheLLM installer (Linux, and Windows via WSL).
#
#   ./install.sh                 install for the current user: ~/.local/bin/shellm (no sudo)
#   ./install.sh --system        install for all users: /usr/local/bin/shellm (sudo)
#   ./install.sh --prefix DIR    install under DIR
#   ./install.sh --deps          install missing packages (compiler, readline, python3)
#   ./install.sh --no-setup      do not open the setup wizard after installing
#   ./install.sh --uninstall     remove SheLLM
set -euo pipefail

VERSION="1.0.0"
PREFIX="${PREFIX:-$HOME/.local}"
ACTION="install"
SYSTEM=0
DEPS=0
SETUP=1

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
info() { printf '  %s\n' "$*"; }
die()  { printf '\033[31mError:\033[0m %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
    case "$1" in
        --prefix) [ $# -ge 2 ] || die "--prefix needs a directory"; PREFIX="$2"; shift ;;
        --prefix=*) PREFIX="${1#--prefix=}" ;;
        --system) SYSTEM=1; PREFIX="/usr/local" ;;
        --deps) DEPS=1 ;;
        --no-setup) SETUP=0 ;;
        --uninstall) ACTION="uninstall" ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see ./install.sh --help)" ;;
    esac
    shift
done

cd "$(dirname "$0")"
[ -f ai_helper.py ] && [ -f Makefile ] || die "run this script from the SheLLM source directory"

SUDO=""
if [ "$SYSTEM" = 1 ] && [ "$(id -u)" != 0 ]; then
    command -v sudo >/dev/null || die "--system needs sudo"
    SUDO="sudo"
fi

interactive() { [ -t 0 ] && [ -t 1 ]; }

ask_yes() {   # ask_yes "question" default(Y|N); non-interactive runs take the default
    local d="$2" ans
    interactive || { [ "$d" = "Y" ]; return; }
    if [ "$d" = "Y" ]; then read -r -p "$1 [Y/n]: " ans || ans=""; else read -r -p "$1 [y/N]: " ans || ans=""; fi
    ans="$(printf '%s' "${ans:-$d}" | tr '[:upper:]' '[:lower:]')"
    case "$ans" in y|yes|e|evet) return 0 ;; *) return 1 ;; esac
}

# ------------------------------------------------------------- uninstall
if [ "$ACTION" = "uninstall" ]; then
    say "Removing SheLLM ($PREFIX)"
    $SUDO make --no-print-directory uninstall PREFIX="$PREFIX" >/dev/null
    info "Program files removed."
    CFG="${XDG_CONFIG_HOME:-$HOME/.config}/shellm"
    if [ -d "$CFG" ]; then
        if ask_yes "Also delete the settings file? (it may contain an API key: $CFG)" N; then
            rm -rf "$CFG"; info "Settings file deleted."
        else
            info "Settings file kept: $CFG"
        fi
    fi
    exit 0
fi

# ------------------------------------------------------------- checks
say "Installing SheLLM $VERSION"
[ "$(uname -s)" = "Linux" ] || die "only Linux (and WSL on Windows) is supported for now"
if grep -qi microsoft /proc/version 2>/dev/null; then
    info "Windows Subsystem for Linux (WSL) detected."
fi

missing=()
command -v make >/dev/null || missing+=("make")
CC_BIN="$(command -v cc || command -v gcc || true)"
[ -n "$CC_BIN" ] || missing+=("a C compiler")
if command -v python3 >/dev/null; then
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' \
        || missing+=("python3 (>= 3.8)")
else
    missing+=("python3")
fi
if [ -n "$CC_BIN" ]; then
    printf '#include <stdio.h>\n#include <readline/readline.h>\nint main(void){return 0;}\n' \
        | "$CC_BIN" -x c - -lreadline -o /dev/null 2>/dev/null || missing+=("GNU readline development files")
fi

pkg_cmd() {
    if command -v apt-get >/dev/null; then echo "apt-get install -y build-essential libreadline-dev python3"
    elif command -v dnf >/dev/null; then echo "dnf install -y gcc make readline-devel python3"
    elif command -v pacman >/dev/null; then echo "pacman -S --needed --noconfirm base-devel readline python"
    elif command -v zypper >/dev/null; then echo "zypper install -y gcc make readline-devel python3"
    else echo ""; fi
}

if [ ${#missing[@]} -gt 0 ]; then
    info "Missing: ${missing[*]}"
    PKG="$(pkg_cmd)"
    [ -n "$PKG" ] || die "install the missing packages with your distribution's package manager and try again"
    if [ "$DEPS" = 1 ] || ask_yes "Install the missing packages now? (sudo $PKG)" Y; then
        if command -v apt-get >/dev/null; then
            if [ "$(id -u)" = 0 ]; then apt-get update -qq; else sudo apt-get update -qq; fi
        fi
        if [ "$(id -u)" = 0 ]; then env DEBIAN_FRONTEND=noninteractive $PKG
        else sudo env DEBIAN_FRONTEND=noninteractive $PKG; fi
    else
        die "first run: sudo $PKG"
    fi
fi

# ------------------------------------------------------------- build and install
say "Building"
make --no-print-directory fclean >/dev/null 2>&1 || true
if ! make --no-print-directory -j"$(nproc 2>/dev/null || echo 2)" PREFIX="$PREFIX" > .build.log 2>&1; then
    tail -20 .build.log >&2
    die "build failed (details: .build.log)"
fi
rm -f .build.log

say "Installing to $PREFIX"
$SUDO make --no-print-directory install PREFIX="$PREFIX" >/dev/null
info "Program: $PREFIX/bin/shellm"
info "Helper files: $PREFIX/share/shellm"

# ------------------------------------------------------------- PATH
BIN="$PREFIX/bin"
case ":$PATH:" in
    *":$BIN:"*) ON_PATH=1 ;;
    *) ON_PATH=0 ;;
esac
if [ "$ON_PATH" = 0 ]; then
    LINE="export PATH=\"$BIN:\$PATH\""
    RC="$HOME/.bashrc"
    if [ "$(basename "${SHELL:-bash}")" = "zsh" ]; then RC="$HOME/.zshrc"; fi
    if grep -qsF "$LINE" "$RC"; then
        info "$BIN is already added to PATH in $RC; open a new terminal."
    elif ask_yes "$BIN is not on your PATH. Add it to $RC?" Y; then
        printf '\n# SheLLM\n%s\n' "$LINE" >> "$RC"
        info "Added. Open a new terminal or run: source $RC"
    else
        info "To start: $BIN/shellm"
    fi
fi

# ------------------------------------------------------------- setup wizard
CFG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/shellm/config"
if [ "$SETUP" = 1 ] && interactive && [ ! -f "$CFG_FILE" ]; then
    echo
    if ask_yes "Configure the language model now?" Y; then
        "$BIN/shellm" --setup || true
    else
        info "Later: shellm --setup (you will also be asked on first start)"
    fi
fi

echo
say "Installation complete."
info "Start:            shellm"
info "Change settings:  shellm --setup"
info "Uninstall:        ./install.sh --uninstall$( [ "$SYSTEM" = 1 ] && echo ' --system' )"
