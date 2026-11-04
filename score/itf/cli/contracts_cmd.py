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
"`itf contracts map|new|check`: discover, define and enforce contracts with the optional contract library.\n\n    itf contracts map [--packs all|a,b] [--tests PATH...] [--format text|json|mermaid|html] [--output FILE]\n    itf contracts new NAME --from-usage [--out FILE]\n\nThe parts are those of the named packs (default: all) and of the project's own `policy.py`; the tests are read\nfrom `@itf.requires(...)` decorators without importing them; the definitions are those of the packs, of\n`ITF_CONTRACTS_PATH` and of `--definitions DIR`."

from __future__ import annotations

import sys
from pathlib import Path

import yaml

from score.itf import contracts
from score.itf.contracts import inventory as inv
from score.itf.contracts import rules as contract_rules
from score.itf.contracts import render


def _packs(value: str) -> list[str]:
    return list(inv.known_packs()) if value == "all" else [p for p in value.split(",") if p]


def _found(args) -> list:
    """What `find` finds for each target file named on the command line (`itf contracts map x.itf.yaml`)."""
    from score.itf.cli import main as cli

    return [cli.find(name, getattr(args, "override", None)) for name in getattr(args, "target", None) or ()]


def _scope(args) -> tuple[list[str], list, list[str], dict]:
    """(packs, what was found per target file, test paths, pack modules). Given target files, the map covers
    exactly their packs (including those their `packs:` section locates), the project code beside them and the
    tests in their directories; otherwise every pack (or --packs) and --tests."""
    from score.itf.core.frontends import target_file

    found = _found(args)
    given = list(getattr(args, "tests", None) or ())
    if not found:
        return _packs(args.packs), [], given, {}
    docs = [target_file.load_all(f.target_file, f.overrides) for f in found]
    names = {p for d in docs for p in target_file.packs_of(d)} - {"local"}
    modules = {k: v for d in docs for k, v in target_file.pack_modules(d).items()}
    tests = given or sorted({str(f.target_file.path.parent) for f in found})
    return sorted(names), found, tests, modules


def _pack_definition_dirs(modules: dict) -> list[str]:
    """A pack's definitions live in its own `contracts/` directory, also for packs a target file locates."""
    import importlib.util

    found = []
    for module in modules.values():
        spec = importlib.util.find_spec(module)
        if spec is not None and spec.origin:
            directory = Path(spec.origin).parent / "contracts"
            if directory.is_dir():
                found.append(str(directory))
    return found


def _policies(found) -> list:
    """Only the policies explicitly selected by the effective target documents."""
    from score.itf.core.frontends.target_file import load_all
    from score.itf.core.frontends.target_source import load_policies

    return list(
        dict.fromkeys(
            module for item in found for module in load_policies(load_all(item.target_file, item.overrides)["policies"])
        )
    )


def _observed(args, packs, found=(), tests=(), modules=None):
    """(catalog, errors, tests, definitions): what the commands read. Given target files, only the definitions
    of the contracts they use are kept, so the map shows that target file and nothing else."""
    catalog, errors = inv.load_catalog(packs, _policies(found), modules)
    requirements = inv.collect_requirements(tests)
    definitions = contracts.load_list([*(args.definitions or ()), *_pack_definition_dirs(modules or {})])
    if found:
        used = set(contracts.contract_map(catalog, tests=requirements, definitions=[]))
        definitions = [d for d in definitions if d.contract in used]
    return catalog, errors, requirements, definitions


def _out(path: str) -> Path:
    """A relative output path is the user's: relative to where the command was run, also under `bazel run`."""
    from score.itf.cli.main import project_root

    return Path(path) if Path(path).is_absolute() else project_root() / path


def cmd_map(args) -> int:
    packs, found, test_paths, modules = _scope(args)
    catalog, errors, tests, definitions = _observed(args, packs, found, test_paths, modules)
    data = inv.inventory(catalog, definitions=definitions, tests=tests, errors=errors, packs=packs)
    text = render.render(data, args.format)
    if args.output:
        _out(args.output).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


def cmd_reference(args) -> int:
    packs = _packs(args.packs)
    catalog, errors, _, definitions = _observed(args, packs)
    text = render.render_reference(inv.inventory(catalog, definitions=definitions, errors=errors, packs=packs))
    _out(args.output).write_text(text, encoding="utf-8")
    print(f"wrote {args.output}")
    return 1 if errors else 0


