## ADDED Requirements

### Requirement: Contract library
ITF SHALL ship a library of canonical contract specifications, and every built-in pack SHALL reference them. Shared specifications SHALL load once; independently authored definitions with the same name SHALL stay visible to duplicate-definition checks.

#### Scenario: Duplicate definition
- **WHEN** two independent files define the same contract name
- **THEN** the duplicate-definition check reports it

### Requirement: Capability majors guide compatibility
A pinned consumer SHALL require an explicitly offered matching major, checked by preflight and policy.

#### Scenario: Missing major
- **WHEN** a consumer pins `exec.command@2` and only `@1` is offered
- **THEN** preflight fails

### Requirement: Contract rules
A project's contract rules SHALL be enforceable with `itf contracts check`, and generic contract, CLI and catalog functionality SHALL work without the optional conformance implementation.

#### Scenario: No conformance installed
- **WHEN** the conformance library is absent
- **THEN** contract and catalog commands still pass

### Requirement: Provider conformance
A contract MAY carry a conformance suite; ITF SHALL run it against a provider through CLI and pytest runners, and a vendor provider SHALL be checkable with built-in metadata but without built-in providers installed.

#### Scenario: Vendor provider
- **WHEN** conformance runs for an external vendor pack
- **THEN** its checks run and pass or fail on that provider's behavior

### Requirement: Generated catalog
ITF SHALL generate a contract map and catalog consistent with the contracts in use, and a check SHALL fail when the generated pages are stale.

#### Scenario: Stale catalog
- **WHEN** a contract changes and the catalog is not regenerated
- **THEN** the consistency check fails
