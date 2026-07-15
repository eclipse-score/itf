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
import shutil
import subprocess

import pytest

from score.itf.plugins.qemu.image_format import get_image_format


_HAS_QEMU_IMG = shutil.which("qemu-img") is not None
requires_qemu_img = pytest.mark.skipif(not _HAS_QEMU_IMG, reason="qemu-img is not installed")


def _create_image(path, image_format):
    subprocess.run(["qemu-img", "create", "-f", image_format, str(path), "1M"], check=True, capture_output=True)


@requires_qemu_img
@pytest.mark.parametrize("image_format", ["raw", "qcow2"])
def test_format_is_probed_from_the_image_content(tmp_path, image_format):
    image = tmp_path / f"disk.{image_format}"
    _create_image(image, image_format)
    assert get_image_format(str(image)) == image_format


@requires_qemu_img
def test_qcow2_image_with_img_extension_is_detected_as_qcow2(tmp_path):
    """Ubuntu cloud images are qcow2 files that use the '.img' extension."""
    image = tmp_path / "ubuntu-24.04-minimal-cloudimg-amd64.img"
    _create_image(image, "qcow2")
    assert get_image_format(str(image)) == "qcow2"


def test_raises_when_probing_fails(mocker):
    mocker.patch(
        "score.itf.plugins.qemu.image_format.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "qemu-img"),
    )
    with pytest.raises(subprocess.CalledProcessError):
        get_image_format("/does/not/exist.img")


def test_raises_when_qemu_img_is_missing(mocker):
    mocker.patch("score.itf.plugins.qemu.image_format.subprocess.run", side_effect=FileNotFoundError())
    with pytest.raises(FileNotFoundError):
        get_image_format("/does/not/exist.wic")


def test_raises_on_unexpected_output(mocker):
    mocker.patch(
        "score.itf.plugins.qemu.image_format.subprocess.run",
        return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps({})),
    )
    with pytest.raises(KeyError):
        get_image_format("/some/image.img")
