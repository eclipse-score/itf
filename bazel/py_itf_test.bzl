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

"""Bazel symbolic macro for running pytest via ITF."""

load("@rules_python//python:defs.bzl", "PyInfo", "py_test")
load("@score_itf//bazel:py_itf_plugin.bzl", "PyItfPluginInfo")

# =============================================================================
# Wrapper test rule: resolves plugin providers at analysis time and creates
# a launcher script that invokes the py_test binary with the full arg list.
# =============================================================================

def _itf_test_impl(ctx):
    executable = ctx.executable.test_binary
    pytest_ini = ctx.file.pytest_ini

    # ---- build the full argument list ----
    args = []

    # 1. User-supplied args (expand $(location ...) against data + data_as_exec)
    #    Rewrite $(location) → $(rootpath) so expand_location produces
    #    runfiles-relative paths instead of exec-root-relative paths.
    #    This matches Bazel's native test-rule args semantics.
    expand_targets = list(ctx.attr.data) + list(ctx.attr.data_as_exec) + [ctx.attr.pytest_ini]
    for arg in ctx.attr.extra_args:
        arg = arg.replace("$(location ", "$(rootpath ").replace("$(locations ", "$(rootpaths ")
        args.append(ctx.expand_location(arg, targets = expand_targets))

    # 2. Pytest configuration
    args.extend(["-c", pytest_ini.short_path])
    args.extend(["-p", "no:cacheprovider", "--show-capture=no"])

    # 3. Plugin enable flags and plugin-specific args (resolved at analysis time)
    args.append("-p score.itf.plugins.core")
    for plugin_target in ctx.attr.plugins:
        info = plugin_target[PyItfPluginInfo]
        for ep in info.enabled_plugins:
            args.append("-p %s" % ep)
        args.extend(info.resolved_args)

    # 4. Source file paths (positional args for pytest)
    for src in ctx.files.srcs:
        args.append(src.short_path)

    # ---- create symlink to exec-config binary ----
    # The test_binary is built with cfg="exec", so its short_path has ../
    # prefixes. A symlink declared in the main repo has a clean short_path
    # that works correctly in the runfiles tree.
    inner_bin = ctx.actions.declare_file(ctx.attr.name + ".bin")
    ctx.actions.symlink(
        output = inner_bin,
        target_file = executable,
        is_executable = True,
    )

    # ---- collect plugin Python import paths for PYTHONPATH ----
    # When plugins use select(), the select may resolve to different branches
    # for _itf_test (target config) vs py_test (exec config via cfg transition).
    # Augmenting PYTHONPATH ensures the correct plugin packages are importable.
    plugin_imports = []
    for plugin_target in ctx.attr.plugins:
        if PyInfo in plugin_target:
            plugin_imports.extend(plugin_target[PyInfo].imports.to_list())
    seen = {}
    unique_imports = []
    for imp in plugin_imports:
        if imp not in seen:
            seen[imp] = True
            unique_imports.append(imp)

    # ---- create launcher script ----
    launcher = ctx.actions.declare_file(ctx.attr.name)
    quoted = " ".join(['"%s"' % a.replace("\\", "\\\\").replace('"', '\\"') for a in args])

    # Build the launcher line by line using %s to avoid .format() vs shell $ conflicts.
    launcher_lines = [
        "#!/bin/bash",
        'RUNFILES_DIR="${RUNFILES_DIR:-$0.runfiles}"',
        "export RUNFILES_DIR",
    ]
    if unique_imports:
        pythonpath_entries = ":".join(
            ["$RUNFILES_DIR/%s" % imp for imp in unique_imports],
        )
        launcher_lines.append(
            'export PYTHONPATH="%s${PYTHONPATH:+:$PYTHONPATH}"' % pythonpath_entries,
        )
    launcher_lines.append(
        'exec "$RUNFILES_DIR/%s/%s" %s "$@"' % (
            ctx.workspace_name,
            inner_bin.short_path,
            quoted,
        ),
    )
    launcher_lines.append("")  # trailing newline

    ctx.actions.write(
        output = launcher,
        content = "\n".join(launcher_lines),
        is_executable = True,
    )

    # ---- merge runfiles ----
    direct_files = (
        ctx.files.data +
        ctx.files.data_as_exec +
        ctx.files.srcs +
        [pytest_ini, inner_bin] +
        ctx.files.test_binary
    )
    transitive = (
        [ctx.attr.test_binary[DefaultInfo].default_runfiles.files] +
        [d[DefaultInfo].default_runfiles.files for d in ctx.attr.data] +
        [d[DefaultInfo].default_runfiles.files for d in ctx.attr.data_as_exec]
    )
    runfiles = ctx.runfiles(
        files = direct_files,
        transitive_files = depset(transitive = transitive),
    )

    # Add plugin runfiles (carries plugin data files + py_library runfiles)
    for plugin_target in ctx.attr.plugins:
        info = plugin_target[PyItfPluginInfo]
        runfiles = runfiles.merge(info.plugin_runfiles)

        # Also merge the DefaultInfo runfiles forwarded from py_library
        runfiles = runfiles.merge(plugin_target[DefaultInfo].default_runfiles)

    return [
        DefaultInfo(
            executable = launcher,
            runfiles = runfiles,
        ),
        RunEnvironmentInfo(
            environment = ctx.attr.env,
        ),
    ]

