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

from score.itf.core.process import ProcessWrapper


def get_image_format(path_to_image: str) -> str:
    """Determine the disk image format by probing image metadata."""
    code, stdout, stderr = ProcessWrapper.run("qemu-img", ["info", "--output=json", path_to_image])
    if code != 0:
        raise subprocess.CalledProcessError(code, "qemu-img", stdout, stderr)
    return json.loads(stdout)["format"]
