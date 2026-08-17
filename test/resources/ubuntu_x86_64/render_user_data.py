#!/usr/bin/env python3
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

"""Render cloud-init user-data using network values from qemu_config.json."""

from __future__ import annotations

import ipaddress
import json
import sys


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("Error: Expected 3 arguments (qemu config, user-data template, rendered user-data)")

    qemu_config_path = sys.argv[1]
    user_data_template_path = sys.argv[2]
    user_data_rendered_path = sys.argv[3]

    with open(qemu_config_path, encoding="utf-8") as f:
        qemu_config = json.load(f)

    networks = qemu_config.get("networks")
    if not isinstance(networks, list) or not networks:
        raise SystemExit("Error: qemu_config.json must provide at least one network")

    network = networks[0]
    for key in ("ip_address", "gateway"):
        if key not in network:
            raise SystemExit(f"Error: missing '{key}' in first network entry")

    ip_address = str(network["ip_address"])
    gateway = str(network["gateway"])
    ipaddress.ip_address(ip_address)
    ipaddress.ip_address(gateway)

    with open(user_data_template_path, encoding="utf-8") as f:
        user_data = f.read()

    if "__SCORE_ITF_IP_ADDRESS__" not in user_data or "__SCORE_ITF_GATEWAY__" not in user_data:
        raise SystemExit("Error: user-data template placeholders are missing")

    user_data = user_data.replace("__SCORE_ITF_IP_ADDRESS__", ip_address)
    user_data = user_data.replace("__SCORE_ITF_GATEWAY__", gateway)

    with open(user_data_rendered_path, "w", encoding="utf-8") as f:
        f.write(user_data)


if __name__ == "__main__":
    main()
