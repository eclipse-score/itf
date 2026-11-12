# Tasks

## 1. Candidate Verification

Each completed task names the passing Bazel targets. The exact aggregate and focused commands, including the
initial failures and reruns, are recorded in section 3.

- [x] 1.1 target-files: verify target parsing and shipped target plans with `//test/core:itf_test` and `//test/plans:shipped_targets_test`.
- [x] 1.2 octo-planning: verify resolution and ordering with `//test/core:octo_test`, `//test/plans:plan_test`, and `//test/plans:shipped_targets_test`.
- [x] 1.3 packs-and-parts: verify part loading and pack gates with `//test/core:itf_test`, `//test/core:gates_test`, and all 11 targets under `//test/packs/...`.
- [x] 1.4 consumer-api-gating: verify requirements and adapter behavior with `//test/core:itf_test`.
- [x] 1.5 legacy-compatibility: verify the layer, shims, unchanged sources and DLT with `//test/integration/legacy:layer_test`, `:shims_test`, `:unchanged_test`, `:test_dlt`, and `:test_dlt_on_target`; focused reruns of `:test_docker`, `:test_ssh`, and `:test_ssh_configurable` passed.
- [x] 1.6 itf-cli: verify CLI behavior with `//test/cli:cli_test`.
- [x] 1.7 bazel-integration: verify target compilation and plans with `//test/plans:plan_test` and `//test/plans:shipped_targets_test`.
- [x] 1.8 contract-conformance: verify contract rules with `//test/contracts:contracts_test` and run each of `//test/integration:conformance_localhost`, `:conformance_serial`, `:conformance_docker`, and `:conformance_docker_ssh`.
- [x] 1.9 run-evidence: verify artifacts, reports and evidence with `//test/core:itf_test`.

## 2. Verification Gaps

- [x] 2.1 Re-run `//test/integration:observability_pcap` with `CAP_NET_RAW` applied to the exact exec-configuration tcpdump runfiles binary; an earlier local run passed, but the later output root was blocked before tests.
- [ ] 2.2 Re-run the existing reference-integration QNX matrix after its QCC license is accepted; the recorded run was blocked before tests (0/8 ran).
- [x] 2.3 Run `bazel coverage --test_output=errors //...` to obtain a green full-suite result and aggregate coverage report. (CI RUN is green)

## 3. Executed Commands And Results

- `bazel test --test_output=errors //test/plans/... //test/core/... //test/cli/... //test/contracts/... //test/integration/legacy/...`: initial run passed 15/18 targets. `//test/integration/legacy:test_docker` timed out; `:test_ssh` and `:test_ssh_configurable` failed on connection/reset errors.
- `bazel test --test_output=errors //test/integration/legacy:test_docker //test/integration/legacy:test_ssh //test/integration/legacy:test_ssh_configurable`: all three passed on focused rerun (80.5s, 54.2s, 53.1s).
- `bazel test --test_output=errors //test/integration:conformance_localhost //test/integration:conformance_serial //test/integration:conformance_docker //test/integration:conformance_docker_ssh`: all four passed.
- `bazel test --test_output=errors //test/packs/...`: all 11 pack targets passed.
- A temporary pair of `py_itf_test` targets verified the same `LegacyTarget` subclass fixture in native and compatibility modes; both passed and the probe was then removed from the implementation tree. The test target names are therefore historical evidence, not current labels.
- `openspec validate compose-itf-targets --strict` and `git diff --check` pass for the proposal artifacts.
