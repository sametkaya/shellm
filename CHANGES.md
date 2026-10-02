# Changelog

SheLLM started as a student prototype ("v1") developed in a TÜBİTAK 2209-A project. This file
lists the changes from that prototype to the current version, newest first. IDs such as H1, S13
or B04 refer to the tests and scenarios in `tests/`.

## 1.0.0 — installable release (October 2026)

- `install.sh` (per-user or system-wide install, optional installation of missing packages,
  uninstall), `make install/uninstall/test/dist` targets, and a Debian package
  (`packaging/build_deb.sh`).
- Setup wizard (`shellm --setup`; runs automatically on first start): asks for the interface
  language, the provider, the API key (read without echo), the model and whether directory
  context may be sent, and verifies the choice with a test request.
- Settings file `~/.config/shellm/config` (mode 0600). Keys are read only by the helper process
  and never enter the shell's environment; environment variables take precedence over the file.
- Bilingual interface: English by default, Turkish when `SHELLM_LANG=tr` (environment or
  settings file) or when the locale (`LC_ALL`, `LC_MESSAGES`, `LANG`) starts with `tr`. Risky
  suggestions accept `yes` or `evet`; ordinary ones also `y` or `e`.
- Code, comments, file names, installer and documentation are in English; a Turkish translation
  of the installation guide is in `docs/INSTALL.tr.md`.
- The experiment scripts pin the English interface (`SHELLM_LANG=en`). The original runs used
  the Turkish interface; their recorded labels and shell messages were converted 1:1 to the
  English ones (see `tests/results/README.md`).
- `--version`, `--help` options.
- Security: `ai_helper.py` is no longer looked up in the current working directory (a shell
  started in an untrusted directory could run a script placed there); the installed data
  directory and `../share/shellm` are searched instead.
- Trailing `/` in server and API URLs is ignored.
- The `tests/` directory is excluded from the build sources (previously `make` also tried to
  compile the test C files).
- The risk rules' logic is unchanged from the version frozen for the evaluation; only their
  messages were translated (identical decisions on all 1,817 evaluation commands). The frozen
  file is kept byte for byte as `tests/guard/ai_risk_frozen.c`; `tests/guard/rules_frozen.sha256`
  holds its hash.
- `make test` writes its fresh results to a temporary directory, so it no longer overwrites
  the recorded results in `tests/results/`.
- `make legacy-guard` builds the shell with the rules before the revision
  (`tests/guard/ai_guard_old.c`), which the guard evaluations use as the "old" rules.
- `analysis/` regenerates the numbers, tables and figures of the papers; `data/` holds the
  benchmark in tabular form; `tests/data/fetch_nl2bash.sh` downloads the NL2Bash corpus.

## Changes after peer review (September 2026)

- **Triggering:** Instead of `$? == 127`, the shell's own decision is used: after parsing and before execution, the command name of every pipeline stage is resolved (`trigger.c`). Thus `grpe x | wc -l` (exit 0) triggers, while a 127 coming from a child process (`sh -c 'exit 127'`) does not. Evidence: S11, S12.
- **Apostrophe:** A line that cannot be parsed because of an unmatched quote is sent to the helper if its first word is not a command (`notlar.txt'yi sil`, Turkish for "delete notlar.txt"). Evidence: S13, `trigger_coverage.py` (B: 94 → 100/100).
- **Explicit request:** A `# request` line goes to the helper without being executed; when AI is off, it is a comment line. Intended for English requests that start with a command name (`find all python files`). Evidence: S16.
- **Secret filter:** Lines containing an access key, token or password are not sent to the model; the user is shown the reason. Evidence: S14, `secret_eval.py`.
- **API key:** After the helper starts, provider keys are removed from the environment the shell passes to child processes. Evidence: S15.
- **Risk checker (`ai_risk.c`):** five classes (deletion, overwrite, permission, system, network); distinction between `>` and `>>`; overwriting an existing file with `>`, `cp`, `mv`, `ln -f`, `tee`, `curl -o`, `wget -O`; `sed -i`, `perl -i`; `xargs rm`, the inner command of `find -exec`; commands inside `sh -c`/`ssh`; sending data out (`curl -T`, `-d @file`, `scp`/`rsync` to a remote target, `nc`); `~/.ssh` and startup files; account, firewall and service operations. Evidence: `guard/categories.py`, held-out NL2Bash sample (recall 34% → 82%).
- **Bug (found by fuzzing):** Two consecutive matching wildcards (`echo /b* /b*`) caused freed memory to be read during glob expansion (`tokens/glob_expand.c`). Fixed; test J15 added.
- **Providers:** `ai_helper.py` supports Gemini, Anthropic, OpenAI and OpenAI-compatible local servers (llama.cpp, Ollama).
- **`--check`** now also prints the result of the secret filter.

## Fixes over the student prototype (v1)

Each item gives the ID of the test or scenario that demonstrates the bug (see `tests/`).