def cmd_new(args) -> int:
    if not args.from_usage:
        print("itf: `contracts new` builds a skeleton from usage: add --from-usage", file=sys.stderr)
        return 2
    packs, found, test_paths, modules = _scope(args)
    catalog, _, tests, definitions = _observed(args, packs, found, test_paths, modules)
    mapped = contracts.contract_map(catalog, tests=tests, definitions=definitions)
    if args.name in mapped and mapped[args.name].definition is not None:
        print(
            f"itf: {args.name} is already defined in {mapped[args.name].definition.source}; edit that file",
            file=sys.stderr,
        )
        return 1
    try:
        skeleton = contracts.skeleton_from_usage(args.name, mapped)
    except KeyError as exc:
        print(f"itf: {exc.args[0]}", file=sys.stderr)
        return 1
    out = Path(args.out) if args.out else Path("contracts") / f"{args.name.replace('/', '_')}.yaml"
    if out.exists():
        print(f"itf: {out} exists; not overwriting it", file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    body = yaml.safe_dump({"contracts": [skeleton]}, sort_keys=False, default_flow_style=False)
    out.write_text(
        f"# Definition skeleton built from the shapes observed; fill in every TODO.\n{body}", encoding="utf-8"
    )
    print(f"wrote {out}")
    return 0


def cmd_check(args) -> int:
    from score.itf.cli import main as cli
    try:
        rules = contract_rules.load_rules(args.rules)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f'itf: rules {args.rules}: {exc}', file=sys.stderr)
        return 2
    try:
        (packs, found, test_paths, modules) = _scope(args)
    except ValueError as exc:
        print(f'itf: {exc}', file=sys.stderr)
        return 2
    (catalog, errors, tests, definitions) = _observed(args, packs, found, test_paths, modules)
    mapped = contracts.contract_map(catalog, tests=tests, definitions=definitions)
    plans = []
    violations = [contracts.Violation('load', e) for e in errors]
    for one in found:
        session = cli.make_session(one, plan_only=True)
        failure = cli._resolve(session)
        label = one.target_file.describe()
        if failure:
            violations.append(contracts.Violation('compile', f'{label} does not compile: {failure.strip()}'))
        else:
            plans.append((label, contracts.roles_of_plan(session.target_plan)))
    violations += contracts.check(rules, mapped, plans)
    for v in violations:
        print(f'violation ({v.rule}): {v.message}', file=sys.stderr)
    print(f'{len(violations)} violation(s)')
    return 1 if violations else 0




def add_contracts(sub) -> None:
    parser = sub.add_parser('contracts', help='map, define and check the contracts in use')
    commands = parser.add_subparsers(dest='contracts_command', required=True)

    def common(p, tests=True):
        p.add_argument('--packs', default='all', help='`all` (default) or a comma separated list of pack names')
        p.add_argument('--definitions', action='append', default=[], help='a directory of definitions (repeatable)')
        if tests:
            p.add_argument('--tests', nargs='+', default=[], metavar='PATH', help='test files or directories to read')
    p = commands.add_parser('map', help='every contract in use: offerers, needers, tests, definition, disagreements')
    p.add_argument('target', nargs='*', help='target files to map (default: every pack, or --packs)')
    p.add_argument('--override', action='append', default=[], help='an override file for every target file')
    common(p)
    p.add_argument('--format', choices=render.FORMATS, default='text')
    p.add_argument('--output', help='write here instead of standard output')
    p.set_defaults(func=cmd_map)
    p = commands.add_parser('reference', help='write the Markdown reference of the defined contracts')
    common(p, tests=False)
    p.add_argument('--output', required=True)
    p.set_defaults(func=cmd_reference)
    p = commands.add_parser('new', help='a definition skeleton for NAME, built from the shapes in use')
    p.add_argument('name')
    p.add_argument('target', nargs='*', help='target files whose usage to read (default: every pack, or --packs)')
    p.add_argument('--from-usage', action='store_true', help='build it from the observed shapes (required)')
    p.add_argument('--out', help='the file to write (default: contracts/NAME.yaml); never overwritten')
    common(p)
    p.set_defaults(func=cmd_new)
    p = commands.add_parser('check', help='enforce a contract rules file; exit 1 on violations')
    p.add_argument('--rules', required=True, help='the contract rules: namespaces, roles, forbid_stability, conformance')
    p.add_argument('target', nargs='*', help='target files whose roles the rules cover')
    p.add_argument('--override', action='append', default=[], help='an override file for every target file')
    common(p)
    p.set_defaults(func=cmd_check)
