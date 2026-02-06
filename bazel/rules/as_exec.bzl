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
"""
    Implements a rule to run generators in exec cfg
    With this host configuration, generators need to be run only once even if the corresponding results
    are built with different bazel configs
"""

def _as_exec_impl(ctx):
    providers = [
        OutputGroupInfo,
        CcInfo,
    ]

    output = [
        ctx.attr.src[provider]
        for provider in providers
        if provider in ctx.attr.src
    ]

    if DefaultInfo in ctx.attr.src:
        output = output + [DefaultInfo(files = ctx.attr.src[DefaultInfo].files, runfiles = ctx.attr.src[DefaultInfo].data_runfiles)]

    return output

as_exec = rule(
    implementation = _as_exec_impl,
    attrs = {
        "src": attr.label(
            allow_files = True,
            cfg = "exec",
        ),
    },
)
