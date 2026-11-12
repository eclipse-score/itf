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
"""`itf compat report|target`: what a suite still uses of the original ITF API, and the target file its original
options make.

    itf compat report [PATH...]                       every original name used, with file, line and replacement
    itf compat target --docker-image IMAGE [--docker-image-bootstrap CMD] [--dlt] --out DIR
    itf compat target --qemu-config FILE [--qemu-kernel FILE] [--qemu-rootfs FILE] [--qemu-disk FILE] [--dlt] --out DIR
"""

from __future__ import annotations

from pathlib import Path


def cmd_report(args) -> int:
    from score.itf.cli.main import project_root
    from score.itf.compat.tools import report

    paths = [p if Path(p).is_absolute() else str(project_root() / p) for p in args.paths or ["."]]
    uses = report(paths)
    for use in uses:
        print(use)
    print(f"{len(uses)} use(s) of the original API" + ("" if uses else ": nothing left to migrate"))
    return 0


def cmd_target(args) -> int:
    from score.itf.cli.main import project_root
    from score.itf.compat.tools import write_target

    options = {
        k: getattr(args, k)
        for k in (
            "docker_image",
            "docker_image_bootstrap",
            "qemu_config",
            "qemu_kernel",
            "qemu_rootfs",
            "qemu_disk",
            "dlt",
        )
    }
    out = Path(args.out) if Path(args.out).is_absolute() else project_root() / args.out
    try:
        written = write_target(options, out)
    except ValueError as exc:
        print(f"itf: {exc}")
        return 2
    for path in written:
        print(f"wrote {path}")
    return 0


def add_compat(sub) -> None:
    parser = sub.add_parser("compat", help="move tests from the original ITF API to the new one")
    commands = parser.add_subparsers(dest="compat_command", required=True)
    p = commands.add_parser("report", help="every original API name a suite uses, with its replacement")
    p.add_argument("paths", nargs="*", help="test files, directories and BUILD files (default: here)")
    p.set_defaults(func=cmd_report)
    p = commands.add_parser("target", help="write the target file the original options make")
    p.add_argument("--docker-image")
    p.add_argument("--docker-image-bootstrap")
    p.add_argument("--qemu-config")
    p.add_argument("--qemu-kernel", "--qemu-image", dest="qemu_kernel")
    p.add_argument("--qemu-rootfs")
    p.add_argument("--qemu-disk")
    p.add_argument("--dlt", action="store_true", help="the variant with a DLT logs role (--dlt-config was given)")
    p.add_argument("--out", required=True, help="the directory to write target.itf.yaml, policy.py, .env.example")
    p.set_defaults(func=cmd_target)
