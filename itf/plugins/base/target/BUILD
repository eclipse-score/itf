# *******************************************************************************
# Copyright (c) 2025 Contributors to the Eclipse Foundation
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
py_library(
    name = "target",
    srcs = [
        "__init__.py",
        "base_target.py",
        "hw_target.py",
        "qemu_target.py",
        "qvp_target.py",
    ],
    imports = ["."],
    visibility = ["//visibility:public"],
    deps = [
        "//itf/plugins/base/os",
        "//itf/plugins/base/target/config",
        "//itf/plugins/base/target/processors",
        "//itf/plugins/dlt",
    ],
)
