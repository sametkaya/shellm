#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SheLLM AI helper server.

The SheLLM shell starts this script itself:
    python3 ai_helper.py --socket /tmp/shellm-XXXXXX/ai.sock

Protocol (one-line messages ending in '\\n'):
    request: {"op":"ping"}  |  {"op":"suggest","input":...,"cwd":...,"exit_code":127}
    reply  : "OK\\t<text>"  |  "NONE\\t"  |  "ERR\\t<explanation>"

Environment variables:
    GEMINI_API_KEY      Gemini API key (never written into source code)
    ANTHROPIC_API_KEY   Claude (Anthropic) API key
    OPENAI_API_KEY      OpenAI API key
    SHELLM_BACKEND      gemini | anthropic | openai | local | mock (offline testing);
                        if unset, the first provider with a key is used
    SHELLM_MODEL        model name; defaults: gemini-flash-lite-latest,
                        claude-haiku-4-5, gpt-5.4-mini (low-latency models)
    SHELLM_LOCAL_URL    local OpenAI-compatible server (default http://127.0.0.1:8080/v1;
                        for Ollama http://localhost:11434/v1)
    SHELLM_CONTEXT      0: do not send the directory context to the model
    SHELLM_LANG         interface language of messages: en (default) or tr
    SHELLM_GEMINI_URL   API base URL (can be changed for testing)
    SHELLM_MOCK_DELAY   artificial delay of the mock backend (seconds)
    SHELLM_MOCK_BIG     mock backend returns a long reply (testing only)
    SHELLM_MOCK_FIXED   mock backend returns this fixed reply (testing only)

Settings file: $XDG_CONFIG_HOME/shellm/config (or ~/.config/shellm/config) with
"KEY=value" lines; created by "shellm --setup" with mode 0600 so that only the
user can read it. Environment variables take precedence over the file. Keys
from this file are read only by the helper process; they never enter the
environment of the shell or of the programs it starts.

Changes over v1: the API key is read from the environment or the settings file;
a Unix domain socket instead of TCP; line-based framing; REST calls with the
standard library instead of a third-party SDK; a prompt with directory context
and SheLLM's grammar constraints; reply cleaning (code fences, explanation
lines); immunity to SIGINT; retries within a time limit after transient API
errors (429, 5xx).
"""
import argparse
import difflib
import json
import os
import signal
import socket
import sys
import time
import urllib.error
import urllib.request

VERSION = "1.0.0"
CONFIG_KEYS = ("SHELLM_LANG", "SHELLM_BACKEND", "SHELLM_MODEL", "SHELLM_LOCAL_URL", "SHELLM_LOCAL_KEY",
               "SHELLM_CONTEXT", "SHELLM_OPENAI_EFFORT", "GEMINI_API_KEY",
               "GOOGLE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def lang_tr():
    """Interface language: English by default; Turkish when SHELLM_LANG=tr, or when
    SHELLM_LANG is unset and LC_ALL, LC_MESSAGES or LANG starts with "tr"."""
    v = os.environ.get("SHELLM_LANG")
    if not v:
        v = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
             or os.environ.get("LANG") or "")
    return v[:2].lower() == "tr"


def T(en, tr):
    """Returns the message for the current interface language."""
    return tr if lang_tr() else en


ENV_OVERRIDES = set()   # keys set both in the settings file and in the environment


def config_path():
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config")
    return os.path.join(base, "shellm", "config")


def read_config(path=None):
    """Reads the settings file; only known keys are accepted."""
    path = path or config_path()
    cfg = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if k.startswith("export "):
                    k = k[7:].strip()
                if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                    v = v[1:-1]
                if k in CONFIG_KEYS:
                    cfg[k] = v
    except OSError:
        pass
    return cfg


def load_config():
    """Loads values from the settings file for keys not set in the environment."""
    path = config_path()
    cfg = read_config(path)
    ENV_OVERRIDES.update(k for k in cfg if os.environ.get(k))
    for k, v in cfg.items():
        os.environ.setdefault(k, v)
    try:
        if cfg and os.stat(path).st_mode & 0o077:
            print(T("warning: %s is readable by others; run 'chmod 600'",
                    "uyarı: %s başkalarınca okunabilir; 'chmod 600' önerilir") % path,
                  file=sys.stderr)
    except OSError:
        pass
    return cfg


load_config()

MODEL = os.environ.get("SHELLM_MODEL", "gemini-flash-lite-latest")  # for Gemini
BASE_URL = os.environ.get("SHELLM_GEMINI_URL",
                          "https://generativelanguage.googleapis.com/v1beta")
BUILTINS = ["echo", "cd", "pwd", "export", "unset", "env", "exit"]

SYSTEM_PROMPT = """You are the command assistant of SheLLM, a small Unix shell.
The user's input just failed with "command not found" (exit status 127).
The input is either a mistyped command or a request written in natural
language (often Turkish). Reply with exactly ONE command line that SheLLM can
execute and nothing else: no explanation, no markdown, no code fences.