| No | Severity | Bug (v1) | File | Fix (v2) | Evidence |
|----|----------|----------|------|----------|----------|
| H1 | Critical | When the first variable of the environment list is `unset`, freed memory is read and the shell crashes (SIGSEGV) | `builtins/builtin.c` | `export/unset/cd` now operate on `shell->env_list`; the whole execution path uses a single list head | I01, I02, I12, Ih04 |
| H2 | High | The AI flow resets `$?` to 0; exit status 127 after `command not found` is lost | `main.c` | If the suggestion is skipped, 127 is preserved; if it is run, the suggestion's exit status is used | B04, B05, B08, B10, B14, C10, S6 |
| H3 | High | The `atexit` handler also runs in every forked child and kills the AI service (no suggestion after a builtin in a pipeline or after a heredoc) | `main.c` | Cleanup runs only in the main process (PID check) and is done explicitly | S1, S2 |
| H4 | High | Out-of-bounds write in the socket client: if `read()` returns 1024, `buffer[1024]` is written; if it returns −1, `buffer[-1]` | `ai_client.c` | Line-based, bounds-checked dynamic read (at most 64 KB) | S7 (AddressSanitizer) |
| H5 | High | At startup, *any* process using port 12345 is killed with `fuser` | `main.c` | Each shell uses its own private Unix socket; other processes are left untouched | S5 |
| H6 | Medium | The AI service listens on a TCP port open to everyone; other users on the same machine can connect to it or inject suggestions through a fake server | `ai_client.c`, `ai_helper.py` | Unix domain socket in a temporary directory with mode 0700 (mkdtemp) | S10 |
| H7 | Medium | Ctrl+C at the prompt also kills the Python service in the same process group | `main.c` | The service runs in a separate session via `setsid()`; SIGINT is ignored on the Python side | S3 |
| H8 | Medium | An unresponsive model request blocks the shell indefinitely; no timeout, Ctrl+C is ignored | `ai_client.c` | `SO_RCVTIMEO` timeout (default 20 s, `SHELLM_AI_TIMEOUT`) and cancellation with Ctrl+C | S8 |
| H9 | Medium | The helper script is looked up in the working directory; when the shell is started from another directory, AI silently does not work, yet the UI shows "AI bagli" ("AI connected") | `main.c`, `ui.c` | The script is located from the executable's directory; the status line shows the actual state (ping) | S4 |
| H10 | Medium | Heredoc temporary files have fixed names (`/tmp/minishell_heredoc_N`): concurrent shells overwrite each other's content; open to symlink attacks | `redir/redir.c` | Unpredictable name via `mkstemp(3)`, mode 0600 | heredoc_race |
| H11 | Medium | Debug leftover for external commands in a pipeline: command names containing a slash are printed to stderr; 127 instead of 126 on permission/directory errors | `env/find.c`, `pipes/pipe_4.c` | Pipelines also use the main process's path resolution | B15, B16 |
| H12 | Medium | Wrong exit status for processes terminated by a signal (SIGTERM→15, SIGKILL→9; 143 and 137 in Bash) | `pipes/pipe_2.c`, `pipes/pipe.c` | Decoded with POSIX macros, 128+signal | B12, B13 |
| H13 | Low | A command consisting only of a redirection (`> file`) does not create the file | `parse/parse_execute_ast.c` | Redirections are applied even without a command | D11 |
| H14 | Low | With a double-quoted heredoc delimiter (`<< "EOF"`), the body is expanded | `redir/redir7.c` | No expansion if any part of the delimiter is quoted | E04 |
| H15 | Low | When a heredoc is terminated by end of file, its content is discarded and the warning is printed to stdout | `redir/redir.c` | As in Bash, the warning goes to stderr and the content is kept | E08 |
| H16 | Low | The unmatched-quote error is printed to stdout and the exit status is not changed | `main_utils.c` | stderr, exit status 2 | F19 |
| H17 | Low | Syntax checking does not work for consecutive redirection operators (`echo > > f`); an uninitialized argument array is freed | `parse/parse_command.c`, `parse/parse_command_utils.c` | Check fixed; the array is allocated with `ft_calloc` | Valgrind H04 |
| H18 | Low | Valueless `export X` variables are passed to child processes as `X=` | `builtins/builtin2.c` | Valueless variables are not exported | manual: `export NEWVAR` + `/usr/bin/env \| grep -c NEWVAR` |
| H19 | Low | External commands cannot run when the environment list becomes empty | `builtins/builtin2.c` | Empty array for an empty list | — |
| H20 | Low | A fixed 1 s wait at every startup | `main.c` | Readiness polling (ping) | E3b |
| H21 | Low | The `exit` message is printed to stdout; typos in messages (`command not found2`) | `env/exit.c`, `pipes/pipe_3.c` | Only in interactive mode, to stderr | — |
| H22 | Configuration | The API key was designed to be written into a constant in the source code | `ai_helper.py` | `GEMINI_API_KEY` environment variable | — |

## New features over the student prototype

- **Tilde and wildcard expansion:** An unquoted `~` or `~/` at the start of a word is expanded to HOME; unquoted words containing `*`, `?`, `[...]` are expanded with `glob(3)`. Wildcard characters inside quotes are escaped. If there is no match, the word is left as is (Bash default).
- **Script (non-tty) mode:** If input is not a terminal, the prompt, UI decorations and AI are disabled; lines are read byte by byte; on a syntax error the shell exits with status 2.
- **Context-aware, constrained prompt:** The working directory, the file names in it and the exit status are sent to the model; the model is asked to restrict its answer to the syntax SheLLM supports. Sending context can be disabled with `SHELLM_CONTEXT=0`.
- **Dangerous command warning:** For suggestions such as `rm`, `sudo`, `chmod -R`, `dd`, `mkfs`, `find -delete`, `| sh`, a red warning is shown and confirmation requires typing the full word (`evet` in the Turkish interface, `yes` in English).
- **Unsupported syntax warning:** If a suggestion contains an element SheLLM does not support, such as `;`, `&&`, `$(...)`, `2>`, a yellow warning is shown.
- **Offline test backend:** `SHELLM_BACKEND=mock` allows testing and demos without an API key (with a simple matcher that only corrects typos).
- **Diagnostic mode:** `./SheLLM --check "command"` prints the result of the suggestion's risk and syntax checks.
- **Robust protocol:** Single-line JSON request / tab-separated response, readiness check with `ping`, actual state on the status line (e.g. "AI connected (gemini-flash-latest)" or "AI off (GEMINI_API_KEY is not set)").
