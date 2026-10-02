# SheLLM — a Unix shell with language-model command suggestions

SheLLM is a small Unix shell written in C that asks a large language model (Gemini, Claude, GPT, or a local model) for help **only when the interpreter itself fails**:

- it cannot resolve a command name in any stage of a pipeline (`grpe x | wc -l`);
- it cannot parse a line because of an unmatched quote, for example a Turkish apostrophe (`notlar.txt'yi sil`);
- the line starts with `# ` (an explicit request, never executed).

The model proposes **one** command. SheLLM checks it for risky operations and unsupported syntax, shows it, and runs it with its own parser and executor only after you confirm. Risky suggestions need the full word `yes`.

```text
🎀 sheLLM mkdr backup
shellm: mkdr: command not found

  ┃ ◆ shellm suggestion
  ┃ mkdir backup
  ┃
  ┃ [y] run   [n] skip
```

SheLLM grew out of a student project supported by TÜBİTAK (2209-A programme, project no. 1919B012531262). This repository contains the shell, its installer, and the complete replication package of the accompanying research: test suites, benchmark tasks, guard labels, all recorded model responses, and the analysis scripts.

## Quick start

```bash
# Ubuntu / Debian / WSL on Windows
sudo apt install build-essential libreadline-dev python3
git clone https://github.com/sametkaya/shellm.git && cd shellm
./install.sh          # builds and installs ~/.local/bin/shellm (no sudo needed)
shellm                # the setup wizard opens on first start
```

