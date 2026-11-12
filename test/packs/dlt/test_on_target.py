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
from score.itf.packs.dlt.on_target.providers import make_on_target
from score.itf.packs.dlt.on_target.receiver import DltOnTarget


class Handle:
    def __init__(self):
        self.running = True
        self.waited = False
        self.stopped = False

    def wait(self):
        self.waited = True

    def is_running(self):
        return self.running

    def stop(self):
        self.running = False
        self.stopped = True

    def get_output(self):
        return "captured"


class Files:
    def __init__(self):
        self.uploaded = None

    def upload(self, source, destination):
        self.uploaded = (source, destination)


class Process:
    def __init__(self):
        self.calls = []
        self.handles = []

    def spawn(self, binary, args=None):
        handle = Handle()
        self.calls.append((binary, args or []))
        self.handles.append(handle)
        return handle


def test_nothing_is_uploaded_until_the_first_start():
    files, process = Files(), Process()
    DltOnTarget(files, process)
    assert files.uploaded is None and process.calls == []


def test_start_uploads_the_tool_once_runs_a_receiver_and_stops_it():
    files, process = Files(), Process()
    receivers = DltOnTarget(files, process, {"binary_path": "custom-dlt-receive"})
    with receivers.start("tcp", target_ip="192.0.2.8", output_file="/tmp/custom.dlt") as receiver:
        assert files.uploaded == ("custom-dlt-receive", "/tmp/dlt-receive")
        assert process.handles[0].waited
        assert receiver.dlt_file == "/tmp/custom.dlt"
        assert receiver.get_output() == "captured"
        assert process.calls[1] == (
            "/tmp/dlt-receive",
            ["--tcp", "192.0.2.8", "-o", "/tmp/custom.dlt", "-a", "--stdout-flush"],
        )
    assert process.handles[1].stopped
    with receivers("udp"):  # called like the original fixture
        pass
    assert len([call for call in process.calls if call[0] == "chmod"]) == 1


def test_teardown_stops_receivers_left_running():
    files, process = Files(), Process()
    roles = make_on_target(files, process, {})
    receivers = next(roles)
    receivers.start("udp", multicast_ips=["224.0.0.1"]).__enter__()
    assert "--mcast-ip" in process.calls[1][1]
    roles.close()
    assert process.handles[1].stopped
