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
"""One ICMP echo using a datagram socket, raw socket or system ping fallback."""

from __future__ import annotations

import os
import select
import shutil
import socket
import struct
import subprocess
import time

from score.itf.core.process import ProcessWrapper

ECHO_REQUEST, ECHO_REPLY = 8, 0


def checksum(data: bytes) -> int:
    if len(data) % 2:
        data += b"\0"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return ~total & 0xFFFF


def echo_request(identifier: int, sequence: int, payload: bytes = b"score-itf") -> bytes:
    header = struct.pack("!BBHHH", ECHO_REQUEST, 0, 0, identifier, sequence)
    return struct.pack("!BBHHH", ECHO_REQUEST, 0, checksum(header + payload), identifier, sequence) + payload


def _open_socket() -> tuple[socket.socket, bool] | None:
    """(socket, replies carry an IP header) or None when neither socket kind is permitted."""
    for kind, raw in ((socket.SOCK_DGRAM, False), (socket.SOCK_RAW, True)):
        try:
            return socket.socket(socket.AF_INET, kind, socket.IPPROTO_ICMP), raw
        except (PermissionError, OSError):
            continue
    return None


def _ping_socket(sock: socket.socket, raw: bool, address: str, timeout: float) -> bool:
    identifier, sequence = os.getpid() & 0xFFFF, int(time.monotonic() * 1000) & 0xFFFF
    sock.sendto(echo_request(identifier, sequence), (address, 0))
    deadline = time.monotonic() + timeout
    while (remaining := deadline - time.monotonic()) > 0:
        if not select.select([sock], [], [], remaining)[0]:
            return False
        packet, (sender, _) = sock.recvfrom(2048)
        if raw:
            packet = packet[(packet[0] & 0x0F) * 4 :]
        if len(packet) < 8 or sender != address:
            continue
        kind, _, _, _, reply_sequence = struct.unpack("!BBHHH", packet[:8])
        # A datagram socket's kernel rewrites the identifier, so only the sequence is compared.
        if kind == ECHO_REPLY and reply_sequence == sequence:
            return True
    return False


def _ping_binary(binary: str, host: str, timeout: float) -> bool:
    windows = os.name == "nt"
    wait = str(int(timeout * 1000)) if windows else str(max(1, int(timeout)))
    command = [binary, "-n" if windows else "-c", "1", "-w" if windows else "-W", wait, host]
    try:
        code, stdout, _ = ProcessWrapper.run(command[0], command[1:], timeout=timeout + 2)
    except subprocess.TimeoutExpired:
        return False
    # Windows ping exits 0 on "Destination host unreachable"; only an echo reply carries TTL=.
    return code == 0 and (not windows or "TTL=" in stdout.upper())


def ping(host: str, timeout: float = 1.0, binary: str = "ping") -> bool:
    try:
        address = socket.gethostbyname(host)
    except OSError:
        return False
    opened = _open_socket()
    if opened is not None:
        sock, raw = opened
        with sock:
            try:
                return _ping_socket(sock, raw, address, timeout)
            except OSError:
                return False
    if shutil.which(binary) is None:
        raise RuntimeError(
            f"no ICMP socket permitted and no {binary!r} binary: grant net.ipv4.ping_group_range "
            "or CAP_NET_RAW, or install ping"
        )
    return _ping_binary(binary, address, timeout)
