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
from score.itf.plugins.docker import _LineAssembler


def _collect():
    emitted = []
    return emitted, _LineAssembler(emitted.append)


def test_complete_lines_in_single_chunk_are_emitted_individually():
    emitted, assembler = _collect()
    assembler.feed("line1\nline2\nline3\n")
    assert emitted == ["line1", "line2", "line3"]


def test_line_split_across_chunks_is_emitted_once():
    """Regression: a single line arriving in two chunks must not be split.

    Mirrors the observed DLT output where a chunk boundary fell mid-line
    and produced two separate log records.
    """
    emitted, assembler = _collect()
    assembler.feed("LM log fatal verbose 3")
    assert emitted == []  # no newline yet, nothing emitted
    assembler.feed(" clock() at failed initial state transition: 38.712000 ms\n")
    assert emitted == ["LM log fatal verbose 3 clock() at failed initial state transition: 38.712000 ms"]


def test_partial_line_is_held_until_newline():
    emitted, assembler = _collect()
    assembler.feed("partial")
    assert emitted == []
    assembler.feed(" still partial")
    assert emitted == []
    assembler.feed("\n")
    assert emitted == ["partial still partial"]


def test_flush_emits_trailing_unterminated_line():
    emitted, assembler = _collect()
    assembler.feed("no trailing newline")
    assert emitted == []
    assembler.flush()
    assert emitted == ["no trailing newline"]


def test_flush_without_buffered_data_emits_nothing():
    emitted, assembler = _collect()
    assembler.feed("done\n")
    assembler.flush()
    assert emitted == ["done"]


def test_blank_lines_are_skipped():
    emitted, assembler = _collect()
    assembler.feed("a\n\n\nb\n")
    assert emitted == ["a", "b"]


def test_carriage_returns_are_stripped():
    emitted, assembler = _collect()
    assembler.feed("windows\r\nunix\n")
    assert emitted == ["windows", "unix"]


def test_byte_at_a_time_reassembles_full_line():
    emitted, assembler = _collect()
    for ch in "hello world\n":
        assembler.feed(ch)
    assert emitted == ["hello world"]
