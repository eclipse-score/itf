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
"""Planning benchmark: how long ITF and OCTO take to plan a target file, and how much memory, without bringing
anything up. See README.md beside this file.

    plan_bench.py [TARGET_FILE...] [--scale KIND,...] [--sizes N,...] [--reps N] [--no-cold]
                  [--env NAME=VALUE]... [--artifacts none|standard|full] [--report FILE] [--check]
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass, field
from pathlib import Path

PHASES = (
    ("load", "_load_target_file", "read the YAML, merge includes and overrides, expand ${NAME}"),
    ("declare", "_declare_parts", "load the packs and the policy, publish their parts"),
    ("compile", None, "turn the target file into claims"),
    ("octo_gate1", None, "OCTO gate 1: what must exist"),
    ("octo_gate2", None, "OCTO gate 2: what must happen"),
    ("dry_run", "_dry_run_check", "resolve every implementation reference, construct nothing"),
    ("artifacts", "_write_artifacts", "write the run directory (per --artifacts)"),
)
KINDS = ("scopes", "chain", "deep", "wide")

# Warn above these (see README.md for where they come from).
THRESHOLDS = {
    "cold_s": (2.0, "a fresh process plans one target file"),
    "warm_ms": (250.0, "a running process plans one target file"),
    "gate_ms": (100.0, "one OCTO gate"),
    "peak_mib": (50.0, "memory allocated while planning"),
}

_TIMES: dict[str, float] = {}


def _timed(name, fn):
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            _TIMES[name] = _TIMES.get(name, 0.0) + time.perf_counter() - start

    return wrapper


def _instrument():
    """Time each planning phase of Session.resolve and OCTO's gates; returns the session module."""
    from score.itf.core import octo
    from score.itf.core import session as session_mod
    from score.itf.core.frontends import target_file

    for key, attr, _ in PHASES:
        if attr:
            setattr(session_mod.Session, attr, _timed(key, getattr(session_mod.Session, attr)))
    octo.resolve_target = _timed("octo_gate1", octo.resolve_target)
    octo.resolve_actions = _timed("octo_gate2", octo.resolve_actions)
    target_file.compile = _timed("compile", target_file.compile)
    return session_mod


def _resolve(session_mod, path: str, artifacts: str, run_dir: Path):
    from score.itf.core.frontends.target_source import load_policy

    policy = Path(path).with_name("policy.py")
    roots = [load_policy(policy)] if policy.is_file() else []
    session = session_mod.Session(roots, target=path, plan_only=True, artifacts=artifacts, run_dir=run_dir)
    return session.resolve()


@dataclass
class Result:
    name: str
    roles: int = 0
    steps: int = 0
    warm_ms: float = 0.0
    warm_p90_ms: float = 0.0
    phases_ms: dict = field(default_factory=dict)
    peak_kib: float = 0.0
    cold_s: float | None = None
    cold_import_ms: float | None = None
    cold_rss_mib: float | None = None
    error: str = ""

    @property
    def gate_ms(self) -> float:
        return max(self.phases_ms.get("octo_gate1", 0.0), self.phases_ms.get("octo_gate2", 0.0))

    @property
    def peak_mib(self) -> float:
        return self.peak_kib / 1024


def warm(session_mod, name: str, path: str, reps: int, artifacts: str) -> Result:
    """`reps` resolves after a first one that imports everything: medians per phase and in total, and the peak
    memory allocated by one more."""
    result = Result(name)
    run_dir = Path(tempfile.mkdtemp(prefix="itf-bench-run-"))
    try:
        _resolve(session_mod, path, artifacts, run_dir)
        totals, phases = [], {}
        for _ in range(reps):
            _TIMES.clear()
            gc.collect()
            start = time.perf_counter()
            session = _resolve(session_mod, path, artifacts, run_dir)
            totals.append((time.perf_counter() - start) * 1000)
            for key, value in _TIMES.items():
                phases.setdefault(key, []).append(value * 1000)
        tracemalloc.start()
        _resolve(session_mod, path, artifacts, run_dir)
        result.peak_kib = tracemalloc.get_traced_memory()[1] / 1024
        tracemalloc.stop()
    except Exception as exc:  # noqa: BLE001 - one target file that does not plan is reported, the rest still run
        result.error = f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
        return result
    result.roles = len(session.target_plan.nodes)
    result.steps = len(session.action_plan.steps)
    result.warm_ms = statistics.median(totals)
    result.warm_p90_ms = sorted(totals)[max(0, int(len(totals) * 0.9) - 1)]
    result.phases_ms = {key: statistics.median(values) for key, values in phases.items()}
    return result


