## Why

ITF on `origin/main` models a target as an environment-specific Python `Target` subclass and pytest plugin. As
platforms and execution paths multiply, setup order and capability differences are hidden in plugin code, and
configuration errors can surface only after resources have started. This proposal makes target composition
declarative and checkable before test execution while preserving existing public entry points.

## Intended Outcome, Scope, And Non-Goals

**Outcome:** A target is described by roles, providers, settings and goals; ITF validates a plan before creating
resources, and one test suite can run against targets that meet its declared API requirements.

**Scope:** target files and policies; packs and their capability factories/actions; planning and lifecycle;
consumer-owned requirements and deselection; contracts and conformance; CLI and Bazel integration; run evidence;
and compatibility for the original plugins, options, fixtures, imports and labels.

**Non-goals:** prescribe the implementation's PR or commit sequence; remove the original API in this change;
require maintainers to adopt the reference implementation's exact module layout; or claim every host-dependent
integration path is covered by ordinary CI.

## What Changes

- Describe composed targets in `*.itf.yaml` files, with explicit roles, settings, goals, relations, policies,
  scopes, includes and overrides.
- Validate factories, slots, shapes and settings, then resolve goal actions and ordering into a plan before
  bring-up.
- Let tests declare consumer-owned API shapes and target roles; preflight compatible providers and explain
  test deselection when a target lacks a requirement.
- Provide versioned contracts, project contract rules, provider conformance, inspection and lifecycle commands,
  Bazel target/test rules, and per-run evidence.
- Keep the legacy entry points available through the compatibility layer. Document known semantic differences
  in the migration guide; do not silently remove public plugins, options, fixtures, imports or labels.

## Capabilities

### New Capabilities

- `target-files`: target-file syntax, composition, policies and secret references.
- `octo-planning`: validated plans, state assumptions, goals and action order.
- `packs-and-parts`: pack discovery, capability factories, actions and probes.
- `consumer-api-gating`: test role/API requirements, preflight and deselection.
- `legacy-compatibility`: continued legacy entry points and facade extension behavior.
- `itf-cli`: target inspection, lifecycle, compatibility and contract commands.
- `bazel-integration`: build-time target validation and test binding.
- `contract-conformance`: versioned contracts, rules and provider checks.
- `run-evidence`: per-run plans, observations and reports.

### Modified Capabilities

None. `openspec/specs/` has no existing capabilities; these are new behavioral specifications.

## Impact

The reference implementation touches `score/itf/{core,packs,cli,compat,contracts}`, Bazel macros, tests, docs and
examples. That file layout is evidence about one implementation, not a required integration structure. Existing
legacy tests are intended to retain their bodies while their BUILD wiring runs through the compatibility path.
Technical boundaries and alternatives are in [design.md](design.md); requirement-level behavior is in the
capability specs.

## Reference Comparison And Verification

The proposal was derived by comparing these immutable snapshots:

| Snapshot | Ref | Commit |
|---|---|---|
| Baseline | `origin/main` | `33e1af4114f1e94d14986beb20bbdcf8ba971f3f` |
| Candidate evidence | `ihsa_itf_platform_bc` | `e12eda1ab65414932de090b87bf93365a99ec763` |

Evidence and gaps are tracked in [tasks.md](tasks.md). The initial targeted Bazel run passed 15/18 targets;
focused reruns later passed the three Docker-backed legacy targets and four conformance targets, and all 11
targets under `//test/packs/...` passed. A temporary subclass probe also passed in both native and compatibility
modes; its result is retained in the design, not as implementation code. These results do not establish a
green full-suite coverage run. Pcap needs `CAP_NET_RAW` on its exact runfiles binary, and QEMU/QNX requires
licensed tooling.

## Alternatives And Open Questions

The principal alternatives and their rationale are summarized in [design.md](design.md): retain per-environment
plugins and subclasses; use shared provider interfaces instead of consumer-owned API shapes; or discover policy
modules implicitly instead of listing them in target files.

- How long must the compatibility layer remain supported after deprecation: two minor releases, or until a
  published date?
- After removal from ITF, should the compatibility layer be published as a separate package?
