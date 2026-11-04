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
"""Which target file, override files and policy a run uses, said once in the project's own configuration.

`discover` is the one function every front calls (the pytest adapter, the `itf` command line, a build tool). The
target file (a file, or inline YAML/JSON text) comes from, in order:

1. the explicit value the front hands in (`--itf-target`, the command-line argument),
2. the environment variable `ITF_TARGET`,
3. `itf_target` in `pytest.ini` (or `[tool.pytest.ini_options]` in `pyproject.toml`) at the root,
4. `[tool.itf] target` in `pyproject.toml` at the root.

The override files (each a target file holding only what changes, merged by role over it) come the same way from
`--itf-override`/`--override`, `ITF_OVERRIDE`, `itf_override` and `[tool.itf] override`; in the environment, the
ini and `pyproject.toml` several files are separated by `os.pathsep`.

A relative path from the explicit value or the environment is tried against the current directory, then the root;
one from a configuration file is relative to the root. Policies are selected only by `policies:` in the merged
target document, never by directory discovery. Their paths are absolute or relative to the invocation working
directory. `load_policies` loads each declared file once under a module name of its own.
"""

from __future__ import annotations

import configparser
import hashlib
import importlib.util
import logging
import os
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

from ..engine.yaml_text import safe_load as yaml_safe_load

logger = logging.getLogger(__name__)

ENV_TARGET_FILE = "ITF_TARGET"
ENV_OVERRIDE = "ITF_OVERRIDE"
INI_TARGET = "itf_target"
INI_OVERRIDE = "itf_override"


class TargetSourceError(ValueError):
    """A configured target file cannot be used: it names no file and is not YAML/JSON text."""


@dataclass(frozen=True)
class TargetSource:
    """`value` is an absolute path, or inline YAML/JSON text; `origin` says where it was configured."""

    value: str
    origin: str

    @property
    def is_inline(self) -> bool:
        return read_document(self.value)[1] is None

    @property
    def path(self) -> Path | None:
        """The file, or None for inline text."""
        return read_document(self.value)[1]

    def describe(self) -> str:
        value = "<inline>" if self.is_inline else self.value
        return f"{value} (from {self.origin})"


@dataclass(frozen=True)
class Discovered:
    target_file: TargetSource | None
    overrides: tuple[TargetSource, ...]


# ---------------------------------------------------------------- the one reader


def read_document(value: Any) -> tuple[str, Path | None]:
    """(text, path): the content of the file `value` names, else `value` itself as inline text (path None)."""
    try:
        candidate = Path(value)
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8"), Path(os.path.abspath(candidate))
    except (OSError, ValueError):  # multiline text cannot be stat()'d as a path
        pass
    return str(value), None


def _is_document(text: str) -> bool:
    try:
        return isinstance(yaml_safe_load(text), Mapping)
    except yaml.YAMLError:
        return False


# ---------------------------------------------------------------- locating one value


def _directories(root, only_root: bool) -> list[Path]:
    """Where a relative path is looked for: the root alone (a configuration file's value), else the working
    directory, then the root."""
    if root is not None and only_root:
        return [Path(root)]
    return list(dict.fromkeys([Path.cwd(), *([Path(root)] if root is not None else [])]))


def _existing_file(text: str, directories: list[Path]) -> Path | None:
    """The file `text` names (a single line), looked for as it is when absolute, else in `directories`."""
    if "\n" in text:
        return None
    path = Path(text)
    for candidate in [path] if path.is_absolute() else [d / path for d in directories]:
        if candidate.is_file():
            # absolute, not resolved: a target file is where it is placed (under Bazel, a symlink in the runfiles),
            # so its includes, its .env and its policy are found beside or above it there
            return Path(os.path.abspath(candidate))
    return None


def locate(value: str, origin: str, *, root=None, relative_to_root: bool = False) -> TargetSource:
    """`value` as a `TargetSource`: an existing file (made absolute) or inline YAML/JSON text. A relative
    path is tried against the current directory, then `root` (against `root` only for a configuration file's value)."""
    if isinstance(value, TargetSource):
        return value
    text = str(value).strip()
    directories = _directories(root, relative_to_root)
    file = _existing_file(text, directories)
    if file is not None:
        return TargetSource(str(file), origin)
    if _is_document(text):
        return TargetSource(str(value), origin)
    path = Path(text)
    tried = str(path.parent) if path.is_absolute() else ", ".join(str(d) for d in directories)
    raise TargetSourceError(
        f"target file {text[:80]!r} (from {origin}) is not an existing file and not inline YAML/JSON text; "
        f"looked in: {tried}"
    )


# ---------------------------------------------------------------- configuration files


def _toml(path: Path) -> dict:
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        import tomli as tomllib  # type: ignore[no-redef]
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise TargetSourceError(f"{path} is not valid TOML: {exc}") from exc


