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
"""Containers only: selected wherever the platform offers a `container` (the docker pack)."""

import http.client
import time

import score.itf as itf


@itf.requires("platform", shape=["container"])
@itf.requires("command")
def test_the_target_file_volume_is_mounted(target):
    assert target.command.exec("ls /extra/mount")[0] == 0


@itf.requires("platform", shape=["container"])
@itf.requires("command")
def test_renew_starts_from_a_clean_container(target):
    target.command.exec("touch /tmp/marker")
    old_id = target.platform.container.id
    target.renew("platform")
    assert target.platform.container.id != old_id
    assert target.command.exec("test -f /tmp/marker")[0] != 0


@itf.requires("platform", shape=["container"])
@itf.requires("command")
@itf.requires("process")
def test_early_output_is_not_lost_when_the_reply_is_read_late(target, monkeypatch):
    # A loaded host reads the reply late: the daemon then sends the response headers and the first output in one
    # burst, which http.client swallows into its read buffer. The docker pack's client still reads it.
    original = http.client.HTTPConnection.getresponse

    def late(self, *args, **kwargs):
        time.sleep(0.5)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(http.client.HTTPConnection, "getresponse", late)
    assert target.command.exec("echo Hello World!") == (0, b"Hello World!\n")
    process = target.process.spawn("sleep 0.3; echo first_application_log; sleep 5")
    try:
        assert process.pid() > 0 and process.is_running()
    finally:
        process.stop()
