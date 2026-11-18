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
"""What an itf_target hands to py_itf_test, and the helpers both rules share."""

ItfTargetInfo = provider(
    doc = "A target file: the document, its override files, the packs it may name, the files it locates.",
    fields = {
        "document": "File: the target file (YAML).",
        "overrides": "List of Files: override files, merged by role in this order.",
        "packs": "List of py_itf_plugin targets the target file's factories come from.",
        "policies": "List of Files: the target file's policy.py files (the project's own parts); a test loads them.",
        "contracts": "List of Files: contract definitions (YAML files, or directories of them) the target file names.",
        "plan": "File: the plan written at build time.",
        "runfiles": "Runfiles: the document, overrides, included files, files and the packs' runfiles.",
        "env": "Dict of string: every `${NAME}` value the target file needs, `files` as runfiles paths included.",
    },
)

def itf_path_list(entries):
    """The one place a list of paths becomes a value of `ITF_OVERRIDE` or `ITF_CONTRACTS_PATH`.

    ITF reads these with os.pathsep, which is ":" on every platform the Bazel rules support (Linux, macOS).
    """
    return ":".join(entries)

def directory_of(path):
    """`a/b/c.yaml` -> `a/b`."""
    return path.rpartition("/")[0] or "."

def contract_directories(files, short = False):
    """The directories ITF_CONTRACTS_PATH wants, from contract definitions given as files or directories.

    A directory (a source directory used as a label) is itself; a file stands for the directory it is in.
    Each directory appears once. `short` gives runfiles-relative paths (a test), otherwise exec paths (an action).
    """
    found = []
    for f in files:
        path = f.short_path if short else f.path
        directory = path if f.is_directory else directory_of(path)
        if directory not in found:
            found.append(directory)
    return found
