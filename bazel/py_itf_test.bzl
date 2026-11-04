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

"""Bazel symbolic macro for running pytest via ITF.

A test with a `target file` (an `itf_target`) runs against that target file: its pack dependencies come
from the target file's `packs`, the target file and its override files arrive through `ITF_TARGET` and
`ITF_OVERRIDE`, its policy is loaded without being listed in `srcs`, and building the test builds the
target file, whose plan fails the build when it does not compile.
`plugins` are for additional pytest plugins. Pack dependencies belong to the target;
project-owned fixtures, including on-target DLT setup, belong in conftest.py.
"""

load("@rules_python//python:defs.bzl", "PyInfo", "py_test")
load("@score_itf//bazel:py_itf_plugin.bzl", "PyItfPluginInfo")
load("@score_itf//bazel:target_info.bzl", "ItfTargetInfo", "contract_directories", "itf_path_list")

# =============================================================================
# Wrapper test rule: resolves plugin providers at analysis time and creates
# a launcher script that invokes the py_test binary with the full arg list.
# =============================================================================

def _itf_test_impl(ctx):
    target = ctx.attr.target[ItfTargetInfo] if ctx.attr.target else None
    plugins = list(ctx.attr.plugins)
    target_packs = list(target.packs) if target else []
    executable = ctx.executable.test_binary
    pytest_config = ctx.file.pytest_config

    # ---- build the full argument list ----
    args = []

    # 1. User-supplied args (expand $(location ...) against data + data_as_exec)
    #    Rewrite $(location) → $(rootpath) so expand_location produces
    #    runfiles-relative paths instead of exec-root-relative paths.
    #    This matches Bazel's native test-rule args semantics.
    expand_targets = list(ctx.attr.data) + list(ctx.attr.data_as_exec) + [ctx.attr.pytest_config]
    for arg in ctx.attr.extra_args:
        arg = arg.replace("$(location ", "$(rootpath ").replace("$(locations ", "$(rootpaths ")
        args.append(ctx.expand_location(arg, targets = expand_targets))

    # 2. Pytest configuration
    args.extend(["-c", pytest_config.short_path])
    args.extend(["-p", "no:cacheprovider", "--show-capture=no"])

    # 3. JUnit XML output (Bazel sets XML_OUTPUT_FILE environment variable)
    args.append("--junit-xml=$XML_OUTPUT_FILE")

    # 4. The ITF adapter (a pip install would register it as a pytest11 entry point), then
    #    every plugin's enable flags and args. Packs are plugins like any other.
    args.append("-p score.itf.core.adapters.pytest.plugin")
    for plugin_target in plugins:
        info = plugin_target[PyItfPluginInfo]
        for ep in info.enabled_plugins:
            args.append("-p %s" % ep)
        args.extend(info.resolved_args)

    # 5. The source file paths (positional args for pytest). The target file's policy is not one of them: the
    #    adapter loads the policy beside the target file itself, wherever the tests are.
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
    for plugin_target in plugins + target_packs:
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
        [pytest_config, inner_bin] +
        ctx.files.test_binary
    )
    runfiles = ctx.runfiles(
        files = direct_files,
        transitive_files = ctx.attr.test_binary[DefaultInfo].default_runfiles.files,
    )

    # Use runfiles.merge() for data deps so that repo-name root symlinks
    # (e.g. bazel_tools/) are preserved.  Collecting only .files loses
    # these symlinks, which breaks executable data deps that use
    # runfiles.bash / rlocation on Bazel 8+ where
    # --legacy_external_runfiles is no longer available.
    for d in ctx.attr.data:
        runfiles = runfiles.merge(d[DefaultInfo].default_runfiles)
    for d in ctx.attr.data_as_exec:
        runfiles = runfiles.merge(d[DefaultInfo].default_runfiles)

    # Merge plugin runfiles (carries plugin data files + py_library runfiles) and envs
    env = {}
    for plugin_target in plugins:
        info = plugin_target[PyItfPluginInfo]
        runfiles = runfiles.merge(info.plugin_runfiles)

        # Also merge the DefaultInfo runfiles forwarded from py_library
        runfiles = runfiles.merge(plugin_target[DefaultInfo].default_runfiles)
        env.update(info.env)
    for pack in target_packs:
        # Packs load from the target file's labels; their data and environment still travel with the test.
        info = pack[PyItfPluginInfo]
        runfiles = runfiles.merge(info.plugin_runfiles).merge(pack[DefaultInfo].default_runfiles)
        env.update(info.env)
    contracts = list(ctx.files.contracts)
    if target:
        runfiles = runfiles.merge(target.runfiles)
        env.update(target.env)  # the target file's ${NAME} values: plain values and the paths of its files
        env["ITF_TARGET"] = target.document.short_path
        if target.overrides:
            env["ITF_OVERRIDE"] = itf_path_list([f.short_path for f in target.overrides])
        contracts = list(target.contracts) + contracts
    if contracts:
        # Contract definitions of the project (or a vendor): the directories ITF_CONTRACTS_PATH names.
        runfiles = runfiles.merge(ctx.runfiles(files = contracts))
        env["ITF_CONTRACTS_PATH"] = itf_path_list(contract_directories(contracts, short = True))
    env.update({
        k: ctx.expand_location(v.replace("$(location ", "$(rootpath "), targets = expand_targets)
        for k, v in ctx.attr.env.items()
    })

    return [
        DefaultInfo(
            executable = launcher,
            runfiles = runfiles,
        ),
        RunEnvironmentInfo(
            environment = env,
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
        "target": attr.label(
            doc = "An itf_target: the target file this test runs against, with the packs it names and its policy.",
            providers = [ItfTargetInfo],
            cfg = "exec",
        ),
        "contracts": attr.label_list(
            doc = "Contract definitions (YAML files, or a directory of them) the test loads besides ITF's own and the target file's: their directories go to ITF_CONTRACTS_PATH.",
            allow_files = True,
            cfg = "exec",
            default = [],
        ),
        "plugins": attr.label_list(
            doc = "List of py_itf_plugin targets: ITF packs and plain pytest plugins.",
            providers = [PyItfPluginInfo],
            cfg = "exec",
            default = [],
        ),
        "srcs": attr.label_list(
            doc = "Test source files (passed as positional args to pytest).",
            cfg = "exec",
            allow_files = [".py"],
        ),
        "pytest_config": attr.label(
            doc = "pytest configuration file.",
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

def _py_itf_test_impl(name, visibility, srcs, args, data, data_as_exec, plugins, target, contracts, deps, tags, pytest_config, env, **kwargs):
    """Symbolic macro implementation for ITF tests."""
    pytest_bootstrap = Label("@score_itf//:main.py")

    # Use provided pytest_config or fall back to default
    if not pytest_config:
        pytest_config = Label("@score_itf//:pytest.ini")

    # Internal py_test target: compiles & bundles Python deps.
    # Plugins forward DefaultInfo from their py_library, so they work as deps.
    py_test(
        name = name + ".test_binary",
        srcs = [pytest_bootstrap] + srcs,
        main = pytest_bootstrap,
        deps = [
            "@score_itf//:itf",
        ] + deps + plugins + ([target] if target else []),
        tags = ["manual"],
        visibility = ["//visibility:private"],
    )

    # Wrapper test rule: resolves plugin providers and launches the py_test.
    # Test attrs (timeout, size, etc.) and common attrs (testonly, etc.) are
    # inherited from _itf_test via inherit_attrs and forwarded via **kwargs.
    _itf_test(
        name = name,
        test_binary = name + ".test_binary",
        plugins = plugins,
        target = target,
        contracts = contracts,
        srcs = srcs,
        pytest_config = pytest_config,
        data = data,
        data_as_exec = data_as_exec,
        extra_args = args,
        env = {
            "PYTHONDONOTWRITEBYTECODE": "1",
        } | env,
        tags = tags,
        visibility = visibility,
        **kwargs
    )

py_itf_test = macro(
    doc = "Symbolic macro for running ITF tests with pytest.",
    implementation = _py_itf_test_impl,
    inherit_attrs = _itf_test,
    attrs = {
        "srcs": attr.label_list(mandatory = True, allow_files = [".py"]),
        "args": attr.string_list(default = []),
        "data": attr.label_list(default = [], allow_files = True),
        "data_as_exec": attr.label_list(default = [], allow_files = True),
        "plugins": attr.label_list(default = [], providers = [PyItfPluginInfo]),
        "target": attr.label(default = None, configurable = False, providers = [ItfTargetInfo], doc = "An itf_target: the target file this test runs against. Its policy (itf_verify, itf_teardown, fixtures, the project's own capabilities and actions) is loaded without being listed in srcs."),
        "deps": attr.label_list(default = [], providers = [PyInfo]),
        "pytest_config": attr.label(default = None, allow_single_file = True, doc = "Custom pytest configuration file. If not specified, uses the default from @score_itf//:pytest.ini."),
        "env": attr.string_dict(default = {}, doc = "Environment variables for the test."),
        # Suppress internal _itf_test attrs that are not part of the public API.
        "test_binary": None,
        "extra_args": None,
    },
)
