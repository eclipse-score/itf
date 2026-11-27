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
"""The Raspberry Pi as the target's `platform`: up means powered and answering on the network.

This is glue over the power supply, the ping role and the command role, with no hardware code of its own. A
board with a different boot signal (a serial prompt, a UDS response) keeps the same members and changes what
`start` waits for."""

import logging
import time
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


class PowerSupply(Protocol):
    __contract__ = "bench/power.supply"

    def on(self) -> None: ...
    def off(self) -> None: ...
    def is_on(self) -> bool: ...


class Pinger(Protocol):
    __contract__ = "net.ping"

    host: str

    def ping(self) -> bool: ...
    def wait_up(self, timeout: float | None = None) -> bool: ...
    def wait_down(self, timeout: float | None = None) -> bool: ...


class Command(Protocol):
    __contract__ = "exec.command"

    def exec(self, command: str, /) -> tuple[int, bytes]: ...


@dataclass(frozen=True)
class BoardConfig:
    reboot_command: str = "sudo reboot"  # the soft reset `restart` sends
    down_timeout: float = 30.0  # seconds for the board to stop answering after the reboot command
    off_time: float = 3.0  # seconds without power in a power cycle, so the board really resets


class RaspberryPi:
    """`platform.instance` (start, running, restart, stop), plus `power_cycle` for a hard reset."""

    def __init__(self, power: PowerSupply, ping: Pinger, command: Command, config: dict):
        self._power = power
        self._ping = ping
        self._command = command
        self._reboot_command = config.get("reboot_command", "sudo reboot")
        self._down_timeout = config.get("down_timeout", 30.0)
        self._off_time = config.get("off_time", 3.0)

    def start(self) -> None:
        """Power the board and wait until it answers on the network (the ping role's boot timeout)."""
        self._power.on()
        self._wait_up("power-on")

    def running(self) -> bool:
        """Powered and answering. A board that is powered but hangs is not up."""
        return self._power.is_on() and self._ping.ping()

    def restart(self) -> None:
        """A soft reset: the reboot command over SSH, then the board goes quiet and answers again. A board that
        does not go down (hung, or the command failed) is power-cycled instead. Connections to the board (SSH,
        SFTP) drop either way; `target.reach()` brings them back."""
        try:
            self._command.exec(self._reboot_command)
        except Exception:  # noqa: BLE001  the session may drop before the command returns
            logger.info("the reboot command ended with the connection", exc_info=True)
        if not self._ping.wait_down(timeout=self._down_timeout):
            logger.warning(
                "%s still answers %ss after the reboot command: power-cycling", self._ping.host, self._down_timeout
            )
            self.power_cycle()
            return
        self._wait_up("reboot")

    def power_cycle(self) -> None:
        """A hard reset: power off, wait, power on, wait until the board answers."""
        self.stop()
        time.sleep(self._off_time)
        self.start()

    def stop(self) -> None:
        self._power.off()

    def _wait_up(self, after: str) -> None:
        if not self._ping.wait_up():
            raise TimeoutError(f"the board at {self._ping.host} did not answer after {after}")
