## ADDED Requirements

### Requirement: Original API remains available
The original plugins, command-line options, fixtures, import paths and Bazel labels SHALL continue to work, served over the same engine.

#### Scenario: Unchanged legacy tests
- **WHEN** ITF's legacy test bodies from `origin/main` run
- **THEN** they pass without source changes

### Requirement: Legacy test sources are guarded
A source-hash gate SHALL fail when a legacy test body differs from its `origin/main` version.

#### Scenario: Modified legacy test
- **WHEN** a legacy test body changes
- **THEN** the gate fails

### Requirement: Compatibility lives in one package
The compatibility layer SHALL be in a single package; original module paths SHALL only re-export from it and the packs, and a test SHALL enforce this.

#### Scenario: Shim with logic
- **WHEN** an original module path contains logic beyond re-exporting
- **THEN** the shim check fails

### Requirement: Layer activates implicitly and announces itself
The layer SHALL switch on through the entry points a project already uses, without a setting, and SHALL state this once per run.

#### Scenario: Notice once
- **WHEN** a legacy suite runs
- **THEN** the compatibility notice appears exactly once

### Requirement: Migration aids
`itf compat report` SHALL list what a suite still uses of the original API, and `itf compat target` SHALL write the target file the legacy options imply.

#### Scenario: Generated target file
- **WHEN** `itf compat target` runs with legacy Docker options
- **THEN** a target file equivalent to those options is written

### Requirement: Facade for custom target classes
A project's own target class SHALL be usable as a facade over target roles; this mechanism SHALL remain when the compatibility layer is removed.

#### Scenario: Facade over roles
- **WHEN** a project class declares a facade over roles `command` and `files`
- **THEN** its methods are served by those roles

### Requirement: Projects can extend the legacy target explicitly
A project SHALL be able to subclass the legacy target facade, add project methods, and export an instance by overriding the pytest `target` fixture around its parent fixture. The resulting object SHALL retain legacy methods and expose the composed target roles. ITF SHALL NOT imply that the compatibility plugin automatically discovers project subclasses.

#### Scenario: Extension used through both APIs
- **WHEN** the same fixture-wrapped subclass is used with a legacy plugin target and a native target-file test
- **THEN** the project method, a legacy method such as `execute`, and the new role API such as `target.command` are available in both runs
