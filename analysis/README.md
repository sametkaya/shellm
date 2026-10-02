# Analysis scripts

These scripts read only the recorded results in `tests/results/` and `tests/guard/` and write to `analysis/output/` (not tracked by git).

| Script | Output | Purpose |
|---|---|---|
| `journal_stats.py` | `output/journal/analysis.json` | Wilson intervals, error categories, latency, token usage, cost, risky and unsupported shares |
| `journal_tables.py` | `output/journal/numbers_j.tex`, `tab_*.tex`, `journal_numbers.json` | All numbers and tables of the journal article (run `journal_stats.py` first) |
| `journal_figures.py` | `output/journal/fig_accuracy.*`, `fig_latency.*` | Figures of the journal article (needs matplotlib) |
| `conference_tables.py` | `output/conference/numbers.tex`, `tab_*.tex` | Numbers and tables of the conference paper |
| `export_dataset.py` | `data/*.csv`, `data/*.tsv` | Tabular export of the benchmark |

Statistics:

- Paired comparisons use the exact McNemar test.
- Families of tests are Holm-adjusted.
- Proportions are given with Wilson 95% intervals.
- Inter-annotator agreement is Cohen's κ.

Costs use the providers' list prices of 1 October 2026 (per million input/output tokens):

| Model | Input | Output |
|---|---|---|
| Gemini 3.5 Flash-Lite | $0.30 | $2.50 |
| Claude Haiku 4.5 | $1 | $5 |
| GPT-5.4 mini | $0.75 | $4.50 |
