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
"""ICMP echo without a ping binary, and the fallbacks when the kernel refuses ICMP sockets."""

import socket
import struct

import pytest

from score.itf.packs.ping.icmp import probe as icmp
from score.itf.packs.ping.icmp.monitor import Pinger, checked_host


def test_echo_request_carries_a_valid_checksum():
    packet = icmp.echo_request(0x1234, 7)
    kind, code, _, identifier, sequence = struct.unpack("!BBHHH", packet[:8])
    assert (kind, code, identifier, sequence) == (icmp.ECHO_REQUEST, 0, 0x1234, 7)
    assert icmp.checksum(packet) == 0, "a packet including its checksum sums to zero"


def test_loopback_answers():
    if icmp._open_socket() is None:
        pytest.skip("this host permits neither datagram nor raw ICMP sockets")
    assert icmp.ping("127.0.0.1", timeout=2)


def test_falls_back_to_the_binary_when_no_socket_is_permitted(mocker):
    mocker.patch.object(icmp, "_open_socket", return_value=None)
    mocker.patch.object(icmp.shutil, "which", return_value="/usr/bin/ping")
    run = mocker.patch.object(icmp.ProcessWrapper, "run", return_value=(0, "", ""))
    assert icmp.ping("127.0.0.1")
    assert run.call_args[0][0] == "ping"


def test_without_socket_or_binary_it_says_what_to_grant(mocker):
    mocker.patch.object(icmp, "_open_socket", return_value=None)
    mocker.patch.object(icmp.shutil, "which", return_value=None)
    with pytest.raises(RuntimeError, match="ping_group_range"):
        icmp.ping("127.0.0.1")


def test_an_unresolvable_host_does_not_answer(mocker):
    mocker.patch.object(icmp.socket, "gethostbyname", side_effect=socket.gaierror)
    assert not icmp.ping("no-such-host.invalid")


class _Endpoint:
    host = "192.0.2.1"


def test_wait_up_and_down_poll_until_the_answer_changes(mocker):
    answers = iter([False, False, True])
    mocker.patch.object(icmp, "ping", side_effect=lambda *a: next(answers))
    pinger = Pinger(_Endpoint(), {"interval": 0.01, "boot_timeout": 5})
    assert pinger.wait_up()
    mocker.patch.object(icmp, "ping", return_value=True)
    assert not pinger.wait_down(timeout=0.05)


@pytest.mark.parametrize("host", ["10.0.0.1", "ecu.local", "fe80::1"])
def test_valid_targets(host):
    assert checked_host(host) == host


@pytest.mark.parametrize("host", ["-c 5 x", "a;b", ""])
def test_option_like_targets_are_rejected(host):
    with pytest.raises(ValueError):
        checked_host(host)
