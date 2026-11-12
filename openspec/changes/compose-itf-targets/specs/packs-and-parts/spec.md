## ADDED Requirements

### Requirement: Packs contribute parts
A pack SHALL be a directory with a `pack.yaml` and its parts. ITF SHALL provide packs for core_dump, docker, dlt, localhost, net, pcap, ping, qemu, serial, sim and ssh. A pack not installed SHALL be locatable via the target file's `packs:` key.

#### Scenario: External pack
- **WHEN** a target file maps `acme: acme.plugin` under `packs:`
- **THEN** factories labelled `acme.<name>` resolve from that module

### Requirement: Capability factories build what tests use
A capability factory SHALL declare the contract it fulfils, take its dependencies as slots (a Protocol naming a contract) plus an optional settings dataclass, and be labelled `<pack>.<name>`. No other parameters SHALL be allowed.

#### Scenario: Extra parameter
- **WHEN** a factory has a parameter that is neither a slot nor its settings
- **THEN** loading the pack fails with a diagnostic naming the parameter

### Requirement: Actions make states true
An action SHALL declare the state it makes true, MAY declare `after`, `breaks` and `also` relations, and SHALL have a probe. A pack SHALL NOT state ordering that depends on other packs.

#### Scenario: Missing probe
- **WHEN** an action declares a state without a probe
- **THEN** validation reports the action as incomplete

### Requirement: Packs are import-light
Importing ITF contract metadata and the command line SHALL NOT require importing every pack implementation.

#### Scenario: Metadata without providers
- **WHEN** contract and catalog commands run with no built-in provider module installed
- **THEN** they succeed

### Requirement: Pack metadata references canonical contracts
Every built-in pack SHALL reference the shared contract library through per-contract files, resolved relative to the declaring file rather than the invocation directory.

#### Scenario: Resolution from another directory
- **WHEN** ITF runs from a directory unrelated to the installed package
- **THEN** every pack's contract references resolve