def cold(path: str, artifacts: str, env: dict) -> dict:
    """One fresh interpreter planning `path` once: imports included, as one `itf validate` or Bazel step."""
    code = (
        "import time, json, resource, sys; t0 = time.perf_counter()\n"
        "import score.itf.core; t1 = time.perf_counter()\n"
        f"sys.argv = ['plan_bench', '--cold-one', {path!r}, '--artifacts', {artifacts!r}]\n"
        "import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('plan_bench', {str(Path(__file__).resolve())!r})\n"
        "m = importlib.util.module_from_spec(spec); sys.modules['plan_bench'] = m; spec.loader.exec_module(m)\n"
        "m.cold_one(t0, t1)\n"
    )
    environment = {**os.environ, **env, "PYTHONPATH": os.pathsep.join(p for p in sys.path if p)}
    start = time.perf_counter()
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=environment)
    wall = time.perf_counter() - start
    if done.returncode != 0:
        return {"error": (done.stderr.strip().splitlines() or ["failed"])[-1][:160]}
    data = json.loads(done.stdout.strip().splitlines()[-1])
    data["wall_s"] = wall
    return data


def cold_one(t0: float, t1: float) -> None:
    """In the child of `cold`: plan once and print the numbers as one JSON line."""
    args = sys.argv
    session_mod = _instrument()
    start = time.perf_counter()
    _resolve(session_mod, args[2], args[4], Path(tempfile.mkdtemp(prefix="itf-bench-run-")))
    print(
        json.dumps(
            {
                "import_ms": (t1 - t0) * 1000,
                "first_plan_ms": (time.perf_counter() - start) * 1000,
                "rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
            }
        )
    )


# ---------------------------------------------------------------- synthetic target files


def synthetic(kind: str, n: int, where: Path) -> str:
    """A target file (and a policy) of size `n` along one axis:
    scopes: n devices of 4 localhost roles; chain: n actions in one sequence; deep: n factories each needing the
    previous one; wide: n independent roles and n goals."""
    if kind == "scopes":
        lines = ["capabilities:", "  platform: localhost.platform", "  command: localhost.exec", "goals:"]
        lines += ["  - platform.up", "scopes:"]
        for i in range(n):
            lines += [f"  d{i}:", "    capabilities:", "      platform: localhost.platform"]
            lines += [
                "      command: localhost.exec",
                "      process: localhost.process",
                "      files: localhost.files",
            ]
            lines += ["    goals:", "      - platform.up"]
        (where / "target.itf.yaml").write_text("\n".join(lines) + "\n")
        return str(where / "target.itf.yaml")
    code = ["from typing import Protocol", "from score.itf.core import capability, state", ""]
    thing = [
        "class Thing:",
        "    def touch(self) -> None: ...",
        "class ThingP(Protocol):",
        "    __contract__ = 'bench.thing'",
        "    def touch(self) -> None: ...",
        "@capability('bench.thing')",
        "def thing() -> Thing:",
        "    return Thing()",
    ]
    if kind == "chain":
        code += thing
        for i in range(n):
            after = f", after=('s.{i - 1}',)" if i else ""
            code += [f"@state('s.{i}'{after})", f"def step_{i}(thing: ThingP) -> None:", "    thing.touch()"]
            code += [f"@step_{i}.probe", f"def held_{i}(thing: ThingP) -> bool:", "    return False"]
        lines = ["capabilities:", "  thing: local.thing", "goals:", f"  - s.{n - 1}"]
    elif kind == "deep":
        for i in range(n):
            code += [f"class T{i}:", "    def use(self) -> None: ...", f"class P{i}(Protocol):"]
            code += [f"    __contract__ = 'bench.c{i}'", "    def use(self) -> None: ..."]
        for i in range(n):
            slot = f"prev: P{i - 1}" if i else ""
            code += [f"@capability('bench.c{i}')", f"def f{i}({slot}) -> T{i}:", f"    return T{i}()"]
        lines = ["capabilities:"] + [f"  r{i}: local.f{i}" for i in range(n)]
    elif kind == "wide":
        code += thing
        for i in range(n):
            code += [f"@capability('bench.w{i}')", f"def w{i}() -> Thing:", "    return Thing()"]
            code += [f"@state('w.{i}')", f"def make_{i}(t: ThingP) -> None:", "    t.touch()"]
        lines = ["capabilities:", "  thing: local.thing"] + [f"  r{i}: local.w{i}" for i in range(n)]
        lines += ["goals:"] + [f"  - w.{i}" for i in range(n)]
    else:
        raise ValueError(f"unknown kind {kind!r}; the kinds are {', '.join(KINDS)}")
    (where / "policy.py").write_text("\n".join(code) + "\n")
    (where / "target.itf.yaml").write_text("\n".join(lines) + "\n")
    return str(where / "target.itf.yaml")


