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
"""Config-based capture extending the canonical DltReceive and DltWindow APIs."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol

from .process import DltReceive, Protocol as Transport, bundled
from .window import DltLogRecord, DltWindow


@dataclass(frozen=True)
class Message:
    ecu_id: str
    apid: str
    ctid: str
    payload: bytes
    time_stamp: float
    raw: object

    def text(self) -> str:
        return self.payload.decode("utf-8", errors="replace")


def _message(raw) -> Message:
    payload = getattr(raw, "payload_decoded", b"")
    if isinstance(payload, str):
        payload = payload.encode()
    return Message(
        ecu_id=str(getattr(raw, "ecuid", "") or ""),
        apid=str(raw.apid),
        ctid=str(raw.ctid),
        payload=payload or b"",
        time_stamp=getattr(raw, "tmsp", 0.0),
        raw=raw,
    )


class DltCaptureRecord(DltLogRecord):
    """A canonical record search with bytes-based Message results."""

    _convert = staticmethod(_message)
    _clock = staticmethod(time.monotonic)


class Endpoint(Protocol):
    __contract__ = "descriptor.endpoint"

    host: str
    port: int


@dataclass(frozen=True)
class ReceiveConfig:
    host_ip: str = "127.0.0.1"
    multicast_ips: str = ""
    file_name: str | None = None
    print_to_stdout: bool = False
    binary_path: str | None = None


class DltCapture(DltReceive):
    """`logs` through dlt-receive: UDP on `host_ip` joining `multicast_ips`,
    or TCP to an endpoint's host. Everything is recorded to `path()`."""

    def __init__(self, config: dict, endpoint: Endpoint | None = None):
        self.endpoint = endpoint
        self.transport = Transport.TCP if endpoint is not None else Transport.UDP
        self.host_ip = config.get("host_ip", "127.0.0.1")
        self.multicast_ips = [ip.strip() for ip in (config.get("multicast_ips") or "").split(",") if ip.strip()]
        self.print_to_stdout = config.get("print_to_stdout", False)
        self.binary_path = config.get("binary_path") or bundled("dlt-receive")
        super().__init__(
            protocol=self.transport,
            host_ip=self.host_ip,
            multicast_ips=self.multicast_ips,
            target_ip=endpoint.host if endpoint is not None else None,
            file_name=config.get("file_name"),
            enable_file_output=False,
            print_to_stdout=self.print_to_stdout,
            logger_name="dlt_receive",
            binary_path=self.binary_path,
        )
        self._args = ["-o", self.file_name(), *self._args]
        self._env = self._daemon_port_env()
        if self.print_to_stdout:
            self._args.append("--stdout-flush")
        self._subscribed = False

    def _daemon_port_env(self) -> dict | None:
        """dlt-receive has no TCP port option; its client library reads the daemon's port from the environment, so
        a published port other than 13490 (a container's) still reaches the daemon. Read when a receiver starts:
        a restart can publish the port elsewhere."""
        if self.endpoint is None:
            return None
        return {**os.environ, "DLT_DAEMON_TCP_PORT": str(self.endpoint.port)}

    def subscribe(self) -> None:
        if self.is_active():
            return
        self._env = self._daemon_port_env()
        if os.path.exists(self.file_name()):
            os.remove(self.file_name())
        os.makedirs(os.path.dirname(self.file_name()) or ".", exist_ok=True)
        super().__enter__()
        self._subscribed = True

    def is_active(self) -> bool:
        return self._subscribed and self.is_running()

    def close(self) -> None:
        if self._subscribed:
            super().__exit__(None, None, None)
            self._subscribed = False

    def path(self) -> str:
        return self.file_name()

    def record(self, filters=None) -> DltCaptureRecord:
        return DltCaptureRecord(self.file_name(), filters)

    def lines(self) -> list[Message]:
        try:
            if os.path.getsize(self.file_name()) == 0:
                return []
        except FileNotFoundError:
            return []
        return self.record().find()

    def filter(self, apid: str | None = None, ctid: str | None = None) -> list[Message]:
        return [m for m in self.lines() if (apid is None or m.apid == apid) and (ctid is None or m.ctid == ctid)]

    @contextmanager
    def window(
        self,
        dlt_filter: str | None = None,
        print_to_stdout: bool = False,
        *,
        transport: Transport | None = None,
        host_ip: str | None = None,
        target_ip: str | None = None,
        multicast_ips: list[str] | None = None,
        logger_name: str = "dlt_receive_window",
    ) -> Iterator[DltCaptureWindow]:
        """A second dlt-receive for a `with` block, e.g. one test; `dlt_filter` like "APID CTID".
        `transport`, `host_ip`, `target_ip` and `multicast_ips` aim this recording elsewhere than the
        node (another interface, another target); its output goes to the `logger_name` logger."""
        recorder_transport = transport or self.transport
        recorder = DltCaptureWindow(
            protocol=recorder_transport,
            host_ip=host_ip or self.host_ip,
            target_ip=target_ip or (self.endpoint.host if self.endpoint is not None else None),
            multicast_ips=self.multicast_ips if multicast_ips is None else multicast_ips,
            print_to_stdout=print_to_stdout,
            logger_name=logger_name,
            dlt_filter=dlt_filter,
            binary_path=self.binary_path,
        )
        if recorder_transport == Transport.TCP and target_ip is None:
            recorder._env = self._daemon_port_env()  # this node's daemon, at the port it is published on now
        with recorder:
            yield recorder


class DltCaptureWindow(DltWindow):
    """A canonical window returning bytes-based capture records."""

    def record(self, filters=None) -> DltCaptureRecord:
        return DltCaptureRecord(self.file_name(), filters)
