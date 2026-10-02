# -*- coding: utf-8 -*-
"""Shared path settings for the experiment scripts.

Default directory layout:
    <repo>/                   SheLLM ("v2" in the scripts), built with make
    <repo>/tests/             these scripts
    <repo>/../SheLLM/SheLLM   optional: the student team's first prototype ("v1"),
                              needed only for the v1 comparisons
For a different layout, set the environment variables:
    SHELLM_V1_DIR, SHELLM_V2_DIR, SHELLM_ASAN_DIR, NL2BASH_CM
"""
import os

# The shell's interface is bilingual (English by default, Turkish when
# SHELLM_LANG=tr). The scripts match English interface text and store English
# risk reasons, so pin the language to English regardless of the locale.
os.environ.setdefault("SHELLM_LANG", "en")
# The experiments never want the first-start setup wizard of the installable
# release; shells started by the test scripts skip it.
os.environ.setdefault("SHELLM_NO_SETUP", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
V2_DIR = os.path.abspath(os.environ.get("SHELLM_V2_DIR", os.path.join(HERE, "..")))
V1_DIR = os.path.abspath(os.environ.get("SHELLM_V1_DIR",
                                        os.path.join(HERE, "..", "..", "SheLLM", "SheLLM")))
# AddressSanitizer builds (created by build_asan.sh)
ASAN_DIR = os.path.abspath(os.environ.get("SHELLM_ASAN_DIR", "/tmp/shellm_asan"))
V1_BIN = os.path.join(V1_DIR, "SheLLM")
V2_BIN = os.path.join(V2_DIR, "SheLLM")
V1_ASAN_BIN = os.path.join(ASAN_DIR, "v1", "SheLLM")
V2_ASAN_BIN = os.path.join(ASAN_DIR, "v2", "SheLLM")
# v1 looks for ai_helper.py in its working directory, so v1 scenarios are run
# in this directory, which holds a mock helper that imitates the v1 protocol.
V1_MOCK_DIR = os.path.join(HERE, "v1_mock")
RESULTS = os.path.join(HERE, "results")
NL2BASH_CM = os.environ.get("NL2BASH_CM", os.path.join(HERE, "data", "all.cm"))
os.makedirs(RESULTS, exist_ok=True)
