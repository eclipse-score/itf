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
"""The helper tools of the compatibility layer.

- `report(paths)`: every original name a suite uses (imports, `target.<method>` calls, `requires_capabilities`,
  the original fixtures, the original plugin labels and options in BUILD files), with file, line and the new
  equivalent. Read from the source; nothing is imported or run.
- `write_target(options, out)`: the target file the layer generates from the original options, written as a
  project's starting point, with a `.env.example` for the values it still needs.
"""

from __future__ import annotations

import ast
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import yaml

TEMPLATES = Path(__file__).resolve().parent / "targets"

MODULES = {
    "score.itf.plugins.core": '@itf.requires("<role>") and target.<role>',
    "score.itf.plugins.docker": "a target file with docker.platform (itf compat target writes one)",
    "score.itf.plugins.qemu": "a target file with qemu.platform (itf compat target writes one)",
    "score.itf.plugins.core_dump": "the core_dump pack: score.itf.packs.core_dump",
    "score.itf.plugins.dlt": "a logs role (dlt.receive) or a dlt_on_target role (dlt.on_target)",
    "score.itf.plugins.dlt.dlt_receive": "score.itf.packs.dlt.receive.process (the same DltReceive)",
    "score.itf.plugins.dlt.dlt_window": "score.itf.packs.dlt.receive.window (the same DltWindow)",
    "score.itf.plugins.qemu.config": "score.itf.packs.qemu.config",
    "score.itf.core.com.ssh": "score.itf.packs.ssh.session (the same Ssh), or target.shell",
    "score.itf.core.com.sftp": "score.itf.packs.ssh.files (the same Sftp), or target.files",
    "score.itf.core.com.ssh_command": "score.itf.packs.ssh.command (the same SshCommand)",
    "score.itf.core.com.ping": "score.itf.packs.ping.ping (the same functions), or target.ping",
    "score.itf.core.target": "target.<role>",
    "score.itf.core.utils": "score.itf.compat.utils, or your own helper",
}
METHODS = {
    "execute": "target.command.exec(cmd)",
    "execute_async": "target.process.spawn(...)",
    "wrap_exec": "target.process.wrap_exec(...)",
    "upload": "target.files.upload(...)",
    "download": "target.files.download(...)",
    "restart": "target.platform.restart()",
    "ssh": "target.shell (one role per login)",
    "sftp": "target.files (ssh.files)",
    "ping": "target.ping.ping(timeout)",
    "ping_lost": "target.ping.ping_lost(timeout)",
    "get_ip": "target.platform.ip()",
    "get_gateway": "target.platform.gateway()",
}
CAPABILITIES = {"exec": "command", "file_transfer": "files", "sftp": "files", "ssh": "shell", "restart": "platform"}
FIXTURES = {
    "docker_configuration": "the platform role's settings in the target file",
    "dlt": "a logs role (dlt.receive) and the goal logs.active",
    "dlt_config": "the logs role's settings",
    "dlt_on_target": "a dlt_on_target role (dlt.on_target): target.dlt_on_target.start(...)",
}
LABELS = re.compile(r"//score/itf/plugins:(docker_plugin|qemu_plugin|dlt_plugin|core_dump_plugin)")
OPTIONS = re.compile(
    r"--(docker-image|docker-image-bootstrap|qemu-config|qemu-image|qemu-kernel|qemu-rootfs|qemu-disk|dlt-config)\b"
)


@dataclass(frozen=True)
class Use:
    path: str
    line: int
    name: str
    instead: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}  {self.name}  ->  {self.instead}"


def report(paths) -> list[Use]:
    """Every use of the original API under `paths` (files or directories), sorted by file and line."""
    found: list[Use] = []
    for path in _files(paths):
        if path.suffix == ".py":
            found += _python_uses(path)
        elif path.name in ("BUILD", "BUILD.bazel"):
            found += _build_uses(path)
    return sorted(found, key=lambda u: (u.path, u.line, u.name))


