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
import pytest

from score.itf.packs.pcap.capture import TcpdumpCapture


def test_failed_capture_start_can_be_torn_down_without_a_second_failure(tmp_path):
    capture = TcpdumpCapture(
        {
            "interface": "lo",
            "out_dir": str(tmp_path),
            "binary_path": str(tmp_path / "missing-tcpdump"),
        }
    )
    with pytest.raises(FileNotFoundError):
        capture.start()
    capture.stop()
    assert not capture.running()


def test_capture_waits_for_tcpdump_to_create_its_output(tmp_path, monkeypatch):
    class Process:
        def __init__(self, _binary, args, **_kwargs):
            self.output_path = args[args.index("-w") + 1]
            self.alive = True

        def start_process(self):
            open(self.output_path, "wb").close()

        def is_running(self):
            return self.alive

        def output(self):
            return ""

        def kill_process(self):
            self.alive = False

    monkeypatch.setattr("score.itf.packs.pcap.capture.ProcessWrapper", Process)
    capture = TcpdumpCapture({"interface": "lo", "out_dir": str(tmp_path), "binary_path": "tcpdump"})

    capture.start()

    assert capture.running()
    capture.stop()


def test_capture_reports_tcpdump_startup_errors(tmp_path, monkeypatch):
    class Process:
        def __init__(self, *_args, **_kwargs):
            self.alive = True
            self.stopped = False

        def start_process(self):
            self.alive = False

        def is_running(self):
            return self.alive

        def output(self):
            return "tcpdump: permission denied (CAP_NET_RAW required)"

        def kill_process(self):
            self.stopped = True

    monkeypatch.setattr("score.itf.packs.pcap.capture.ProcessWrapper", Process)
    capture = TcpdumpCapture({"interface": "lo", "out_dir": str(tmp_path), "binary_path": "tcpdump"})

    with pytest.raises(RuntimeError, match="CAP_NET_RAW"):
        capture.start()

    assert not capture.running()
