## ADDED Requirements

### Requirement: Tests require roles
A test SHALL declare the roles and API shape it needs, and SHALL use the result as `target.<role>`. The same test SHALL be runnable on any target that offers the required roles.

#### Scenario: Same test, two targets
- **WHEN** a test requires `command` and two targets offer it (host and container)
- **THEN** the test runs on both

### Requirement: Consumer owns the API
Providers SHALL accept every call the consumer's declared Protocol makes. Providers MAY offer extra members and optional parameters. Callable checks SHALL validate argument structure, not return types or semantics.

#### Scenario: Provider with extra members
- **WHEN** a provider offers more methods than the consumer declares
- **THEN** the requirement is satisfied

#### Scenario: Incompatible provider
- **WHEN** a provider does not accept a declared call
- **THEN** the requirement is not satisfied

### Requirement: Grouped preflight
ITF SHALL check test requirements against the target before bring-up. Strict mode SHALL reject incompatible or unknown applicable APIs; loose mode SHALL deselect them.

#### Scenario: Strict mode
- **WHEN** strict mode is on and a required API is incompatible
- **THEN** the run fails before any bring-up

#### Scenario: Loose mode
- **WHEN** loose mode is on and a required API is incompatible
- **THEN** the test is deselected

### Requirement: Deselection states the reason
A test whose required roles a target cannot offer SHALL be deselected, and the reason SHALL be reported.

#### Scenario: Missing role
- **WHEN** a test requires `console` and the target has none
- **THEN** the test is deselected with the reason naming `console`

### Requirement: Shared minimum
Module-level requirements SHALL declare a minimum shared by all tests of the module; function-level requirements SHALL add only test-specific APIs.

#### Scenario: Additive requirements
- **WHEN** a module requires `command` and a test adds `files`
- **THEN** that test requires both

### Requirement: Policy-wide guarantees
A policy expectation SHALL validate every matching capability in every session scope even if no test uses it, SHALL NOT create or require roles that are absent, and a violation SHALL fail resolution.

#### Scenario: Unused capability violates expectation
- **WHEN** a policy expects a shape and an unused capability does not meet it
- **THEN** resolution fails
