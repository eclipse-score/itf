"""Report and check the versions that describe an ITF source tree and its contracts."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml

from score.itf.contracts import inventory as contract_inventory
from score.itf.contracts import rules as contract_rules
from score.itf.core.engine import packs as pack_loader
from score.itf.core.engine.metadata import contributor_metadata


def _repository_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "MODULE.bazel").is_file():
            return candidate
    return start


def _module_metadata(root: Path) -> dict:
    path = root / "MODULE.bazel"
    if not path.is_file():
        return {"file": None, "name": None, "version": None}
    text = path.read_text(encoding="utf-8")
    declaration = re.search(r"(?m)^\s*module\s*\((.*?)\)", text, re.DOTALL)
    fields = declaration.group(1) if declaration else ""

    def value(key):
        found = re.search(rf"\b{key}\s*=\s*(['\"])(.*?)\1", fields)
        return found.group(2) if found else None

    return {"file": str(path.relative_to(root)), "name": value("name"), "version": value("version")}


def _git_metadata(root: Path) -> dict:
    def run(*args):
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)

    revision = run("rev-parse", "HEAD")
    if revision.returncode:
        return {"revision": None, "tag": None, "dirty": None}
    tag = run("describe", "--exact-match", "--tags", "HEAD")
    status = run("status", "--porcelain")
    return {
        "revision": revision.stdout.strip(),
        "tag": tag.stdout.strip() if tag.returncode == 0 else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else None,
    }


def _bazel_dependencies(root: Path) -> list[dict]:
    path = root / "MODULE.bazel"
    if not path.is_file():
        return []
    dependencies = []
    for call in re.findall(r"\bbazel_dep\s*\(([^)]*)\)", path.read_text(encoding="utf-8"), re.DOTALL):
        fields = {key: value for key, _, value in re.findall(r"\b(name|version)\s*=\s*(['\"])(.*?)\2", call)}
        if "name" in fields:
            dependencies.append({"name": fields["name"], "version": fields.get("version")})
    return sorted(dependencies, key=lambda dependency: dependency["name"])


def _lockfiles(root: Path) -> list[dict]:
    paths = sorted(root.glob("requirements_lock*.txt"))
    module_lock = root / "MODULE.bazel.lock"
    if module_lock.is_file():
        paths.append(module_lock)
    result = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        packages = []
        if path.name.startswith("requirements_lock"):
            for line in text.splitlines():
                match = re.match(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)==([^\s\\]+)", line)
                if match:
                    packages.append({"name": match.group(1), "version": match.group(2)})
        result.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "packages": packages,
            }
        )
    return result


def _distribution_versions(module_name: str) -> list[dict]:
    top_level = module_name.split(".", 1)[0]
    distributions = importlib.metadata.packages_distributions().get(top_level, ())
    versions = []
    for name in sorted(set(distributions)):
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        versions.append({"name": name, "version": version})
    return versions


def _core_distribution() -> dict:
    import score.itf

    source = Path(score.itf.__file__).resolve()
    try:
        distribution = importlib.metadata.distribution("score-itf")
    except importlib.metadata.PackageNotFoundError:
        return {"name": "score-itf", "version": None, "loaded_source": str(source), "owns_loaded_source": None}
    files = distribution.files or ()
    owned = any(
        Path(distribution.locate_file(path)).resolve() == source
        for path in files
        if path.as_posix().endswith("score/itf/__init__.py")
    )
    return {
        "name": "score-itf",
        "version": distribution.version,
        "loaded_source": str(source),
        "owns_loaded_source": owned,
    }


def _pack_versions(pack_entries: list[dict], names: list[str], modules: dict, loaded: dict, errors: dict) -> list[dict]:
    by_name = {entry["name"]: dict(entry) for entry in pack_entries}
    result = []
    for name in names:
        entry = by_name.setdefault(name, {"name": name, "version": None, "prerequisites": []})
        module = loaded.get(name)
        if module is None:
            entry["module"] = modules.get(name, f"score.itf.packs.{name}.plugin")
            entry["load_error"] = errors.get(name, "pack was not loaded")
        else:
            module_name = module.__name__
            metadata = contributor_metadata(module) or {}
            entry["version"] = str(metadata.get("version", entry.get("version") or "")) or None
            entry["module"] = module_name
            entry["distributions"] = _distribution_versions(module_name)
        result.append(entry)
    return result


def _catalog_with_pack_errors(packs: list[str], modules: dict, roots: list) -> tuple[object, dict, list[str]]:
    from score.itf.core.engine.publish import publish
    from score.itf.core.engine.registry import expand, register_modules
    from score.itf.core.session import _roots

    loaded, errors, parts, seen = {}, {}, [], set()
    for name in packs:
        try:
            entry = pack_loader.load(name, modules)
            expanded = expand([entry])
        except Exception as exc:  # noqa: BLE001 - report unavailable optional packs independently
            errors[name] = f"{type(exc).__name__}: {exc}"
            continue
        loaded[name] = entry
        for module, origin in expanded:
            if module.__name__ not in seen:
                seen.add(module.__name__)
            parts.append((module, origin))
    try:
        catalog = publish(register_modules([*parts, *_roots(roots)]))
    except Exception as exc:  # noqa: BLE001 - preserve a report if declarations collide
        errors["catalog"] = f"{type(exc).__name__}: {exc}"
        catalog = publish(register_modules([]))
    return catalog, loaded, errors


def build_report(args) -> dict:
    from score.itf.cli import main as cli
    from score.itf.cli import contracts_cmd

    root = _repository_root(cli.project_root())
    packs, found, test_paths, modules = contracts_cmd._scope(args)
    catalog, loaded, pack_errors = _catalog_with_pack_errors(packs, modules, contracts_cmd._policies(found))
    errors = [*pack_errors.values()]
    tests = contract_inventory.collect_requirements(test_paths, errors=errors)
    definition_dirs = list(args.definitions or ())
    for module in loaded.values():
        module_file = getattr(module, "__file__", None)
        if module_file and not module.__name__.startswith("score.itf.packs."):
            directory = Path(module_file).resolve().parent / "contracts"
            if directory.is_dir():
                definition_dirs.append(str(directory))
    from score.itf import contracts

    definitions = contracts.load_list(definition_dirs)
    if found:
        used = set(contracts.contract_map(catalog, tests=tests, definitions=[]))
        definitions = [definition for definition in definitions if definition.contract in used]
    data = contract_inventory.inventory(catalog, definitions=definitions, tests=tests, errors=errors, packs=packs)
    return {
        "schema_version": 1,
        "project": {
            "module": _module_metadata(root),
            "distribution": _core_distribution(),
            "git": _git_metadata(root),
        },
        "dependencies": {"bazel": _bazel_dependencies(root), "locks": _lockfiles(root)},
        "packs": _pack_versions(data["packs"], packs, modules, loaded, pack_errors),
        "contracts": data["contracts"],
        "errors": data["errors"],
    }


def _release_violations(report: dict, expected: str) -> list[str]:
    problems = []
    problems.extend(f"incomplete inventory: {error}" for error in report["errors"])
    expected = expected.removeprefix("v")
    module_version = report["project"]["module"]["version"]
    if module_version != expected:
        problems.append(f"MODULE.bazel declares version {module_version or '(none)'}, expected {expected}")
    distribution = report["project"]["distribution"]
    if distribution["owns_loaded_source"] and distribution["version"] != expected:
        problems.append(f"Python distribution is {distribution['version']}, expected {expected}")
    git = report["project"]["git"]
    if git["tag"] not in {expected, f"v{expected}"}:
        problems.append(f"HEAD tag is {git['tag'] or '(none)'}, expected {expected} or v{expected}")
    if git["dirty"]:
        problems.append("tracked or untracked working-tree changes are present")
    missing_packs = [pack["name"] for pack in report["packs"] if not pack.get("version")]
    if missing_packs:
        problems.append(f"packs have no version in pack.yaml: {', '.join(missing_packs)}")
    return problems


def _consistency_violations(report: dict, required_major_namespaces=()) -> list[str]:
    problems = []
    for contract in report["contracts"]:
        for disagreement in contract["disagreements"]:
            if disagreement["kind"] in {"major-mismatch", "two-definitions"}:
                problems.append(disagreement["message"])
        namespace = contract["contract"].split("/", 1)[0].split(".", 1)[0]
        if namespace not in required_major_namespaces:
            continue
        unversioned = [offer["label"] for offer in contract["offered_by"] if offer["major"] is None]
        unversioned += [need["label"] for need in contract["needed_by"] if need["major"] is None]
        unversioned += [test["test"] or test["role"] for test in contract["tests"] if test["major"] is None]
        if unversioned:
            problems.append(
                f"{contract['contract']} requires explicit @major declarations for: {', '.join(sorted(set(unversioned)))}"
            )
    return problems


def _render_text(report: dict) -> str:
    project = report["project"]
    module = project["module"]
    git = project["git"]
    lines = [
        f"project: {module['name'] or '(unknown)'}",
        f"Bazel module version: {module['version'] or '(unreleased / undeclared)'}",
        f"Python distribution: {project['distribution']['version'] or '(not installed)'} "
        f"(owns loaded source: {project['distribution']['owns_loaded_source']})",
        f"source: {git['revision'] or '(unknown)'} (tag {git['tag'] or '-'}, dirty={git['dirty']})",
        "Bazel dependencies:",
    ]
    lines.extend(
        f"  {dependency['name']} {dependency['version'] or '(unversioned)'}"
        for dependency in report["dependencies"]["bazel"]
    )
    lines.append("lockfiles:")
    lines.extend(
        f"  {lock['path']} sha256:{lock['sha256'][:12]} ({len(lock.get('packages', []))} packages)"
        for lock in report["dependencies"]["locks"]
    )
    lines += [
        f"packs: {len(report['packs'])}",
    ]
    lines.extend(
        f"  {pack['name']} {pack.get('version') or '(unversioned)'} ({pack.get('module', '-')})"
        for pack in report["packs"]
    )
    lines.append(f"contracts: {len(report['contracts'])}")
    for contract in report["contracts"]:
        definition = contract["definition"]
        offered = sorted({item["major"] for item in contract["offered_by"] if item["major"] is not None})
        required = sorted(
            {item["major"] for item in contract["needed_by"] + contract["tests"] if item["major"] is not None}
        )
        offered_text = ",".join(f"@{major}" for major in offered) or "unversioned"
        required_text = ",".join(f"@{major}" for major in required) or "unversioned"
        definition_text = f"definition v{definition['version']}" if definition else "undefined"
        lines.append(f"  {contract['contract']}: offers {offered_text}; requires {required_text}; {definition_text}")
        lines.extend(f"    disagreement: {item['message']}" for item in contract["disagreements"])
    lines.extend(f"error: {error}" for error in report["errors"])
    return "\n".join(lines)


def _write(report: dict, *, as_json: bool, output: str | None) -> None:
    text = json.dumps(report, indent=2, sort_keys=True) if as_json else _render_text(report)
    if output:
        from score.itf.cli.contracts_cmd import _out

        _out(output).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {output}", file=sys.stderr if as_json else sys.stdout)
    else:
        print(text)


def cmd_report(args) -> int:
    report = build_report(args)
    _write(report, as_json=args.json, output=args.output)
    return 1 if report["errors"] else 0


def cmd_check(args) -> int:
    report = build_report(args)
    rules = {}
    if args.rules:
        try:
            rules = contract_rules.load_rules(args.rules)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            print(f"itf: version rules {args.rules}: {exc}", file=sys.stderr)
            return 2
    required_majors = set(rules.get("require_major") or ()) | set(args.require_major)
    problems = _consistency_violations(report, required_majors)
    if args.release_version:
        problems.extend(_release_violations(report, args.release_version))
    complete = not report["errors"]
    report["check"] = {"ok": not problems and complete, "complete": complete, "violations": problems}
    _write(report, as_json=args.json, output=args.output)
    for error in report["errors"]:
        print(f"warning: inventory incomplete: {error}", file=sys.stderr)
    for problem in problems:
        print(f"violation: {problem}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} version violation(s)", file=sys.stderr)
        return 1
    if not complete:
        return 2
    if not args.json:
        suffix = "" if complete else "; inventory incomplete, see warnings"
        print(f"declared ITF versions are consistent{suffix}")
    return 0


def add_versions(sub) -> None:
    parser = sub.add_parser("versions", help="report and check release, pack, dependency and contract versions")
    commands = parser.add_subparsers(dest="versions_command", required=True)

    def common(command):
        command.add_argument("target", nargs="*", help="target files to scope the pack and contract report")
        command.add_argument("--override", action="append", default=[])
        command.add_argument("--packs", default="all", help="all packs or a comma-separated selection")
        command.add_argument("--tests", nargs="+", default=[], metavar="PATH")
        command.add_argument("--definitions", action="append", default=[])
        command.add_argument("--json", action="store_true", help="emit machine-readable JSON")
        command.add_argument("--output", help="write report to this file")

    report = commands.add_parser("report", help="report source, dependencies, packs and contract majors")
    common(report)
    report.set_defaults(func=cmd_report)

    check = commands.add_parser("check", help="fail on declared version disagreements")
    common(check)
    check.add_argument(
        "--require-major",
        action="append",
        default=[],
        metavar="NAMESPACE",
        help="require explicit majors for capability and state contracts in this namespace (repeatable)",
    )
    check.add_argument("--rules", help="shared project contract/version rules")
    check.add_argument("--release-version", help="also require module version, exact Git tag and clean tree")
    check.set_defaults(func=cmd_check)
