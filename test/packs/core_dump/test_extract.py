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
"""Core dump extraction through the command and file-transfer contracts."""

from score.itf.packs.core_dump import plugin
from score.itf.packs.core_dump.collector import CoreDumpCollector
from score.itf.packs.core_dump.extract import LIST_CORES, extract_core_dumps
from score.itf.packs.core_dump.providers import make_collector


class _Command:
    def __init__(self, listing: str):
        self.listing = listing
        self.ran = []

    def exec(self, command, timeout=30.0):
        self.ran.append(command)
        return 0, self.listing.encode("utf-8")


class _Files:
    def __init__(self, failing=()):
        self.downloaded = []
        self.failing = failing

    def download(self, remote, local):
        if remote in self.failing:
            raise OSError("gone")
        self.downloaded.append((remote, local))


def test_found_cores_are_mirrored_under_the_output_dir(tmp_path):
    command, files = _Command("/tmp/core.123\n/opt/app/app.core\n"), _Files()
    extracted = extract_core_dumps(command, files, str(tmp_path))
    assert command.ran == [LIST_CORES]
    assert files.downloaded == [
        ("/tmp/core.123", str(tmp_path / "tmp/core.123")),
        ("/opt/app/app.core", str(tmp_path / "opt/app/app.core")),
    ]
    assert extracted == [local for _, local in files.downloaded]


def test_a_failed_download_does_not_stop_the_others(tmp_path):
    files = _Files(failing={"/tmp/core.1"})
    extracted = extract_core_dumps(_Command("/tmp/core.1\n/tmp/core.2\n"), files, str(tmp_path))
    assert extracted == [str(tmp_path / "tmp/core.2")]


def test_paths_escaping_the_output_dir_are_skipped(tmp_path):
    files = _Files()
    assert extract_core_dumps(_Command("/../../etc/passwd\n"), files, str(tmp_path)) == []
    assert files.downloaded == []


class _ContentFiles(_Files):
    def __init__(self, content, failing=()):
        super().__init__(failing)
        self.content = content

    def download(self, remote, local):
        super().download(remote, local)
        with open(local, "wb") as destination:
            destination.write(self.content[remote])


def test_collector_is_explicit_and_starts_no_collection_on_construction(tmp_path):
    command = _Command("/tmp/core.1\n")
    files = _ContentFiles({"/tmp/core.1": b"first crash"})
    collector = make_collector(command, files)
    assert isinstance(collector, CoreDumpCollector)
    assert command.ran == []
    assert files.downloaded == []
    assert collector.collect(str(tmp_path)) == [str(tmp_path / "tmp/core.1")]
    assert (tmp_path / "tmp/core.1").read_bytes() == b"first crash"


def test_repeated_collection_reports_only_new_or_changed_dumps(tmp_path):
    command = _Command("/tmp/core.1\n")
    files = _ContentFiles({"/tmp/core.1": b"first crash"})
    collector = make_collector(command, files)
    assert len(collector.collect(str(tmp_path / "test-1"))) == 1
    assert collector.collect(str(tmp_path / "test-2")) == []
    files.content["/tmp/core.1"] = b"second crash at the same path"
    assert collector.collect(str(tmp_path / "test-3")) == [str(tmp_path / "test-3/tmp/core.1")]
    command.listing += "/tmp/core.2\n"
    files.content["/tmp/core.2"] = b"new dump"
    assert collector.collect(str(tmp_path / "test-4")) == [str(tmp_path / "test-4/tmp/core.2")]
    assert (tmp_path / "test-1/tmp/core.1").read_bytes() == b"first crash"


def test_failed_downloads_are_retried_and_do_not_hide_other_dumps(tmp_path):
    files = _ContentFiles({"/tmp/core.1": b"one", "/tmp/core.2": b"two"}, failing={"/tmp/core.1"})
    collector = make_collector(_Command("/tmp/core.1\n/tmp/core.2\n"), files)
    assert collector.collect(str(tmp_path)) == [str(tmp_path / "tmp/core.2")]
    files.failing = ()
    assert collector.collect(str(tmp_path)) == [str(tmp_path / "tmp/core.1")]


def test_sibling_prefix_paths_cannot_escape_output_directory(tmp_path):
    files = _Files()
    escaped = f"/../{tmp_path.name}-outside/core"
    assert extract_core_dumps(_Command(escaped), files, str(tmp_path)) == []
    assert files.downloaded == []


def test_collector_cannot_write_through_output_symlink(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (output / "tmp").symlink_to(outside, target_is_directory=True)
    collector = make_collector(_Command("/tmp/core.1\n"), _ContentFiles({"/tmp/core.1": b"dump"}))
    assert collector.collect(str(output)) == []
    assert list(outside.iterdir()) == []


def test_pack_registers_only_factories_and_no_automatic_teardown():
    assert plugin.pytest_plugins == ["score.itf.packs.core_dump.providers"]
    assert not hasattr(plugin, "itf_teardown")
