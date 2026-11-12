## ADDED Requirements

### Requirement: Plan before anything starts
ITF SHALL resolve a target file into a plan, covering which factory fills which role and which actions run in which order, before any resource is created. Resolution SHALL require no hardware.

#### Scenario: Plan without hardware
- **WHEN** `itf plan` runs on a QEMU target file on a host without QEMU
- **THEN** the plan is printed and no machine is started

### Requirement: Gate 1 checks what must exist
Resolution SHALL fail when a factory's slot has no candidate role, has more than one candidate without a `bind:`, when a factory's settings do not match its schema, or when a provided shape does not satisfy the slot's shape.

#### Scenario: Ambiguous slot
- **WHEN** two roles fit one slot and no `bind:` is given
- **THEN** resolution fails naming both candidate roles and the `bind:` to write

### Requirement: Gate 2 checks what must happen
Resolution SHALL select an action for each goal and order actions by their own `after`/`breaks` plus the target file's `relations:`. A relation that names a state that no listed action makes true and that is not assumed SHALL be a compile error. A goal that two actions could satisfy SHALL require `by:`.

#### Scenario: Order from relations
- **WHEN** `relations:` states `shell.open` after `platform.up`
- **THEN** the plan places the `shell.open` action after the `platform.up` action

#### Scenario: Unsatisfied relation
- **WHEN** a relation names a state that nothing makes true
- **THEN** resolution fails at gate 2

### Requirement: Assumed states
A state listed under `assume:` SHALL be treated as true without an action, and SHALL record its owner and reason.

#### Scenario: Assumed platform
- **WHEN** `platform.up` is assumed with an owner and reason
- **THEN** no action is planned for it and the plan shows the assumption

### Requirement: Observed state with probes
Every state SHALL have a probe that checks it without changing anything. During bring-up ITF SHALL keep what already holds, and teardown SHALL undo only what ITF did.

#### Scenario: Already-true state
- **WHEN** a probe reports a state already holds
- **THEN** its action is skipped

#### Scenario: Teardown scope
- **WHEN** a target was brought up partly by ITF and partly pre-existing
- **THEN** `itf down` undoes only what ITF made true

### Requirement: Versioned states
State tokens with a major (for example `ready@1` and `ready@2`) SHALL stay distinct through planning and execution, with no suffix stripping and no implicit latest. Reports SHALL retain the state major.

#### Scenario: Distinct majors
- **WHEN** an action makes `ready@1` true and a goal requests `ready@2`
- **THEN** the goal is not satisfied by that action