def _string(value: Any, where: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise TargetSourceError(f"{where} must be a string, not {type(value).__name__}")
    return value.strip() or None if value is not None else None


def _ini(root, name: str) -> tuple[str, str] | None:
    """`name` from `pytest.ini`, else from `[tool.pytest.ini_options]` of `pyproject.toml` (pytest's own rule:
    a `pytest.ini` is the configuration, even when it does not mention `name`). (value, origin) or None."""
    if root is None:
        return None
    ini = Path(root) / "pytest.ini"
    if ini.is_file():
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(ini, encoding="utf-8")
        except configparser.Error as exc:
            raise TargetSourceError(f"{ini} cannot be read: {exc}") from exc
        value = _string(parser.get("pytest", name, fallback=None), f"{ini}: {name}")
        return (value, f"pytest.ini {name}") if value else None
    pyproject = Path(root) / "pyproject.toml"
    if pyproject.is_file():
        options = _toml(pyproject).get("tool", {}).get("pytest", {}).get("ini_options", {})
        value = _string(options.get(name), f"{pyproject}: {name}")
        return (value, f"pyproject.toml [tool.pytest.ini_options] {name}") if value else None
    return None


def _pyproject(root, key: str) -> tuple[str, str] | None:
    """`[tool.itf] <key>` in `pyproject.toml` at `root`: (value, origin) or None."""
    pyproject = Path(root) / "pyproject.toml" if root is not None else None
    if pyproject is None or not pyproject.is_file():
        return None
    value = _string((_toml(pyproject).get("tool", {}).get("itf", {}) or {}).get(key), f"{pyproject}: [tool.itf] {key}")
    return (value, f"pyproject.toml [tool.itf] {key}") if value else None


# ---------------------------------------------------------------- the discovery


def _configured(root, ini_name: str, key: str) -> tuple[str, str] | None:
    return _ini(root, ini_name) or _pyproject(root, key)


def _find_target_file(explicit, environ, root, origin) -> TargetSource | None:
    if explicit and str(explicit).strip():
        return locate(explicit, origin, root=root)
    if (environ.get(ENV_TARGET_FILE) or "").strip():
        return locate(environ[ENV_TARGET_FILE], ENV_TARGET_FILE, root=root)
    configured = _configured(root, INI_TARGET, "target")
    return locate(configured[0], configured[1], root=root, relative_to_root=True) if configured else None


def _paths(text: str) -> list[str]:
    return [p for p in text.split(os.pathsep) if p.strip()]


def _find_overrides(explicit, environ, root, origin) -> tuple[TargetSource, ...]:
    values = [v for v in explicit if v and str(v).strip()]
    if values:
        return tuple(locate(v, origin, root=root) for v in values)
    if environ.get(ENV_OVERRIDE):
        return tuple(locate(p, ENV_OVERRIDE, root=root) for p in _paths(environ[ENV_OVERRIDE]))
    configured = _configured(root, INI_OVERRIDE, "override")
    if configured is None:
        return ()
    return tuple(locate(p, configured[1], root=root, relative_to_root=True) for p in _paths(configured[0]))


def discover(
    target_file: str | None = None,
    overrides: Iterable[str] = (),
    *,
    root=None,
    environ: Mapping[str, str] | None = None,
    target_file_origin: str = "explicit",
    override_origin: str = "explicit",
) -> Discovered:
    """The target file and override files this run uses (see the module's docstring). Raises
    `TargetSourceError` for a configured value that is neither an existing file nor inline text, and for
    override files with no target file. `root` is the project root (where `pytest.ini` and `pyproject.toml` are)."""
    environ = os.environ if environ is None else environ
    found = _find_target_file(target_file, environ, root, target_file_origin)
    extra = _find_overrides(tuple(overrides), environ, root, override_origin)
    if extra and found is None:
        raise TargetSourceError(
            f"override files need a target file, and none is configured ({target_file_origin}, {ENV_TARGET_FILE}, "
            f"{INI_TARGET} or [tool.itf] target)"
        )
    return Discovered(found, extra)


# ---------------------------------------------------------------- the one policy loader

_CONFTESTS: dict[Path, types.ModuleType] = {}


def load_policies(paths: Iterable[str]) -> tuple[types.ModuleType, ...]:
    """Load only declared policies, relative to the invocation directory or from absolute paths."""
    modules = []
    directory = Path(os.environ.get("BUILD_WORKING_DIRECTORY") or os.getcwd())
    for value in paths:
        path = directory / value
        if not path.is_file():
            raise TargetSourceError(f"policy {value!r} is not a file (working directory: {directory})")
        module = load_policy(path)
        if module not in modules:
            modules.append(module)
    return tuple(modules)


def load_policy(path) -> types.ModuleType | None:
    """The policy.py at `path` loaded as a module (its declarations register on import), once per file,
    under a module name of its own so that the `module:function` references it publishes resolve to this file.
    None when there is no such file."""
    path = Path(path)
    if not path.is_file():
        return None
    key = path.resolve()
    if key not in _CONFTESTS:
        name = f"itf_policy_{hashlib.sha1(str(key).encode()).hexdigest()[:10]}"
        spec = importlib.util.spec_from_file_location(name, key)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[name]
            raise
        _CONFTESTS[key] = module
    return _CONFTESTS[key]
