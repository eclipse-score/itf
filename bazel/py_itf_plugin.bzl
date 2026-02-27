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
"""Bazel rule for defining ITF test plugins."""

load("@rules_python//python:defs.bzl", "PyInfo")

PyItfPluginInfo = provider(
    doc = "Information about an ITF test plugin.",
    fields = {
        "enabled_plugins": "List of pytest plugin module paths to enable.",
        "resolved_args": "List of CLI args with $(location ...) pre-resolved.",
        "plugin_runfiles": "Merged runfiles from all plugin data dependencies.",
        "plugin_files": "Depset of all files contributed by the plugin.",
    },
)

def _py_itf_plugin_impl(ctx):
    # Resolve $(location ...) in plugin args using the plugin's own data targets.
    # Rewrite $(location) → $(rootpath) for runfiles-relative paths.
    all_data_targets = list(ctx.attr.plugin_data) + list(ctx.attr.plugin_data_as_exec)
    resolved_args = []
    for arg in ctx.attr.plugin_args:
        arg = arg.replace("$(location ", "$(rootpath ").replace("$(locations ", "$(rootpaths ")
        resolved_args.append(ctx.expand_location(arg, targets = all_data_targets))

    # Collect all plugin files and runfiles
    plugin_file_depsets = []
    plugin_runfiles = ctx.runfiles()
    for dep in all_data_targets:
        plugin_file_depsets.append(dep[DefaultInfo].files)
        if dep[DefaultInfo].default_runfiles:
            plugin_runfiles = plugin_runfiles.merge(dep[DefaultInfo].default_runfiles)

    all_plugin_files = depset(transitive = plugin_file_depsets)
    plugin_runfiles = plugin_runfiles.merge(ctx.runfiles(
        transitive_files = all_plugin_files,
    ))

    # Build providers list - always include PyItfPluginInfo
    providers = [
        PyItfPluginInfo(
            enabled_plugins = ctx.attr.enabled_plugins,
            resolved_args = resolved_args,
            plugin_runfiles = plugin_runfiles,
            plugin_files = all_plugin_files,
        ),
    ]

    # Forward PyInfo from py_library so this target can be used as a py_test dep
    if PyInfo in ctx.attr.py_library:
        providers.append(ctx.attr.py_library[PyInfo])

    # Forward DefaultInfo from py_library (carries runfiles for Python imports)
    providers.append(ctx.attr.py_library[DefaultInfo])

    return providers

py_itf_plugin = rule(
    doc = "Defines an ITF test plugin with its dependencies and configuration.",
    implementation = _py_itf_plugin_impl,
    attrs = {
        "py_library": attr.label(
            doc = "The py_library target providing the plugin's Python code.",
            mandatory = True,
        ),
        "enabled_plugins": attr.string_list(
            doc = "List of pytest plugin module paths to enable (e.g. 'score.itf.plugins.docker').",
            default = [],
        ),
        "plugin_args": attr.string_list(
            doc = "Additional CLI arguments. Supports $(location ...) referencing plugin_data targets.",
            default = [],
        ),
        "plugin_data": attr.label_list(
            doc = "Data files built for target configuration.",
            default = [],
            allow_files = True,
        ),
        "plugin_data_as_exec": attr.label_list(
            doc = "Data files built for exec (host) configuration.",
            default = [],
            allow_files = True,
            cfg = "exec",
        ),
    },
)
