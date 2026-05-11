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

import json
import pytest

from python.runfiles import runfiles
from score.itf.plugins.qemu.config import load_configuration


def _resource_path(filename: str) -> str:
    rf = runfiles.Create()
    return rf.Rlocation(f"score_itf/test/resources/{filename}")


def test_sample_qemu_configs_validate() -> None:
    for filename in [
        "qemu_bridge_config.json",
        "qemu_port_forwarding_config.json",
    ]:
        load_configuration(_resource_path(filename))


def test_invalid_qemu_config_is_rejected(tmp_path) -> None:
    invalid = {
        # "networks" missing
        "ssh_port": 22,
        "qemu_num_cores": 2,
        "qemu_ram_size": "1G",
    }

    invalid_config_file = tmp_path / "qemu_invalid.json"
    invalid_config_file.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(ValueError):
        load_configuration(invalid_config_file)
