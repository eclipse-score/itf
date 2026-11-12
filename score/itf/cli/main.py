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
"""`itf`: validate, plan, draw, bring up, take down and test a target file, and work with contracts.

A target file is a YAML or JSON document (the format `score.itf.core.frontends.target file` reads), given as an
argument or configured (`ITF_TARGET`, `itf_target` in pytest.ini, `[tool.itf] target` in
pyproject.toml) exactly as for a test run: both go through `target_source.discover`. Override files
(`--override`, `ITF_OVERRIDE`) are merged by role over it. Packs load from the factory labels it names.
`validate`, `plan` and `graph` read metadata only and construct nothing.
"""

from __future__ import annotations

import argparse
import code
import json
import os
import sys
import tempfile
from pathlib import Path

from score.itf.cli.doctor import cmd_doctor
from score.itf.cli.graph import render_graph
from score.itf.core.adapters.definitions import definitions
from score.itf.core.engine.evidence import (
    HTML_NAME,
    render_summary,
    summarize,
    write_html,
)
from score.itf.core.engine.failure import banner
from score.itf.core.engine.labels import node_label
from score.itf.core.engine.scopes import display
from score.itf.core.artifacts import plan_document
from score.itf.core.frontends.target_source import Discovered, discover
from score.itf.core.session import ConfigValidationFailed, NotReady, ResolutionFailed, Session, TargetNameClash

ADAPTER = "score.itf.core.adapters.pytest.plugin"
NO_TARGET_FILE = (
    "no target file: pass one, or configure it (ITF_TARGET, `itf_target` in pytest.ini, "
    'or `[tool.itf] target = "x.itf.yaml"` in pyproject.toml)'
)


# ---------------------------------------------------------------- building a session from a target file


def project_root() -> Path:
    """The invocation directory, including when `bazel run` changes the process working directory."""
    return Path(os.environ.get("BUILD_WORKING_DIRECTORY") or os.getcwd())  # `bazel run` starts in the runfiles


def find(target_file: str | None, overrides=()) -> Discovered:
    """The target file and override files a command uses, as for a test run. Raises `ValueError` when
    none is configured or a value is not usable."""
    found = discover(
        target_file,
        overrides or (),
        root=project_root(),
        target_file_origin="the command line",
        override_origin="--override",
    )
    if found.target_file is None:
        raise ValueError(NO_TARGET_FILE)
    return found


def default_run_dir() -> Path:
    return project_root() / "itf-run"


def make_session(found: Discovered, *, run_dir=None, **options) -> Session:
    """A session on the target and overrides; its policies are explicitly declared in their YAML."""
    return Session(
        target=found.target_file,
        overrides=found.overrides,
        run_dir=run_dir,
        definitions=definitions(),
        **options,
    )


def session_of(args, *, run_dir=None, **options) -> Session:
    artifacts = getattr(args, "artifacts", None) or os.environ.get("ITF_ARTIFACTS") or "standard"
    found = find(args.target_file, args.override)
    return make_session(found, run_dir=run_dir or args.run_dir, artifacts=artifacts, **options)


def _resolve(session: Session) -> str | None:
    """Resolve; returns the diagnostics to show on failure, else None."""
    try:
        session.resolve()
    except ResolutionFailed as exc:
        return banner(f"ITF: plan failed at gate {exc.gate}", 100) + "\n" + exc.rendered
    except (ConfigValidationFailed, TargetNameClash) as exc:
        return banner("ITF: target file rejected", 100) + "\n" + str(exc)
    except Exception as exc:  # noqa: BLE001 - CrossContributorImport, a malformed document, a missing pack, ...
        return banner("ITF: target file rejected", 100) + f"\n{type(exc).__name__}: {exc}"
    return None


# ---------------------------------------------------------------- summaries


def target_summary(session: Session) -> str:
    plan = session.target_plan
    lines = [f"roles ({len(plan.nodes)}):"]
    lines += [f"  {node_label(display(n.ref), n.provider):<32} [{n.contract}]" for n in plan.nodes] or ["  -"]
    held = sorted(display(h) for h in session.observed)
    lines.append(f"held states ({len(held)}): {', '.join(held) or '-'}")
    return "\n".join(lines)


