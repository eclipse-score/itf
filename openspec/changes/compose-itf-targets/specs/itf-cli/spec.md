## ADDED Requirements

### Requirement: Inspection commands need no hardware
`itf validate` SHALL compile a target file and exit 1 with diagnostics on failure. `itf plan` SHALL print the plan and exit 1 on failure. `itf graph` SHALL draw topology and bring-up sequence as Mermaid.

#### Scenario: Invalid target
- **WHEN** `itf validate` runs on an invalid target file
- **THEN** it prints diagnostics and exits 1

### Requirement: Lifecycle commands
`itf up` SHALL bring a target up, print it and open a Python console on it. `itf down` SHALL take down what probes observe. `itf test` SHALL run tests against a target file.

#### Scenario: Up and down
- **WHEN** `itf up` brings up a target and `itf down` runs later in a fresh session
- **THEN** observed resources are removed

### Requirement: Plan diff
`itf diff` SHALL compare two `plan.json` files and exit 0 when identical, 1 otherwise, listing changes in roles, steps and order.

#### Scenario: Reordered step
- **WHEN** two plans differ only in step order
- **THEN** `itf diff` exits 1 and reports the reordering

### Requirement: Doctor
`itf doctor` SHALL check host prerequisites of the packs a target file names.

#### Scenario: Missing prerequisite
- **WHEN** a named pack needs a binary the host lacks
- **THEN** `itf doctor` reports it

### Requirement: Version inventory
`itf versions` SHALL inventory and check capability majors and state majors.

#### Scenario: Inconsistent versions
- **WHEN** a consumer pins a major no provider offers
- **THEN** `itf versions check` fails

### Requirement: Contract commands
`itf contracts` SHALL provide `map`, `new` and `check`, where `check` enforces project rules from a rules file.

#### Scenario: Rule violation
- **WHEN** `itf contracts check --rules rules.yaml` finds a violation
- **THEN** it reports it and exits non-zero
