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

genrule(
    name = "itf-image",
    srcs = [
        "@ubuntu_noble_minimal_cloudimg_amd64//file",
        "build_image.sh",
        "//scripts:render_user_data.py",
        "cloud-init/user-data",
        "cloud-init/meta-data",
        "qemu_config.json",
    ],
    outs = ["ubuntu-x86_64-itf/ubuntu-24.04-minimal-cloudimg-amd64.img"],
    cmd = """
        bash $(location build_image.sh) \
            $(RULEDIR) \
            $(location @ubuntu_noble_minimal_cloudimg_amd64//file) \
            $(RULEDIR)/ubuntu-x86_64-itf/ubuntu-24.04-minimal-cloudimg-amd64.img \
            $(location cloud-init/user-data) \
            $(location cloud-init/meta-data) \
                $(location qemu_config.json) \
                $(location //scripts:render_user_data.py)
    """,
    tags = [
        "manual",
    ],
    visibility = ["//visibility:private"],
)

filegroup(
    name = "image",
    srcs = [":ubuntu-x86_64-itf/ubuntu-24.04-minimal-cloudimg-amd64.img"],
    tags = [
        "manual",
    ],
    visibility = ["//visibility:public"],
)

filegroup(
    name = "qemu_config",
    srcs = ["qemu_config.json"],
    visibility = ["//:__subpackages__"],
)