def _action_label(session: Session, step) -> str:
    """The label of the action that runs a step (`docker.start`), from its impl."""
    for label, desc in session.catalog.action_descs.items():
        if desc.impl == step.impl:
            return label
    return display(step.key)


def _planned_steps(session: Session) -> tuple:
    return session.action_plan.steps if session.action_plan is not None else ()


def plan_summary(session: Session) -> str:
    lines = [target_summary(session).split("\nheld states")[0]]
    steps = _planned_steps(session)
    lines.append(f"steps ({len(steps)}):")
    for i, step in enumerate(steps, 1):
        needs = f"  after {display(', '.join(step.requires))}" if step.requires else ""
        lines.append(f"  {i:>2}. {display(', '.join(step.delivers))} by {_action_label(session, step)}{needs}")
    return "\n".join(lines)


# ---------------------------------------------------------------- planning without constructing


def _planned(args, show) -> int:
    """Resolve the target file in plan-only mode, in a scratch run directory unless `--run-dir` says where, and
    pass the session and the run directory to `show(session, run_dir)`. Nothing is constructed."""
    with tempfile.TemporaryDirectory(prefix="itf-plan-") as scratch:
        run_dir = args.run_dir or scratch
        try:
            session = session_of(args, run_dir=run_dir, plan_only=True)
        except ValueError as exc:
            print(f"itf: {exc}", file=sys.stderr)
            return 1
        failure = _resolve(session)
        if failure:
            print(failure, file=sys.stderr)
            return 1
        return show(session, run_dir)


def definition_problems(session: Session) -> list[str]:
    """Disagreements between the parts this target file uses and their contract definitions (when the optional
    contract library is there): a definition's required member the factory does not publish, majors that do not
    match, a name defined twice. Metadata only."""
    try:
        from score.itf import contracts
    except ImportError:
        return []
    catalog = session.catalog
    labels = {n.provider for n in session.target_plan.nodes}
    parts = [catalog.factories[label] for label in sorted(labels)]
    impls = {s.impl for s in _planned_steps(session)}
    parts += [d for d in catalog.action_descs.values() if d.impl in impls]
    mapped = contracts.contract_map(parts, definitions=contracts.load_list())
    return [d.message for entry in mapped.values() for d in entry.disagreements if d.kind != "missing-member"]


def _show_validation(session: Session, _run_dir) -> int:
    try:
        problems = definition_problems(session)
    except Exception as exc:  # noqa: BLE001 - a malformed definition file
        problems = [f"contract definitions cannot be read: {exc}"]
    for warning in session.warnings:
        print(f"warning: {warning}", file=sys.stderr)
    if problems:
        print(banner("ITF: target file rejected by its contract definitions", 100), file=sys.stderr)
        print("\n".join(f"  {p}" for p in problems), file=sys.stderr)
        return 1
    source = session.target_source
    print(
        f"ok: {source.describe() if source else 'empty target file'}: "
        f"{len(session.target_plan.nodes)} roles, {len(_planned_steps(session))} steps"
    )
    return 0


def cmd_validate(args) -> int:
    return _planned(args, _show_validation)


def cmd_plan(args) -> int:
    def show(session: Session, _run_dir) -> int:
        text = json.dumps(plan_document(session), indent=2, sort_keys=True, default=str)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        print(text if args.json else plan_summary(session))
        for warning in session.warnings:
            print(f"warning: {warning}", file=sys.stderr)
        return 0

    return _planned(args, show)


def cmd_graph(args) -> int:
    def show(session: Session, _run_dir) -> int:
        print(render_graph(session, args.kind, action_label=lambda step: _action_label(session, step)))
        return 0

    return _planned(args, show)


# ---------------------------------------------------------------- up, down, test


