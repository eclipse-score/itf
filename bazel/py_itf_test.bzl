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
"""Bazel interface for running pytest"""

load("@itf_pip//:requirements.bzl", "requirement")
load("@rules_python//python:defs.bzl", "py_test")
load("@score_itf//bazel/rules:run_as_exec.bzl", "test_as_exec")

def py_itf_test(name, srcs, args = [], data = [], data_as_exec = [], plugins = [], deps = [], tags = []):
    """Bazel macro for running ITF tests.

    Args:
      name: Name of the test target.
      srcs: List of source files for the test.
      args: Additional arguments to pass to ITF.
      data: Data files that will be build for target config.
      data_as_exec: Data files that will be build for exec(host) config.
      plugins: List of pytest plugins to enable.
      deps: Additional python dependencies needed for the test.
      tags: Tags forwarded to the test target.
    """
    pytest_bootstrap = Label("@score_itf//:main.py")
    pytest_ini = Label("@score_itf//:pytest.ini")

    plugin_deps = []
    for plugin in plugins:
        plugin_deps += [plugin.py_library]

    plugin_tags = []
    for plugin in plugins:
        plugin_tags += plugin.tags

    py_test(
        name = "_" + name,
        srcs = [
            pytest_bootstrap,
        ] + srcs,
        main = pytest_bootstrap,
        deps = [
            # Only core ITF dep allowed, rest is resolved by plugins
            "@score_itf//:itf",
        ] + deps + plugin_deps,
        tags = ["manual"] + tags + plugin_tags,
    )

    plugin_enable_args = ["-p itf.plugins.core"]
    for plugin in plugins:
        for enabled_plugin in plugin.enabled_plugins:
            plugin_enable_args += ["-p %s" % enabled_plugin]

    plugin_args = []
    for plugin in plugins:
        plugin_args += (plugin.args)

    plugin_data = []
    for plugin in plugins:
        plugin_data += plugin.data

    plugin_data_as_exec = []
    for plugin in plugins:
        plugin_data_as_exec.extend(plugin.data_as_exec)

    data_as_exec = [pytest_ini] + srcs + data_as_exec + plugin_data_as_exec

    test_as_exec(
        name = name,
        executable = "_" + name,
        data_as_exec = data_as_exec,
        data = data + plugin_data,
        args = args +
               ["-c $(location %s)" % pytest_ini] +
               [
                   "-p no:cacheprovider",
                   "--show-capture=no",
               ] +
               plugin_enable_args +
               plugin_args +
               ["$(location %s)" % x for x in srcs],
        env = {
            "PYTHONDONOTWRITEBYTECODE": "1",
        },
        tags = tags + plugin_tags,
    )
