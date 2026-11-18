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
"""dlt-receive run on the target itself (`dlt.on_target`), through the target's own files and process roles.

`start(transport, ...)` uploads the bundled tool on first use and runs one receiver on the target; every receiver
still running stops when its `with` block ends, and at the latest when the role is torn down.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Protocol as Shape

from ..receive.process import Protocol, bundled, protocol_arguments

logger = logging.getLogger(__name__)

REMOTE_OUTPUT_DIR = "/tmp"


class Files(Shape):
    __contract__ = "files.transfer"

    def upload(self, local_path: str, remote_path: str) -> None: ...


class Process(Shape):
    __contract__ = "exec.process"

    def spawn(self, binary_path: str, args: list[str] | None = None): ...


@dataclass(frozen=True)
class OnTargetConfig:
    binary_path: str | None = None  # the dlt-receive built for the target; default: the one the pack ships
    remote_path: str = "/tmp/dlt-receive"


class DltReceiver:
    """A receiver running on the target: the process handle, plus the target path it records to."""

    def __init__(self, process, dlt_file: str):
        self._process = process
        self.dlt_file = dlt_file

    def __getattr__(self, name):
        return getattr(self._process, name)


class DltOnTarget:
    def __init__(self, files: Files, process: Process, config: dict | None = None):
        settings = {**vars(OnTargetConfig()), **(config or {})}
        self._files = files
        self._process = process
        self._binary = settings["binary_path"]
        self._remote = settings["remote_path"]
        self._uploaded = False
        self._started = []
        self._counter = 0

    def _upload(self) -> None:
        # Not at construction: the target is not up yet when roles are built.
        if not self._uploaded:
            self._files.upload(self._binary or bundled("dlt-receive"), self._remote)
            self._process.spawn("chmod", ["+x", self._remote]).wait()
            self._uploaded = True

    @contextmanager
    def start(
        self,
        transport,
        host_ip="127.0.0.1",
        target_ip="127.0.0.1",
        multicast_ips=None,
        print_to_stdout=True,
        output_file=None,
    ):
        """Run dlt-receive on the target over `transport` (`Protocol`, or "tcp"/"udp"); stop it on exit."""
        self._upload()
        self._counter += 1
        if not isinstance(transport, Protocol):
            transport = Protocol[str(getattr(transport, "name", transport)).upper()]
        dlt_file = output_file or f"{REMOTE_OUTPUT_DIR}/dlt-receive-{self._counter}.dlt"
        args = protocol_arguments(transport, host_ip, target_ip, multicast_ips or []) + ["-o", dlt_file]
        args += ["-a", "--stdout-flush"] if print_to_stdout else []
        handle = self._process.spawn(self._remote, args)
        self._started.append(handle)
        try:
            yield DltReceiver(handle, dlt_file)
        finally:
            if handle.is_running():
                handle.stop()

    __call__ = start  # `dlt_on_target("tcp")`, as the original fixture was called

    def close(self) -> None:
        for handle in self._started:
            try:
                if handle.is_running():
                    handle.stop()
            except Exception:
                logger.warning("Failed to stop dlt-receive on the target", exc_info=True)
        self._started.clear()