def undetachable(session: Session) -> str | None:
    """Why this target cannot be left running or taken down by a later process, or None when it can: every
    capability factory with a teardown must say (`observes`) that a factory built afresh sees what an earlier
    one created, so probes tell the truth and the teardown removes it."""
    catalog = session.catalog
    offenders = []
    for node in session.target_plan.nodes:
        factory = catalog.factories.get(node.provider)
        if factory is not None and factory.has_teardown and not factory.observable(dict(node.config)):
            offenders.append(f"{display(node.ref)} ({node.provider})")
    if not offenders:
        return None
    return (
        "this target cannot be left running or taken down by a later process: "
        f"{', '.join(offenders)} {'owns' if len(offenders) == 1 else 'own'} a teardown, and the factory does not "
        "say that a fresh instance observes "
        "what an earlier one created (`@capability(..., observes=True)`). Run `itf up` without --detach, "
        "which unwinds when you leave it."
    )


def _up(session: Session, args) -> int:
    """Bring `session` up and hold it (a console, or detached); the caller closes it."""
    failure = _resolve(session)
    if failure:
        print(failure, file=sys.stderr)
        return 1
    refusal = undetachable(session) if args.detach else None
    if refusal:
        print(f"itf: --detach refused: {refusal}", file=sys.stderr)
        return 1
    try:
        session.bring_up()
    except NotReady as exc:
        print(exc.failure.render() if exc.failure is not None else f"ITF: not ready: {exc}", file=sys.stderr)
        return 1
    print(target_summary(session))
    print(f"\nrun directory: {session.run_dir}")
    if args.detach:
        print("detached: the target keeps running; `itf down` takes it down")
    elif sys.stdin.isatty():
        code.interact(
            banner="itf: `target` and `session` are in scope; leave the console (Ctrl-D) to tear everything down.",
            local={"target": session.target, "session": session},
            exitmsg="itf: unwinding ...",
        )
    return 0


def cmd_up(args) -> int:
    args.run_dir = args.run_dir or default_run_dir()
    try:
        session = session_of(
            args, reuse="fresh" if args.fresh else "probe", on_exit="keep" if args.detach else "unwind"
        )
    except ValueError as exc:
        print(f"itf: {exc}", file=sys.stderr)
        return 1
    status = 0
    try:
        status = _up(session, args)
    except KeyboardInterrupt:
        print("\nitf: interrupted, unwinding ...", file=sys.stderr)
        status = 130
    finally:
        try:
            session.close()
        except KeyboardInterrupt:  # a second Ctrl-C while unwinding: finish the unwind anyway
            session.close()
        problems = session.close_problems()
        if problems is not None:
            print(problems.render(), file=sys.stderr)
            status = status or 1
        evidence = Path(session.run_dir) / HTML_NAME
        if evidence.is_file():
            print(f"evidence: {evidence}")
    return status


def _resolved_or_refused(session: Session) -> str | None:
    """Why `itf down` cannot act on `session` (not resolvable, or its target cannot be taken down later), or None."""
    failure = _resolve(session)
    if failure:
        return failure
    refusal = undetachable(session)
    return f"itf: down refused: {refusal}" if refusal else None


def _take_down(session: Session) -> int:
    held = sorted(display(h) for h in session.probe())
    session.close()
    report = session.unwind_report
    dismantled = [display(ref) for ref in (report.dismantled if report else ())]
    print(f"observed ({len(held)}): {', '.join(held) or '-'}")
    print(f"dismantled ({len(dismantled)}): {', '.join(dismantled) or '-'}")
    if not held:
        print("nothing held: the target was not up")
    problems = session.close_problems()
    if problems is not None:
        print(problems.render(), file=sys.stderr)
    return 1 if problems is not None else 0


def cmd_down(args) -> int:
    """A fresh session: its probes observe what holds, and the unwind removes what they observed."""
    args.run_dir = args.run_dir or default_run_dir()
    try:
        session = session_of(args, reuse="probe", on_exit="unwind")
    except ValueError as exc:
        print(f"itf: {exc}", file=sys.stderr)
        return 1
    problem = _resolved_or_refused(session)
    if problem:
        print(problem, file=sys.stderr)
        return 1
    return _take_down(session)


def _adapter_is_installed() -> bool:
    """A pip install registers the adapter as a pytest11 entry point; then `-p` would load it twice."""
    from importlib import metadata

    return any(ep.value.split(":")[0] == ADAPTER for ep in metadata.entry_points(group="pytest11"))


