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
"""Which shipped target file the original options select, and the `${NAME}` values they fill."""

import os
from pathlib import Path

from .core import option

TARGET_FILES = Path(__file__).resolve().parent.parent / "targets"


def with_dlt(config) -> bool:
    """The dlt plugin is in use (its label always passes --dlt-receive-path)."""
    return bool(option(config, "dlt_receive_path") or option(config, "dlt_config"))


def select(config, kind: str, values: dict) -> None:
    """Fill the values and point the session at `targets/<kind>[_dlt].itf.yaml`, unless --itf-target names the
    project's own target file, which then wins."""
    if with_dlt(config):
        from .dlt import settings

        dlt = settings(config)
        values = {
            **values,
            "LEGACY_DLT_HOST_IP": dlt["host_ip"],
            "LEGACY_DLT_MULTICAST": ",".join(dlt["multicast_ips"]),
            "LEGACY_DLT_ON_TARGET": option(config, "dlt_receive_on_target_path"),
        }
    os.environ.update({k: str(v) for k, v in values.items() if v is not None})
    if not option(config, "itf_target"):
        if kind == "docker" and option(config, "docker_ssh"):
            kind = "docker_ssh"
        config.option.itf_target = str(TARGET_FILES / f"{kind}{'_dlt' if with_dlt(config) else ''}.itf.yaml")
