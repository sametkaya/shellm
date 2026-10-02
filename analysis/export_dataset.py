#!/usr/bin/env python3
"""Exports the benchmark in plain tabular form to data/.

    data/tasks.csv                  the 400 tasks (sets A, B, E, C)
    data/guard_labels_dev.tsv       300 labeled NL2Bash commands (development sample)
    data/guard_labels_heldout.tsv   300 labeled NL2Bash commands (held-out sample)

The files are derived from tests/results/llm2_items.json, tests/results/llm2_scores.json
and tests/guard/*.json; running this script regenerates them byte for byte.
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
R = os.path.join(ROOT, "tests", "results")
G = os.path.join(ROOT, "tests", "guard")
OUT = os.path.join(ROOT, "data")

SOURCE = {"A": "generated typo (fixed seed 2026)",
          "B": "written by the authors (Turkish)",
          "E": "translation of set B (English)",
          "C": "NL2Bash sample (fixed seed 2026)"}
LANGUAGE = {"A": "-", "B": "tr", "E": "en", "C": "en"}
# Directories of the fixture (tests/llm_fixture.py) that can hold a requested file
FIXTURE_DIRS = ("belgeler", "eski", "gecici", "loglar", "projeler", "resimler")


def export_tasks():
    items = json.load(open(os.path.join(R, "llm2_items.json"), encoding="utf-8"))
    rows = json.load(open(os.path.join(R, "llm2_scores.json"), encoding="utf-8"))
    injection_ids = {r["id"] for r in rows if r["cond"] == "INJ"}
    path = os.path.join(OUT, "tasks.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["id", "set", "language", "source", "input", "reference", "typo_op",
                    "judge_check", "first_word_is_command", "subdir_not_named", "paired_id",
                    "in_injection_subset"])
        for it in items:
            s = it["set"]
            subdir = ""
            if s in "BE":
                dirs = [d for d in FIXTURE_DIRS if d + "/" in it["ref"]]
                subdir = int(bool(dirs) and not any(d in it["input"] for d in dirs))
            pair = {"B": "E", "E": "B"}.get(s)
            check = it.get("check") or "fs_only"
            w.writerow([it["id"], s, LANGUAGE[s], SOURCE[s], it["input"], it["ref"],
                        it.get("typo_op", "") if s == "A" else "", check,
                        int(bool(it.get("first_word_is_command"))), subdir,
                        (pair + it["id"][1:]) if pair else "", int(it["id"] in injection_ids)])
    return path


def export_labels(gold_file, result_file, out_name):
    gold = json.load(open(os.path.join(G, gold_file), encoding="utf-8"))
    res = json.load(open(os.path.join(G, result_file), encoding="utf-8"))
    flags = {}
    for variant in ("old", "new"):
        missed = {m[0] for m in res[variant].get("misses", [])}
        false_alarms = {m[0] for m in res[variant].get("false_alarms", [])}
        flags[variant] = {g["pid"]: int((g["label"] == 1 and g["pid"] not in missed)
                                        or (g["label"] == 0 and g["pid"] in false_alarms))
                          for g in gold}
        tp = sum(1 for g in gold if g["label"] == 1 and flags[variant][g["pid"]])
        fp = sum(1 for g in gold if g["label"] == 0 and flags[variant][g["pid"]])
        assert (tp, fp) == (res[variant]["all"]["tp"], res[variant]["all"]["fp"]), out_name
    path = os.path.join(OUT, out_name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["pid", "stratum", "command", "label", "class", "annotator1", "annotator2",
                    "flagged_old_rules", "flagged_revised_rules"])
        for g in gold:
            w.writerow([g["pid"], g["stratum"], g["cmd"], g["label"], g["cat"], g["a1"], g["a2"],
                        flags["old"][g["pid"]], flags["new"][g["pid"]]])
    return path


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for p in (export_tasks(),
              export_labels("nl2bash_gold.json", "nl2bash_guard_result.json", "guard_labels_dev.tsv"),
              export_labels("nl2bash_gold_test.json", "nl2bash_guard_result_test.json",
                            "guard_labels_heldout.tsv")):
        print("wrote", os.path.relpath(p, ROOT))