def cmd_test(args) -> int:
    """pytest with the target file given as options: what `pytest --itf-target=...` does, found as every
    other command finds it. The process environment is left alone."""
    import pytest

    try:
        found = find(args.target_file, args.override)
    except ValueError as exc:
        print(f"itf: {exc}", file=sys.stderr)
        return 1
    options = [f"--itf-target={found.target_file.value}"]
    options += [f"--itf-override={o.value}" for o in found.overrides]
    plugin = [] if _adapter_is_installed() else ["-p", ADAPTER]
    return int(pytest.main([*plugin, *options, *args.pytest_args]))


# ---------------------------------------------------------------- diff


def _read_plan(path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _nodes(plan: dict) -> dict:
    target = plan.get("target") or {}
    nodes = list(target.get("nodes", ()))
    for scope in (target.get("scopes") or {}).values():
        nodes += scope.get("nodes", ())
    return {f"{n['scope']}.{n['name']}": n for n in nodes}


def _steps(plan: dict) -> list:
    action = plan.get("action") or {}
    return list(action.get("steps", ()))


def _step_key(step: dict) -> str:
    return step.get("key") or f"{step.get('impl')}:{','.join(step.get('delivers', ()))}"


def _field_changes(old: dict, new: dict, prefix: str = "") -> list[str]:
    out = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a == b:
            continue
        if isinstance(a, dict) and isinstance(b, dict):
            out += _field_changes(a, b, f"{prefix}{key}.")
        else:
            out.append(f"{prefix}{key}: {json.dumps(a, sort_keys=True)} -> {json.dumps(b, sort_keys=True)}")
    return out


def _membership(kind: str, old: dict, new: dict, detail=lambda item: "") -> list[str]:
    """`+ <kind> <key>` for what only `new` has, then `- <kind> <key>` for what only `old` has."""
    added = [f"+ {kind} {key}{detail(new[key])}" for key in new if key not in old]
    removed = [f"- {kind} {key}{detail(old[key])}" for key in old if key not in new]
    return added + removed


def _changed(kind: str, old: dict, new: dict) -> list[str]:
    """`~ <kind> <key>` and the changed fields under it, for what both have and differs."""
    lines: list[str] = []
    for key in old:
        if key in new and old[key] != new[key]:
            lines.append(f"~ {kind} {key}")
            lines += [f"      {change}" for change in _field_changes(old[key], new[key])]
    return lines


def _reordered(old: dict, new: dict) -> list[str]:
    was = [k for k in old if k in new]
    now = [k for k in new if k in old]
    if was == now:
        return []
    return ["~ steps reordered:", f"      was {' -> '.join(was)}", f"      now {' -> '.join(now)}"]


def diff_plans(old: dict, new: dict) -> list[str]:
    roles_old, roles_new = _nodes(old), _nodes(new)
    steps_old, steps_new = ({_step_key(s): s for s in _steps(plan)} for plan in (old, new))
    lines = _membership("role", roles_old, roles_new, lambda n: f"  ({n['provider']})")
    lines += _changed("role", roles_old, roles_new)
    lines += _membership("step", steps_old, steps_new) + _changed("step", steps_old, steps_new)
    lines += _reordered(steps_old, steps_new)
    return lines + (["~ assumptions changed"] if old.get("assumptions") != new.get("assumptions") else [])


def cmd_diff(args) -> int:
    try:
        old, new = _read_plan(args.old), _read_plan(args.new)
    except (OSError, ValueError) as exc:
        print(f"itf: {exc}", file=sys.stderr)
        return 2
    lines = diff_plans(old, new)
    print("\n".join(lines) if lines else "plans are identical")
    return 1 if lines else 0


# ---------------------------------------------------------------- evidence


def cmd_evidence(args) -> int:
    try:
        if args.summary:
            print(render_summary(summarize(args.run_dirs)))
            return 0
        if len(args.run_dirs) != 1:
            print("itf evidence: give exactly one run directory (or --summary for several)", file=sys.stderr)
            return 2
        print(write_html(args.run_dirs[0], output=args.output))
        return 0
    except FileNotFoundError as exc:
        print(f"itf: {exc}", file=sys.stderr)
        return 1
    except PermissionError as exc:
        # Bazel's test outputs are read-only: the page goes elsewhere then.
        print(f"itf: cannot write {exc.filename}; give the page another place with --output FILE", file=sys.stderr)
        return 1


# ---------------------------------------------------------------- argument parsing


def _target_file_args(p, *, run_dir: bool = False) -> None:
    p.add_argument(
        "target_file",
        nargs="?",
        metavar="target",
        help="a YAML or JSON target file (default: the configured one: ITF_TARGET, itf_target, [tool.itf])",
    )
    p.add_argument(
        "--override",
        action="append",
        default=[],
        help="an override file merged by role over the target file (repeatable; default: ITF_OVERRIDE)",
    )
    if run_dir:
        p.add_argument("--run-dir", default=None, help="where run artifacts go")
        p.add_argument(
            "--artifacts",
            choices=("none", "standard", "full"),
            default=None,
            help="what the run directory gets: none, standard (default; what a person reads) or full (every file)",
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="itf", description="Integration Test Framework: work with a target file.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="compile the target file (every metadata check); exit 1 with diagnostics")
    _target_file_args(p, run_dir=True)
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("plan", help="resolve only and print the plan; exit 1 with diagnostics")
    _target_file_args(p, run_dir=True)
    p.add_argument("--json", action="store_true", help="print plan.json instead of the summary")
    p.add_argument("--output", help="also write plan.json here")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("graph", help="draw the topology and the bring-up sequence from metadata, as Mermaid")
    _target_file_args(p, run_dir=True)
    p.add_argument("--kind", choices=("topology", "sequence", "both"), default="both")
    p.set_defaults(func=cmd_graph)

    p = sub.add_parser("up", help="bring a target file up, print the target and open a Python console on it")
    _target_file_args(p, run_dir=True)
    p.add_argument("--fresh", action="store_true", help="run every planned action, ignoring what probes observe")
    p.add_argument("--detach", action="store_true", help="leave it running and exit; `itf down` takes it down")
    p.set_defaults(func=cmd_up)

    p = sub.add_parser("down", help="take down what probes observe (a fresh session; for observing factories only)")
    _target_file_args(p, run_dir=True)
    p.set_defaults(func=cmd_down)

    p = sub.add_parser(
        "test",
        help="run pytest on a target file: itf test [target] [--override FILE] [-- pytest arguments]",
    )
    _target_file_args(p)
    p.set_defaults(func=cmd_test, pytest_args=[])

    p = sub.add_parser("doctor", help="check the host prerequisites of the packs a target file names")
    _target_file_args(p)
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("diff", help="compare two plan.json files; exit 0 if identical, 1 otherwise")
    p.add_argument("old")
    p.add_argument("new")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("evidence", help="write evidence.html for a run, or summarize several runs")
    p.add_argument("run_dirs", nargs="+", metavar="run-dir")
    p.add_argument("--summary", action="store_true", help="aggregate several runs instead")
    p.add_argument("--output", help="where to write the page (default: evidence.html in the run directory)")
    p.set_defaults(func=cmd_evidence)

    from score.itf.cli.compat_cmd import add_compat
    from score.itf.cli.contracts_cmd import add_contracts
    from score.itf.cli.versions_cmd import add_versions

    add_contracts(sub)
    add_compat(sub)
    add_versions(sub)
    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if os.environ.get("BUILD_WORKING_DIRECTORY"):
        # `bazel run` starts in the runfiles; every path a person gives (and every default, like "here") means the
        # directory they ran it from.
        os.chdir(os.environ["BUILD_WORKING_DIRECTORY"])
    pytest_args: list[str] = []
    if argv[:1] == ["test"] and "--" in argv:
        # `itf test [target] [--override F] -- pytest arguments`: what follows `--` is pytest's.
        split = argv.index("--")
        argv, pytest_args = argv[:split], argv[split + 1 :]
    args = build_parser().parse_args(argv)
    if args.command == "test":
        args.pytest_args = pytest_args
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