_itf_test = rule(
    doc = "Wrapper test rule that launches a py_test binary with ITF plugin args.",
    implementation = _itf_test_impl,
    attrs = {
        "test_binary": attr.label(
            doc = "The py_test target to wrap.",
            cfg = "exec",
            executable = True,
            mandatory = True,
            providers = [PyInfo],
        ),
        "plugins": attr.label_list(
            doc = "List of py_itf_plugin targets.",
            providers = [PyItfPluginInfo],
            cfg = "exec",
            default = [],
        ),
        "srcs": attr.label_list(
            doc = "Test source files (passed as positional args to pytest).",
            cfg = "exec",
            allow_files = [".py"],
        ),
        "pytest_ini": attr.label(
            doc = "pytest.ini configuration file.",
            cfg = "exec",
            allow_single_file = True,
            mandatory = True,
        ),
        "data": attr.label_list(
            doc = "Data files built for target configuration.",
            cfg = "target",
            allow_files = True,
            default = [],
        ),
        "data_as_exec": attr.label_list(
            doc = "Data files built for exec (host) configuration.",
            cfg = "exec",
            allow_files = True,
            default = [],
        ),
        "extra_args": attr.string_list(
            doc = "User-supplied args (supports $(location ...) against data targets).",
            default = [],
        ),
        "env": attr.string_dict(
            doc = "Environment variables for the test.",
            default = {},
        ),
    },
    test = True,
)

# =============================================================================
# Symbolic macro: the public API, creates the py_test + _itf_test pair.
# =============================================================================

def _py_itf_test_impl(name, visibility, srcs, args, data, data_as_exec, plugins, deps, tags, **kwargs):
    """Symbolic macro implementation for ITF tests."""
    pytest_bootstrap = Label("@score_itf//:main.py")
    pytest_ini = Label("@score_itf//:pytest.ini")

    # Internal py_test target: compiles & bundles Python deps.
    # Plugins forward DefaultInfo from their py_library, so they work as deps.
    py_test(
        name = name + ".test_binary",
        srcs = [pytest_bootstrap] + srcs,
        main = pytest_bootstrap,
        deps = [
            "@score_itf//:itf",
        ] + deps + plugins,
        tags = ["manual"],
        visibility = ["//visibility:private"],
    )

    # Wrapper test rule: resolves plugin providers and launches the py_test.
    _itf_test(
        name = name,
        test_binary = name + ".test_binary",
        plugins = plugins,
        srcs = srcs,
        pytest_ini = pytest_ini,
        data = data,
        data_as_exec = data_as_exec,
        extra_args = args,
        env = {
            "PYTHONDONOTWRITEBYTECODE": "1",
        },
        tags = tags,
        visibility = visibility,
    )

py_itf_test = macro(
    doc = "Symbolic macro for running ITF tests with pytest.",
    implementation = _py_itf_test_impl,
    attrs = {
        "srcs": attr.label_list(mandatory = True, allow_files = [".py"]),
        "args": attr.string_list(default = []),
        "data": attr.label_list(default = [], allow_files = True),
        "data_as_exec": attr.label_list(default = [], allow_files = True),
        "plugins": attr.label_list(default = [], providers = [PyItfPluginInfo]),
        "deps": attr.label_list(default = [], providers = [PyInfo]),
    },
    inherit_attrs = "common",
)
