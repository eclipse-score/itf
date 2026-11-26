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
"""The flasher that writes the board's image to its SD card.

On a Raspberry Pi bench an SD-card multiplexer sits between the board and the bench host: with the board
powered off, the card is switched to the host, written, and switched back. Wire `SdMuxFlasher` to your
multiplexer (`sd-mux-ctrl`, the SDWire tools) and the write (`dd`, `bmaptool`)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FlasherConfig:
    sd_mux: str  # the multiplexer's serial number, e.g. "sd-wire_11"
    image: str  # the image to write, e.g. a Raspberry Pi OS .img
    block_device: str | None = None  # where the card appears on the host; None: ask the multiplexer


class SdMuxFlasher:
    """Writes `image` to the board's SD card through the multiplexer."""

    def __init__(self, config: dict):
        self.sd_mux = config["sd_mux"]
        self.image = config["image"]
        self.block_device = config.get("block_device")

    def flash(self) -> None:
        """Switch the card to the host, write the image, verify it, switch the card back to the board. The
        board must be powered off: the flash action switches the supply off first."""
        raise NotImplementedError(f"write {self.image} through {self.sd_mux}")

    def is_flashed(self) -> bool:
        """True when the card holds `image`. For example: compare the image's checksum with the one `flash()`
        recorded on the card's boot partition, read while the card is switched to the host. While the board
        runs, the card is switched to the board: answer from what the last flash or check verified, so a probe
        never switches the card away from a running board."""
        raise NotImplementedError(f"check whether the card behind {self.sd_mux} holds {self.image}")