SheLLM supports ONLY: simple commands with arguments; pipes (|); redirections
<, >, >> and here-documents (<<); single and double quotes; $VAR and $?
expansion; ~ and ~/ at the start of a word; wildcards * ? [...].
SheLLM does NOT support: ; && || & $(...) backticks ( ) subshells {a,b} brace
expansion, 2> or 2>&1, backslash escapes, or variable assignment without
export. If a task would need these, express it as a single pipeline of
standard utilities. Prefer safe, non-destructive commands. If you cannot
produce a suitable command, reply exactly: #NONE"""


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


# ----------------------------------------------------------------- context
def build_context(cwd):
    if os.environ.get("SHELLM_CONTEXT", "1") == "0" or not cwd:
        return ""
    try:
        names = sorted(os.listdir(cwd))[:60]
        entries = []
        for n in names:
            if n.startswith("."):
                continue
            entries.append(n + ("/" if os.path.isdir(os.path.join(cwd, n)) else ""))
        listing = ", ".join(entries[:50])
    except OSError:
        listing = "(unreadable)"
    return ("Context:\n- operating system: Linux\n- current directory: %s\n"
            "- entries in current directory: %s\n" % (cwd, listing))


def user_message(req):
    return ("%sFailed input (exit status %s):\n%s"
            % (build_context(req.get("cwd", "")), req.get("exit_code", 127),
               req.get("input", "")))


# ---------------------------------------------------------- reply cleaning
def clean_reply(text):
    """Extracts a single command line from the model output."""
    if not text:
        return None
    lines = [l.rstrip() for l in text.strip().splitlines()]
    lines = [l for l in lines if l.strip() and not l.strip().startswith("```")]
    if not lines:
        return None
    cmd = lines[0].strip()
    if cmd.startswith("$ "):
        cmd = cmd[2:]
    if len(cmd) >= 2 and cmd[0] == "`" and cmd[-1] == "`":
        cmd = cmd[1:-1].strip()
    if not cmd or cmd.upper().startswith("#NONE") or len(cmd) > 1000:
        return None
    return cmd


# ---------------------------------------------------------------- backends
RETRY_CODES = (429, 500, 502, 503, 504)


# Providers: each builds a single HTTP request and extracts the text from the
# reply. The retry policy belongs to the caller (time-limited in the shell,
# quota-aware in the experiments). Keys are read only from the environment
# (filled from the settings file at startup).
PROVIDERS = {
    "gemini": {"keys": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
               "model": "gemini-flash-lite-latest"},
    "anthropic": {"keys": ("ANTHROPIC_API_KEY",), "model": "claude-haiku-4-5"},
    "openai": {"keys": ("OPENAI_API_KEY",), "model": "gpt-5.4-mini"},
    # Local model: an OpenAI-compatible server (llama.cpp llama-server, Ollama);
    # requests never leave the machine and no key is needed.
    "local": {"keys": (), "model": "local"},
}


def provider_key(provider):
    if provider == "local":
        return os.environ.get("SHELLM_LOCAL_KEY", "yerel")
    for k in PROVIDERS[provider]["keys"]:
        if os.environ.get(k):
            return os.environ[k]
    return None


def provider_model(provider):
    if os.environ.get("SHELLM_MODEL"):
        return os.environ["SHELLM_MODEL"]
    return PROVIDERS[provider]["model"]


class ProviderError(Exception):
    def __init__(self, code, body=""):
        Exception.__init__(self, "HTTP %s" % code)
        self.code = code
        self.body = body


