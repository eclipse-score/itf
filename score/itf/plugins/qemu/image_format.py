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
import subprocess


def get_image_format(path_to_image: str) -> str:
    """Determine the disk image format by probing image metadata."""
    result = subprocess.run(
        ["qemu-img", "info", "--output=json", path_to_image],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)["format"]