# ---------------------------------------------------------------- tables and the report


def table(headers: list[str], rows: list[list], markdown: bool) -> str:
    cells = [[str(c) for c in headers]] + [[str(c) for c in row] for row in rows]
    if markdown:
        lines = ["| " + " | ".join(cells[0]) + " |", "|" + "|".join("---" for _ in headers) + "|"]
        return "\n".join(lines + ["| " + " | ".join(r) + " |" for r in cells[1:]])
    widths = [max(len(r[i]) for r in cells) for i in range(len(headers))]
    numeric = [all(_is_number(r[i]) for r in cells[1:]) and len(cells) > 1 for i in range(len(headers))]

    def line(r):
        return "  ".join(c.rjust(w) if num else c.ljust(w) for c, w, num in zip(r, widths, numeric)).rstrip()

    return "\n".join([line(cells[0]), "  ".join("-" * w for w in widths)] + [line(r) for r in cells[1:]])


def _is_number(text: str) -> bool:
    try:
        float(text.rstrip("%"))
    except ValueError:
        return text == "-"
    return True


def _ms(value) -> str:
    return "-" if value is None else f"{value:.2f}"


def over(result: Result) -> list[str]:
    """The thresholds `result` exceeds, as text."""
    found = []
    for key, (limit, what) in THRESHOLDS.items():
        value = getattr(result, key)
        if value is not None and not result.error and value > limit:
            found.append(f"{result.name}: {what}: {value:.2f} > {limit:g} ({key})")
    return found


def summary_rows(results) -> list[list]:
    rows = []
    for r in results:
        if r.error:
            rows.append([r.name, "-", "-", "error", "-", "-", "-", "-", r.error[:60]])
            continue
        verdict = "over" if over(r) else "ok"
        cold_s = "-" if r.cold_s is None else f"{r.cold_s:.2f}"
        rows.append(
            [r.name, r.roles, r.steps, _ms(r.warm_ms), cold_s, _ms(r.gate_ms), f"{r.peak_mib:.2f}", verdict, ""]
        )
    return rows


SUMMARY_HEADERS = ["target", "roles", "steps", "warm ms", "cold s", "max gate ms", "peak MiB", "thresholds", "note"]


def report(results, args, markdown: bool) -> str:
    """The whole report: environment, summary, phases, cold starts, thresholds."""
    h = (lambda t: f"## {t}") if markdown else (lambda t: f"{t}\n{'=' * len(t)}")
    ok = [r for r in results if not r.error]
    out = ["# ITF planning benchmark" if markdown else "ITF planning benchmark", ""]
    out += [h("Environment"), ""]
    out += [
        table(
            ["what", "value"],
            [
                ["python", platform.python_version()],
                ["machine", f"{platform.machine()}, {os.cpu_count()} CPUs"],
                ["system", platform.platform()],
                ["repetitions (warm)", args.reps],
                ["artifacts", args.artifacts],
            ],
            markdown,
        ),
        "",
    ]
    out += [h("Summary"), "", table(SUMMARY_HEADERS, summary_rows(results), markdown), ""]
    if ok:
        rows = [[r.name] + [_ms(r.phases_ms.get(key)) for key, _, _ in PHASES] for r in ok]
        out += [h("Warm plan by phase (median ms)"), ""]
        out += [table(["target"] + [key for key, _, _ in PHASES], rows, markdown), ""]
        out += [table(["phase", "what it does"], [[k, d] for k, _, d in PHASES], markdown), ""]
        shares = []
        for key, _, _ in PHASES:
            values = [r.phases_ms.get(key, 0.0) / r.warm_ms for r in ok if r.warm_ms]
            shares.append([key, f"{statistics.median(values) * 100:.1f}%" if values else "-"])
        out += [h("Median share of a warm plan"), "", table(["phase", "share"], shares, markdown), ""]
    colds = [r for r in ok if r.cold_s is not None]
    if colds:
        rows = [[r.name, _ms(r.cold_import_ms), f"{r.cold_s:.2f}", f"{r.cold_rss_mib:.1f}"] for r in colds]
        out += [h("Fresh process (imports included)"), ""]
        out += [table(["target", "import core ms", "wall s", "peak RSS MiB"], rows, markdown), ""]
    limits = [[key, f"{limit:g}", what] for key, (limit, what) in THRESHOLDS.items()]
    out += [h("Thresholds"), "", table(["measure", "warn above", "what"], limits, markdown), ""]
    exceeded = [line for r in results for line in over(r)]
    out += ["Exceeded:" if exceeded else "No threshold exceeded."]
    out += [f"- {line}" for line in exceeded]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- the command