A prebuilt Debian package is attached to each [release](https://github.com/sametkaya/shellm/releases) (`sudo apt install ./shellm_1.0.0_amd64.deb`). See **[INSTALL.md](INSTALL.md)** for the full guide, including Windows (WSL), local models with Ollama, and troubleshooting. A Turkish translation is in [docs/INSTALL.tr.md](docs/INSTALL.tr.md).

## Using SheLLM

```bash
shellm                       # uses the model from ~/.config/shellm/config
shellm --setup               # change provider, key, model or interface language
GEMINI_API_KEY=... shellm    # environment variables take precedence over the settings file
SHELLM_BACKEND=mock shellm   # no model: simple typo correction only
SHELLM_LANG=tr shellm        # Turkish interface
shellm --check 'rm -rf ~/old'   # show the risk, syntax and secret checks for a command
```

| You type | What happens |
|---|---|
| `mkdr backup` | Command not found → suggestion `mkdir backup` |
| `list the txt files in the belgeler folder` | Natural-language request → `ls belgeler/*.txt` |
| `notlar.txt'yi sil` | Turkish request with an apostrophe still reaches the model; deletion is flagged as risky |
| `# find all python files` | Explicit request: the line is not run but sent to the model |

**Confirming:** `y` (or `e`) runs an ordinary suggestion; a risky one (deletion, overwriting, permission changes, piping downloads into a shell, …) runs only after `yes` (or `evet`). Any other answer skips it and leaves `$?` unchanged.

**Privacy:** lines that look like they contain a password, key or token are never sent. For hosted models, the failed line, the working directory and up to 50 file names in it are sent (the file names can be switched off); file contents never are. API keys are read only by the helper process and are removed from the environment of programs the shell starts.

**Supported syntax:** simple commands, pipelines `|`, redirections `<`, `>`, `>>`, `<<`, single and double quotes, `$VAR` and `$?`, `~`, wildcards `*`, `?`, `[...]`, and the built-ins `echo`, `cd`, `pwd`, `export`, `unset`, `env`, `exit`. Not supported: `;`, `&&`, `||`, `&`, `$(...)`, backquotes, subshells, brace expansion, `2>`, backslash escapes. SheLLM is a teaching shell; do not use it as your login shell.

### Configuration

Settings live in `~/.config/shellm/config` (`KEY=value` lines, mode 0600, written by `shellm --setup`). Environment variables override them.

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | Provider API keys | — |
| `SHELLM_BACKEND` | `gemini`, `anthropic`, `openai`, `local`, or `mock` | first provider with a key |
| `SHELLM_MODEL` | Model name | `gemini-flash-lite-latest`, `claude-haiku-4-5`, `gpt-5.4-mini` |
| `SHELLM_LOCAL_URL` | OpenAI-compatible local server (Ollama, llama.cpp) | `http://127.0.0.1:8080/v1` |
| `SHELLM_LANG` | Interface language: `en` or `tr` | settings file, then locale, else English |
| `SHELLM_CONTEXT` | `0`: do not send directory context | `1` |
| `SHELLM_AI_TIMEOUT` | Suggestion timeout in seconds | `20` |
| `SHELLM_AI` | `0`: AI completely off | — |
| `SHELLM_KEEP_KEYS` | Keep API keys in the environment of child processes | — |
| `SHELLM_KEEP_LOG` | Keep the helper's log | — |
| `SHELLM_HELPER` | Custom path to `ai_helper.py` (development) | — |
| `SHELLM_NO_SETUP` | Do not open the setup wizard on first start | — |

The helper `ai_helper.py` is looked up in `SHELLM_HELPER`, next to the executable, in `../share/shellm/`, and in the data directory given at build time — never in the current directory.

## Repository layout

```text
*.c, minishell.h, ast/ builtins/ env/ parse/ pipes/ redir/ signal/ tokens/ libft/
                      the shell (C)
ai_client.c           bridge to the helper process (private Unix socket)
trigger.c             trigger rules and the secret filter
ai_risk.c, ai_guard.c risk rules and unsupported-syntax check
ai_helper.py          helper process: prompt, providers (Gemini, Anthropic, OpenAI, local)
shellm_setup.py       setup wizard
install.sh, packaging/  installer and Debian package script
docs/                 translated installation guide
data/                 the benchmark in tabular form (tasks, guard labels)
tests/                conformance tests, scenarios, experiment scripts
tests/guard/          guard evaluation: rubric, labels, old and frozen rules
tests/results/        recorded results of all experiments
analysis/             scripts that regenerate the numbers, tables and figures of the papers
```

## Tests

```bash
make test                         # SheLLM vs. Bash on the main and hold-out suites
cd tests && python3 scenarios.py  # 16 AI-bridge scenarios (needs pexpect)
```

The conformance suites run every test script in Bash and in SheLLM and compare standard output, exit status and the presence of standard error: 134/134 tests of the main suite and 57/57 of the hold-out suite agree on the supported grammar.

## Reproducing the research

The experiments are described in two papers (see [Citation](#citation)). All raw results are in `tests/results/` (described in [tests/results/README.md](tests/results/README.md)); the benchmark is also exported to `data/` ([data/README.md](data/README.md)).

```bash
# Regenerate all numbers, tables and figures from the recorded results
python3 analysis/journal_stats.py && python3 analysis/journal_tables.py
python3 analysis/journal_figures.py          # needs matplotlib
python3 analysis/conference_tables.py
python3 analysis/export_dataset.py           # rewrites data/
```

To re-run experiments (Linux, as root). Suggestions are executed by an unprivileged account named `kullanici` in the fixture directory `/home/kullanici/Masaustu/calisma`; both names are part of the benchmark (they appear in the prompt context), so create the account first with `useradd -m kullanici`.

```bash
make && make legacy-guard                    # current shell and the pre-revision guard rules
sh tests/data/fetch_nl2bash.sh               # NL2Bash corpus (not redistributed here)
cd tests
python3 llm_eval.py prepare && python3 llm_eval2.py prepare
python3 llm_eval2.py query --provider gemini --model gemini-3.5-flash-lite --plan gemini
python3 llm_eval2.py score && python3 llm_eval2.py summary
python3 baselines.py run && python3 baselines2.py run && python3 baselines_nl.py
python3 trigger_coverage.py                  # which inputs reach the assistant
python3 guard_exec_eval.py                   # guard on executed suggestions
python3 secret_eval.py                       # secret filter
(cd guard && python3 nl2bash_guard_eval.py ../../SheLLM nl2bash_gold_test.json)
python3 run_tests.py --impl v2 --valgrind && python3 vg_summary.py v2
python3 bench.py && python3 heredoc_race.py
```

Model queries need the provider's API key in the environment and cost a few US dollars for the full plan. Comparisons with the student prototype (`v1`) need that prototype built in `../SheLLM/SheLLM`; they are skipped otherwise. The "old" trigger rule in `trigger_coverage.py` needs a build of the pre-revision release (`SHELLM_OLD_BIN`).

## Citation

The system and its verification, and the multi-model, bilingual evaluation, are described in two papers that are currently under review. Citation details will be added once they are published.

## License

The license has not been chosen yet. Note that SheLLM links against GNU Readline, which is licensed under GPL-3.0-or-later, and that the NL2Bash corpus used by the experiments is distributed under GPL-3.0.
