# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************
"""Vocabulary gate over ITF core: `score.itf.core/` excluding `score.itf.core/octo` and `score.itf.core/adapters`."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).absolute().parents[3]
ITF_DIR = ROOT / "score" / "itf" / "core"
WORDLIST_PATH = ROOT / "tools" / "gates" / "itf_banned_words.txt"
# The original API's module paths (score.itf.core.com, .target, .utils): re-exports of the packs and of
# score.itf.compat, kept for existing tests; //test/integration/legacy:shims_test checks they hold nothing else.
COMPATIBILITY_SHIMS = ("com", "target", "utils")


def _itf_core_py_files():
    files = []
    for path in sorted(ITF_DIR.rglob("*.py")):
        rel = path.relative_to(ITF_DIR)
        parts = rel.parts
        if parts[0] in ("octo", "adapters") or parts[0] in COMPATIBILITY_SHIMS:
            continue
        files.append(path)
    return files


def _banned_words() -> list[str]:
    return [w.strip() for w in WORDLIST_PATH.read_text().splitlines() if w.strip()]


def _find_banned(text: str, words: list[str]) -> list[str]:
    hits = []
    for w in words:
        if re.search(rf"\b{re.escape(w)}\b", text, re.IGNORECASE):
            hits.append(w)
    return hits


def test_itf_core_source_has_no_banned_words():
    words = _banned_words()
    offenders = {}
    for path in _itf_core_py_files():
        hits = _find_banned(path.read_text(), words)
        if hits:
            offenders[str(path)] = hits
    assert not offenders, f"banned words found: {offenders}"


def test_itf_core_excludes_octo_and_adapters():
    files = _itf_core_py_files()
    for path in files:
        rel = path.relative_to(ITF_DIR)
        assert rel.parts[0] not in ("octo", "adapters")
    assert files, "expected score.itf.core/ to contain files outside octo/ and adapters/"