def _root() -> Path:
    return Path(os.environ.get("BUILD_WORKING_DIRECTORY") or os.getcwd())  # `bazel run` starts in the runfiles


def _inputs(args) -> list[tuple[str, str]]:
    """(name, target file) for each file given and each synthetic size asked for."""
    found = []
    for value in args.targets:
        path = Path(value) if Path(value).is_absolute() else _root() / value
        found.append((value, str(path)))
    for kind in [k for k in (args.scale or "").split(",") if k]:
        for n in [int(s) for s in args.sizes.split(",") if s]:
            where = Path(tempfile.mkdtemp(prefix=f"itf-bench-{kind}-{n}-"))
            found.append((f"{kind}-{n}", synthetic(kind, n, where)))
    return found


def parse(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="plan_bench", description="Benchmark planning (no bring-up) of target files.")
    p.add_argument("targets", nargs="*", help="target files to plan (a policy.py beside one is loaded)")
    p.add_argument("--scale", help=f"synthetic target files, comma separated: {', '.join(KINDS)}")
    p.add_argument("--sizes", default="10,50,100", help="sizes for --scale (default: 10,50,100)")
    p.add_argument("--reps", type=int, default=15, help="warm repetitions per target file (default: 15)")
    p.add_argument("--no-cold", action="store_true", help="skip the fresh-process measurement")
    p.add_argument("--env", action="append", default=[], metavar="NAME=VALUE", help="a ${NAME} value (repeatable)")
    p.add_argument(
        "--artifacts", choices=("none", "standard", "full"), default="none", help="run files (default: none)"
    )
    p.add_argument("--report", metavar="FILE", help="write the full report (Markdown) here; print a summary")
    p.add_argument("--check", action="store_true", help="exit 1 when a threshold is exceeded")
    p.add_argument("--cold-one", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    if not args.targets and not args.scale:
        p.error("give target files, --scale, or both")
    return args


def main(argv=None) -> int:
    args = parse(argv)
    env = dict(item.split("=", 1) for item in args.env)
    os.environ.update(env)
    session_mod = _instrument()
    results = []
    for name, path in _inputs(args):
        print(f"planning {name} ...", file=sys.stderr, flush=True)
        result = warm(session_mod, name, path, args.reps, args.artifacts)
        if not result.error and not args.no_cold:
            data = cold(path, args.artifacts, env)
            if "error" not in data:
                result.cold_s = data["wall_s"]
                result.cold_import_ms = data["import_ms"]
                result.cold_rss_mib = data["rss_mib"]
        results.append(result)
    if args.report:
        path = Path(args.report) if Path(args.report).is_absolute() else _root() / args.report
        path.write_text(report(results, args, markdown=True), encoding="utf-8")
        print(table(SUMMARY_HEADERS, summary_rows(results), markdown=False))
        print(f"\nreport: {path.resolve().as_uri()}")
    else:
        print(report(results, args, markdown=False))
    exceeded = any(over(r) for r in results)
    return 1 if args.check and (exceeded or any(r.error for r in results)) else 0


if __name__ == "__main__":
    if "--cold-one" in sys.argv:
        raise SystemExit("--cold-one is internal")
    sys.exit(main())