def _files(paths) -> list[Path]:
    files: list[Path] = []
    for entry in map(Path, paths):
        files += sorted(p for p in entry.rglob("*") if p.is_file()) if entry.is_dir() else [entry]
    return files


def _python_uses(path: Path) -> list[Use]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return []
    uses = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in MODULES:
            uses.append(Use(str(path), node.lineno, f"from {node.module} import ...", MODULES[node.module]))
        elif isinstance(node, ast.Call):
            uses += _call_uses(path, node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            for arg in node.args.args:
                if arg.arg in FIXTURES:
                    uses.append(Use(str(path), node.lineno, f"fixture {arg.arg}", FIXTURES[arg.arg]))
    return uses


def _call_uses(path: Path, node: ast.Call) -> list[Use]:
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in METHODS and _named(func.value, "target"):
        return [Use(str(path), node.lineno, f"target.{func.attr}()", METHODS[func.attr])]
    if (isinstance(func, ast.Attribute) and func.attr == "requires_capabilities") or _named(
        func, "requires_capabilities"
    ):
        roles = sorted({CAPABILITIES.get(a.value, "<role>") for a in node.args if isinstance(a, ast.Constant)})
        instead = " ".join(f'@itf.requires("{r}")' for r in roles) or '@itf.requires("<role>")'
        return [Use(str(path), node.lineno, "requires_capabilities(...)", instead)]
    return []


def _named(node, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _build_uses(path: Path) -> list[Use]:
    uses = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        for match in LABELS.finditer(line):
            uses.append(Use(str(path), number, match.group(0), "the packs its target file names, on an itf_target"))
        for match in OPTIONS.finditer(line):
            uses.append(Use(str(path), number, match.group(0), "a target file (itf compat target writes one)"))
    return uses


# ---- the target file the original options make ----

VALUES = {
    "docker_image": "LEGACY_DOCKER_IMAGE",
    "docker_image_bootstrap": "LEGACY_DOCKER_BOOTSTRAP",
    "qemu_config": "LEGACY_QEMU_CONFIG",
    "qemu_kernel": "LEGACY_QEMU_KERNEL",
    "qemu_rootfs": "LEGACY_QEMU_ROOTFS",
    "qemu_disk": "LEGACY_QEMU_DISK",
}


def write_target(options: dict, out: Path) -> list[Path]:
    """Write `out`/target.itf.yaml (and what it includes), policy.py and .env.example from the original options:
    the values given are filled in, every other ${NAME} stays and is listed in .env.example."""
    kind = "docker" if options.get("docker_image") else "qemu" if options.get("qemu_config") else None
    if kind is None:
        raise ValueError("give --docker-image or --qemu-config, as the original plugins needed")
    out.mkdir(parents=True, exist_ok=True)
    names = [f"{kind}_dlt.itf.yaml", f"{kind}.itf.yaml"] if options.get("dlt") else [f"{kind}.itf.yaml"]
    values = {VALUES[k]: v for k, v in options.items() if k in VALUES and v}
    written, left = [], set()
    for i, name in enumerate(names):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        for key, value in values.items():
            text = re.sub(r"\$\{" + key + r"(:-[^}]*)?\}", str(value), text)
        left |= set(re.findall(r"\$\{([A-Z_][A-Z0-9_]*)\}", text))
        target = out / ("target.itf.yaml" if i == 0 else name)
        if i == 0:
            text += "\n" + yaml.safe_dump({"policies": [str((out / "policy.py").resolve())]})
        target.write_text(text, encoding="utf-8")
        written.append(target)
    shutil.copyfile(TEMPLATES / "policy.py", out / "policy.py")
    env = out / ".env.example"
    lines = ["# Values the target file still needs: copy to .env (git ignores it) and set them."]
    env.write_text("\n".join(lines + [f"{name}=" for name in sorted(left)]) + "\n", encoding="utf-8")
    return [*written, out / "policy.py", env]
