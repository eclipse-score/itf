# Version Reporting

ITF has two versioning layers. Build tools resolve artifact versions; ITF checks and reports contract compatibility.
Do not infer compatibility between a pack and the core from their release numbers.

## Runtime Compatibility And Policy

Capability factories offer `contract@major`; consumer Protocols and `itf.requires` may require that major.
Grouped test preflight compares each exact requirement profile with the chosen provider. An explicit
different major is a separate API family, not evidence that the implementation is broken. A provider with
no declared major cannot satisfy a versioned test requirement: loose mode deselects it as unknown, while
strict preflight rejects the collected run before bring-up. Within a matching family, callable structure
still has to satisfy the consumer; declaring a version does not waive shape checks.

Infrastructure policy can declare `itf_expect = [ConsoleAPI]`, using consumer-owned Protocols with
`__contract__`. These are conditional session invariants on every matching capability in every scope,
including unused roles. Multiple declarations compose independently. An unversioned policy baseline
applies across majors; `name@1` applies only to explicitly offered major 1 and rejects an unknown major.
Policy violations always reject resolution, independent of loose/strict test selection.

## State Contract Versions

State versions are explicit state tokens throughout planning and execution:

```python
@itf.state("service.ready@2", after=("platform.up@1",), breaks=("service.ready@1",))
def prepare_service(platform: Platform) -> None:
    ...
```

```yaml
goals:
  - service.ready@2
```

The action decorator preserves the full token. Goals, `after`, `also`, `breaks`, relations, assumptions,
probes and `session.reach` must use the intended version explicitly. `service.ready`, `service.ready@1`
and `service.ready@2` are distinct states; an unversioned goal is not an alias for the latest major.
Two versioned producers can coexist without collapsing into one ambiguous unversioned producer.
The contract inventory groups the base name for reporting and retains each delivery/requirement's major.
`versions check --require-major` governs both capability and state namespaces.

Runtime state resolution is version-exact, whereas capability wiring selects a factory explicitly and
then checks consumer requirements against its published major. Neither mechanism negotiates versions
or chooses a latest release implicitly. This fixes the former decorator behavior that silently discarded
the primary state's `@major` while goals and relations retained it.

## Report

From the project checkout:

```bash
itf versions report
itf versions report target.itf.yaml --tests test --json --output itf-run/versions.json
```

The report includes the Bzlmod module name/version, installed Python distribution version when available, Git
revision/tag/worktree status, pinned Bazel dependencies, lockfile SHA-256 digests, loaded pack versions, contract
definition versions, provider/consumer/test majors, and disagreements. With targets, it reports those targets' packs;
without targets, it inventories known packs. An import or optional dependency failure is retained as an inventory
error rather than hidden. Lockfile entries include the resolved Python package pins as well as their digest.

## Check

`itf versions check` fails on declared contract-major mismatches and duplicate definitions. It reports undeclared
majors; teams can require them for governed capability and state namespaces:

```bash
itf versions check --rules tools/contract_rules.yaml --tests test
itf versions check --tests test --require-major exec --require-major platform
```

`--require-major` is a command-line override; the shared `require_major` policy lives in the rules file. Keep that
list empty or add namespaces as contracts are migrated. Definition version is the
latest major described, not a package version. `itf contracts check --rules ...` continues to enforce project rules
such as required definitions, fixed roles and forbidden deprecated contracts; conformance checks validate behavior.
In development mode, unavailable optional packs are reported as inventory warnings and the JSON check marks
`complete: false`; declared-version consistency is distinct from inventory completeness. Release mode treats an
incomplete inventory as a failure.

For a release, declare the same version in `MODULE.bazel`, create an exact matching Git tag (`1.2.3` or `v1.2.3`),
and run:

```bash
itf versions check --release-version 1.2.3
```

Release mode requires matching module/tag versions, a clean working tree, a matching installed Python distribution
version when one is present, versioned packs and a complete inventory. Development builds may be unreleased; their
commit and dirty state still appear in the report. Dependency versions and lockfiles remain owned by Bazel/pip.