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
"""dlt-receive run on the target itself, through the dlt_on_target role (ITF's former tests)."""

import time

import score.itf as itf

SECRET = "dlt_on_target_secret_payload"


def send(target):
    target.command.exec(f"echo -n {SECRET} | /usr/bin/dlt-adaptor-stdin")


@itf.requires("command")
@itf.requires("dlt_on_target")
def test_receives_over_tcp(target):
    with target.dlt_on_target.start("tcp") as receiver:
        time.sleep(1)
        send(target)
        time.sleep(1)
    assert SECRET in receiver.get_output()
    assert target.command.exec(f"test -f {receiver.dlt_file}")[0] == 0


@itf.requires("command")
@itf.requires("dlt_on_target")
def test_receives_over_udp_multicast(target):
    with target.dlt_on_target.start("udp", multicast_ips=["224.0.0.1"]) as receiver:
        time.sleep(1)
        send(target)
        time.sleep(1)
    assert SECRET in receiver.get_output()


@itf.requires("command")
@itf.requires("dlt_on_target")
def test_receivers_stop_when_their_block_ends(target):
    with target.dlt_on_target.start("tcp") as receiver:
        assert receiver.is_running()
    assert not receiver.is_running()


@itf.requires("command")
@itf.requires("dlt_on_target")
def test_a_custom_output_file_is_used(target):
    with target.dlt_on_target.start("tcp", output_file="/tmp/custom_trace.dlt") as receiver:
        pass
    assert receiver.dlt_file == "/tmp/custom_trace.dlt"


@itf.requires("command")
@itf.requires("dlt_on_target")
def test_several_receivers_run_at_once(target):
    with (
        target.dlt_on_target.start("tcp") as tcp,
        target.dlt_on_target.start("udp", multicast_ips=["224.0.0.1"]) as udp,
    ):
        time.sleep(1)
        send(target)
        time.sleep(1)
    assert SECRET in tcp.get_output() and SECRET in udp.get_output()
