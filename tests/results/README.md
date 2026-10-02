# Recorded results

Raw results of all experiments, as written by the scripts in `tests/` (runs of 30 September and 1 October 2026). `analysis/` derives every number, table and figure of the papers from these files.

## Files

| File | Written by | Content |
|---|---|---|
| `bash.json`, `bash_holdout.json` | `run_tests.py --impl bash` | Bash outputs of the conformance suites (reference) |
| `v2.json`, `v2_holdout.json` | `run_tests.py --impl v2` | SheLLM outputs of the same suites |
| `v1*.json` | `run_tests.py --impl v1` | Outputs of the student prototype |
| `*.vg.json`, `valgrind_summary.json` | `run_tests.py --valgrind`, `vg_summary.py` | Valgrind runs |
| `*asan*.json` | `run_tests.py --impl v1asan/v2asan` | AddressSanitizer and UBSan builds |
| `scenarios.json`, `scenarios_run{1,2,3}.json` | `scenarios.py` | AI-bridge scenarios S1–S16 (earlier runs covered S1–S10) |
| `bench.json` | `bench.py` | Per-command cost, start-up time, suggestion overhead |
| `heredoc_race.json`, `heredoc_race_repeats.json` | `heredoc_race.py` | Concurrent here-document test |
| `nl2bash_coverage.json` | `nl2bash_coverage.py` | Share of NL2Bash commands within SheLLM's grammar |
| `llm_items.json`, `llm_responses.jsonl`, `llm_scores.json`, `llm_summary.json` | `llm_eval.py` | First Gemini run on sets A, B, C; imported by `llm_eval2.py` as run 1 |
| `llm2_items.json` | `llm_eval2.py prepare` | The 400 tasks with reference results |
| `llm2_responses.jsonl` | `llm_eval2.py query` | All 9,700 model responses: raw text, latency, token usage, model version |
| `llm2_scores.json` | `llm_eval2.py score` | Each response executed and judged; risk and syntax checks |
| `llm2_summary.json` | `llm_eval2.py summary` | Accuracy per cell, McNemar tests, Holm adjustment, repetitions |
| `baselines*_scores.json`, `baselines*_summary.json` | `baselines.py`, `baselines2.py`, `baselines_nl.py` | thefuck, nearest-name matcher, zsh `CORRECT`, frequency matcher |
| `trigger_coverage.json`, `trigger_coverage_summary.json` | `trigger_coverage.py` | Which inputs open a suggestion (old rule, new rule, `#` prefix) |
| `guard_exec.json`, `guard_exec_summary.json` | `guard_exec_eval.py` | All 1,107 distinct suggestions for sets A, B, E executed; data loss and guard decisions |
| `secret_eval.json` | `secret_eval.py` | Secret filter on synthetic credentials, the task inputs, and NL2Bash |
| `gemini_paid_tier_start.txt` | — | When the Gemini runs switched from the free to the paid tier |
| `fuzz_campaign.log` | `tests/fuzz/build_fuzz.sh` | libFuzzer campaign after the use-after-free fix; the crash that found the bug is in `tests/fuzz/found/` |

The guard results on labeled NL2Bash commands are in `tests/guard/` (`nl2bash_guard_result*.json`, `categories_result.json`).

## Conditions and identifiers

- **Providers and models:** `gemini` (`gemini-3.5-flash-lite`), `anthropic` (`claude-haiku-4-5-20251001`), `openai` (`gpt-5.4-mini-2026-03-17`), `local` (Qwen2.5-Coder 1.5B Instruct, Q4_K_M).
- **Prompt conditions:**

  | Condition | Prompt |
  |---|---|
  | `V1` | Baseline prompt |
  | `C1K1` | SheLLM prompt (context and grammar constraints) |
  | `C0K1` | Ablation: constraints only |
  | `C1K0` | Ablation: context only |
  | `C0K0` | Ablation: neither |
  | `INJ` | SheLLM prompt with injected file names |

- **Repetitions:** `rep` is 1–3.

## Language of the recorded messages

The original runs used SheLLM's Turkish interface. Labels and shell messages in these files were converted 1:1 to the English messages of the current interface:

- risk and syntax reasons;
- typo-operation labels;
- data-loss labels;
- benchmark and scenario names;
- the helper's two error texts.

The rules and the judging are unchanged. Re-running the scripts, which now pin the English interface, reproduces `guard_exec*.json`, `secret_eval.json` and the result files in `tests/guard/` byte for byte, and the recorded outcomes of `scenarios.json` and `trigger_coverage.json`.

Task inputs, references, model responses and test outputs are recorded as they were. They include the Turkish requests of set B and the Turkish file names of the fixture.
