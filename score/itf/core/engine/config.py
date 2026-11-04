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
"""Settings declared by a capability factory and side-effect-free validation."""

from __future__ import annotations

import dataclasses
import difflib
import types
import typing
from dataclasses import dataclass

from .secrets import Secrets


class Unset(str):
    """A `${NAME}` that has no value at plan time, kept as the text `${NAME}`. Only a plan-only session uses it
    (the Bazel compile step, where a login is only known at test time); it is accepted for any type, since
    nothing is ever constructed from it."""


@dataclass(frozen=True)
class ConfigField:
    name: str
    types: tuple[type, ...]
    required: bool
    sensitive: bool
    default: object = dataclasses.MISSING

    @property
    def type_name(self) -> str:
        return " | ".join("null" if kind is type(None) else kind.__name__ for kind in self.types)

    def describe(self) -> dict:
        data = {"name": self.name, "type": self.type_name, "required": self.required, "sensitive": self.sensitive}
        if not self.required and not self.sensitive:
            data["default"] = self.default
        return data


@dataclass(frozen=True)
class ConfigSchema:
    fields: tuple[ConfigField, ...]

    @classmethod
    def from_dataclass(cls, model: type) -> "ConfigSchema":
        if not isinstance(model, type) or not dataclasses.is_dataclass(model):
            raise TypeError("config_schema must be a dataclass type")
        hints = typing.get_type_hints(model)
        fields = []
        for field in dataclasses.fields(model):
            annotation = hints[field.name]
            choices = (
                typing.get_args(annotation)
                if typing.get_origin(annotation) in (typing.Union, types.UnionType)
                else (annotation,)
            )
            if not choices or any(kind not in (str, int, float, bool, type(None)) for kind in choices):
                raise TypeError(f"config_schema.{field.name} must be a scalar type or optional scalar")
            if field.default_factory is not dataclasses.MISSING:
                raise TypeError(f"config_schema.{field.name} cannot have a default factory")
            required = field.default is dataclasses.MISSING
            if not required and type(field.default) not in choices:
                raise TypeError(f"config_schema.{field.name} default has wrong type")
            fields.append(
                ConfigField(field.name, choices, required, field.metadata.get("sensitive", False), field.default)
            )
        return cls(tuple(fields))

    def validate(self, config: dict) -> tuple[str, ...]:
        by_name = {field.name: field for field in self.fields}
        issues = []
        for name in sorted(config.keys() - by_name.keys()):
            guess = difflib.get_close_matches(name, by_name, n=1)
            issues.append(f"config.{name}: unknown key" + (f"; did you mean '{guess[0]}'?" if guess else ""))
        for field in self.fields:
            if isinstance(config.get(field.name), Unset):
                continue
            if field.name not in config:
                if field.required:
                    issues.append(f"config.{field.name}: required {field.type_name}")
            elif type(config[field.name]) not in field.types and not (
                type(config[field.name]) is int and float in field.types
            ):
                issues.append(f"config.{field.name}: expected {field.type_name}")
        return tuple(issues)

    def describe(self) -> list[dict]:
        return [field.describe() for field in self.fields]

    def all_sensitive(self) -> "ConfigSchema":
        """This schema with every field sensitive."""
        return type(self)(tuple(dataclasses.replace(f, sensitive=True) for f in self.fields))

    def secrets(self, config: dict) -> list:
        """The values of the sensitive fields in `config`."""
        return [config[f.name] for f in self.fields if f.sensitive and f.name in config]

    def redact(self, config: dict) -> dict:
        hidden = {field.name for field in self.fields if field.sensitive}
        return {key: "[redacted]" if key in hidden else value for key, value in config.items()}


def sensitive_values(target, schemas) -> list:
    """The values of every sensitive setting in `target`'s plan."""
    if target is None:
        return []
    return [
        value
        for node in target.nodes
        if node.provider in schemas
        for value in schemas[node.provider].secrets(dict(node.config))
    ]


def plan_secrets(target, schemas) -> Secrets:
    """The secrets of `target`'s plan, to mask wherever a setting is shown."""
    secrets = Secrets()
    for value in sensitive_values(target, schemas):
        secrets.add(value)
    return secrets


def shown_config(config: dict, schema, secrets: Secrets) -> dict:
    """`config` as ITF shows it: sensitive fields redacted, and a secret copied into any other setting
    (`environment: PASSWORD=${PASSWORD}`) masked there too."""
    config = schema.redact(config) if schema is not None else dict(config)
    return {key: _masked(value, secrets) for key, value in config.items()}


def _masked(value, secrets: Secrets):
    if not isinstance(value, str):
        return value
    masked = secrets.mask(value)
    return value if masked == value else masked


def redact_target(target, schemas):
    if target is None:
        return None
    secrets = plan_secrets(target, schemas)
    return dataclasses.replace(
        target,
        nodes=tuple(
            dataclasses.replace(
                node,
                config=tuple(sorted(shown_config(dict(node.config), schemas.get(node.provider), secrets).items())),
            )
            for node in target.nodes
        ),
    )