def _build(provider, model, system, text, drop=()):
    key = provider_key(provider)
    if provider == "gemini":
        body = {"contents": [{"role": "user", "parts": [{"text": text}]}],
                "generationConfig": {"temperature": 0}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        url = "%s/models/%s:generateContent" % (BASE_URL, model)
        hdr = {"x-goog-api-key": key}
    elif provider == "anthropic":
        body = {"model": model, "max_tokens": 256, "temperature": 0,
                "messages": [{"role": "user", "content": text}]}
        if system:
            body["system"] = system
        url = os.environ.get("SHELLM_ANTHROPIC_URL",
                             "https://api.anthropic.com/v1").rstrip("/") + "/messages"
        hdr = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    else:
        msgs = ([{"role": "system", "content": system}] if system else []) + \
            [{"role": "user", "content": text}]
        body = {"model": model, "messages": msgs, "temperature": 0}
        if provider == "openai":
            body["max_completion_tokens"] = 2048
            if os.environ.get("SHELLM_OPENAI_EFFORT", "none"):
                body["reasoning_effort"] = os.environ.get("SHELLM_OPENAI_EFFORT", "none")
            url = os.environ.get("SHELLM_OPENAI_URL", "https://api.openai.com/v1")
        else:
            body["max_tokens"] = 256
            url = os.environ.get("SHELLM_LOCAL_URL", "http://127.0.0.1:8080/v1")
        url = url.rstrip("/") + "/chat/completions"
        hdr = {"Authorization": "Bearer %s" % key}
    for d in drop:
        body.pop(d, None)
    hdr["Content-Type"] = "application/json"
    return url, hdr, json.dumps(body).encode("utf-8")


def _extract(provider, d):
    """Returns (text, actual_model_version, usage)."""
    if provider == "gemini":
        cand = d["candidates"][0]
        # Replies blocked by a content filter have no "parts": no suggestion.
        parts = cand.get("content", {}).get("parts", [])
        usage = dict(d.get("usageMetadata") or {}, finishReason=cand.get("finishReason"))
        return ("".join(p.get("text", "") for p in parts), d.get("modelVersion"), usage)
    if provider == "anthropic":
        txt = "".join(c.get("text", "") for c in d["content"] if c.get("type") == "text")
        return txt, d.get("model"), d.get("usage")
    return d["choices"][0]["message"].get("content") or "", d.get("model"), d.get("usage")


def provider_request(provider, model, system, text, timeout):
    """A single API request. Returns (text, version, usage) on success and
    raises ProviderError on an HTTP error. Parameters that some models reject
    (e.g. temperature, reasoning_effort) are dropped after a 400 reply and the
    request is repeated once."""
    drop = []
    for _ in range(3):
        url, hdr, data = _build(provider, model, system, text, drop)
        r = urllib.request.Request(url, data=data, headers=hdr)
        try:
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            return _extract(provider, d)
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                body = ""
            if e.code == 400 and provider == "openai":
                bad = [p for p in ("temperature", "reasoning_effort")
                       if p in body and p not in drop]
                if bad:
                    drop += bad
                    continue
            raise ProviderError(e.code, body)
    raise ProviderError(400, "parametreler kabul edilmedi")


def generate(system, text, deadline=18.0, max_attempts=3, provider=None):
    """Call used by the shell: retries transient errors (429, 5xx, network
    errors) with exponential backoff within a total time limit.
    Returns (status, text, attempts); status is "OK" or "ERR"."""
    provider = provider or backend_name()
    if not provider_key(provider):
        return "ERR", T("%s is not set", "%s tanımlı değil") % PROVIDERS[provider]["keys"][0], 0
    model = provider_model(provider)
    t_end = time.monotonic() + deadline
    err = T("unknown error", "bilinmeyen hata")
    attempt = 0
    for attempt in range(1, max_attempts + 1):
        remaining = t_end - time.monotonic()
        if remaining <= 0.5:
            break
        try:
            txt, _, _ = provider_request(provider, model, system, text,
                                         min(remaining, 15))
            return "OK", txt, attempt
        except ProviderError as e:
            err = "HTTP %s" % e.code
            if e.code not in RETRY_CODES:
                return "ERR", err, attempt
        except (KeyError, IndexError, TypeError, ValueError):
            return "ERR", T("unexpected response", "beklenmeyen yanıt"), attempt
        except Exception as e:  # network error, timeout
            err = type(e).__name__
        wait = 0.8 * (2 ** (attempt - 1))
        if time.monotonic() + wait >= t_end - 0.5:
            break
        time.sleep(wait)
    return "ERR", err, attempt


def gemini_generate(system, text, deadline=18.0, max_attempts=3):
    return generate(system, text, deadline, max_attempts, "gemini")


def model_backend(req):
    try:
        deadline = max(3.0, float(os.environ.get("SHELLM_AI_TIMEOUT", "20")) - 2.0)
    except ValueError:
        deadline = 18.0
    status, text, _ = generate(SYSTEM_PROMPT, user_message(req), deadline)
    if status != "OK":
        return "ERR", text
    cmd = clean_reply(text)
    return ("OK", cmd) if cmd else ("NONE", "")


def _executables():
    names = set(BUILTINS)
    for d in os.environ.get("PATH", "").split(":"):
        try:
            for n in os.listdir(d):
                if os.access(os.path.join(d, n), os.X_OK):
                    names.add(n)
        except OSError:
            pass
    return sorted(names)


def mock_backend(req):
    """Offline backend: replaces the first word with the closest command name
    on PATH (difflib). No model is involved; used for IPC and interface
    measurements and for trying SheLLM without an API key."""
    delay = float(os.environ.get("SHELLM_MOCK_DELAY", "0"))
    if delay > 0:
        time.sleep(delay)
    fixed = os.environ.get("SHELLM_MOCK_FIXED")
    if fixed:  # testing only: fixed reply (to measure communication overhead)
        return "OK", fixed
    big = int(os.environ.get("SHELLM_MOCK_BIG", "0"))
    if big > 0:  # testing only: long reply
        return "OK", "echo " + "x" * big
    words = req.get("input", "").split(" ", 1)
    if not words or not words[0]:
        return "NONE", ""
    m = difflib.get_close_matches(words[0], _executables(), n=1, cutoff=0.6)
    if not m:
        return "NONE", ""
    return "OK", " ".join([m[0]] + words[1:])


def backend_name():
    """If SHELLM_BACKEND is unset, the first provider with a key is chosen."""
    b = os.environ.get("SHELLM_BACKEND", "").lower()
    if b in PROVIDERS or b == "mock":
        return b
    for p in ("gemini", "anthropic", "openai"):  # "local" only when chosen explicitly
        if provider_key(p):
            return p
    return "gemini"


def handle(req):
    op = req.get("op")
    if op == "ping":
        b = backend_name()
        if b == "mock":
            return "OK", "mock"
        if not provider_key(b):
            return "ERR", T("%s is not set", "%s tanımlı değil") % PROVIDERS[b]["keys"][0]
        return "OK", provider_model(b)
    if op == "suggest":
        return mock_backend(req) if backend_name() == "mock" else model_backend(req)
    return "ERR", T("unknown operation", "bilinmeyen işlem")


# ------------------------------------------------------------------ server
def recv_line(conn, limit=65536):
    buf = b""
    while not buf.endswith(b"\n") and len(buf) < limit:
        chunk = conn.recv(4096)
        if not chunk:
            break
        buf += chunk
    return buf.decode("utf-8", "replace").strip()


def serve(path):
    if os.path.exists(path):
        os.unlink(path)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old = os.umask(0o177)
    srv.bind(path)
    os.umask(old)
    srv.listen(4)
    log("listening:", path, "backend:", backend_name())
    while True:
        conn, _ = srv.accept()
        with conn:
            conn.settimeout(30)
            try:
                line = recv_line(conn)
                req = json.loads(line) if line else {}
                status, text = handle(req)
            except Exception as e:  # a malformed request must not stop the server
                status, text = "ERR", type(e).__name__
            text = (text or "").replace("\n", " ").replace("\t", " ")
            try:
                conn.sendall(("%s\t%s\n" % (status, text)).encode("utf-8"))
            except OSError:
                pass
            if req.get("op") == "suggest":
                log(status, repr(req.get("input", ""))[:80], "->", repr(text)[:80])


def main():
    ap = argparse.ArgumentParser(description="SheLLM AI helper process")
    ap.add_argument("--socket", help="Unix socket opened by the shell")
    ap.add_argument("--setup", action="store_true", help="run the setup wizard")
    ap.add_argument("--version", action="store_true")
    a = ap.parse_args()
    if a.version:
        print("SheLLM ai_helper %s" % VERSION)
        return
    if a.setup:
        import shellm_setup  # noqa: E402  (the wizard next to this file)
        sys.exit(shellm_setup.run(sys.modules[__name__]))
    if not a.socket:
        ap.error("--socket or --setup is required")
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    serve(a.socket)


if __name__ == "__main__":
    main()
