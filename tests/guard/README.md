# Guard (risk checker) evaluation

Data and scripts for the guard measurements in the papers.

## Method

1. `rubric.md` defines "risky" in five classes (DEL, OVW, PRIV, SYS, NET). It was written before the rules were revised.
2. **Development sample** (`nl2bash_pool.json`, 300 commands): 150 random NL2Bash commands and 150 commands that contain a token that may signal risk.
   - Two independent annotators labeled the sample without seeing the rules (`annotate_input.txt` → `annot_1.tsv`, `annot_2.tsv`).
   - Agreement κ = 0.97; the 3 disagreements were resolved according to the rubric (`nl2bash_gold.json`).
   - The revised rules were developed by examining the misses in this sample.
3. The revised rules were frozen. `ai_risk_frozen.c` is that file, kept byte for byte, and `rules_frozen.sha256` holds the hash recorded at that moment. Its comments and messages are in Turkish, as in the evaluated version. The current `ai_risk.c` has the same logic with bilingual messages (identical decisions on all 1,817 evaluation commands).
4. **Held-out sample** (`nl2bash_pool_test.json`, 300 commands, disjoint from the development sample) was labeled the same way (`annotate_input_test.txt` → `annot_test_*.tsv`; κ = 0.93, 8 disagreements resolved, `nl2bash_gold_test.json`).
5. `nl2bash_guard_eval.py <shell binary> <gold file>` computes recall and precision of the old and the revised rules → `nl2bash_guard_result*.json`.

Result on the held-out sample:

- The old rules flag 26 of the 76 risky commands (34%); the revised rules flag 62 of 76 (82%).
- The revised rules raise 2 false alarms among the 224 safe commands (precision 97%).

`categories.py <shell binary>` is a coverage test for the harmful patterns listed in the threat model and for similar harmless commands → `categories_result.json`. It is not a measure of generalization.

For the execution-based measurement, see `../guard_exec_eval.py`.

## Old rules

`ai_guard_old.c` contains the rules before the revision. `make legacy-guard` (in the repository root) links them into the current shell as `tests/guard/shellm_old_guard`. The scripts use that binary as the "old" rules; `SHELLM_OLD_BIN` overrides it. On 4,468 commands this build gives the same risk and syntax decisions as the original pre-revision release.

The scripts pin the English interface (`SHELLM_LANG=en`), so the risk reasons in the result files are in English.

## Annotators

The annotators were two separate instances of a large language model (Claude). Each saw only the rubric and the commands, not the rules and not the other's labels.
