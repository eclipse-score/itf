## ADDED Requirements

### Requirement: Every run leaves evidence
Each run SHALL write its plan, what the probes observed and a report to a run directory. `itf evidence` SHALL write `evidence.html` for a run or summarize several runs.

#### Scenario: Evidence after a run
- **WHEN** a run finishes
- **THEN** the run directory holds the plan, probe observations and a report

### Requirement: Failures are attributable
A failed run SHALL identify the gate, step or probe that failed.

#### Scenario: Failed probe
- **WHEN** a probe reports a state does not hold after its action
- **THEN** the report names that state and action

### Requirement: Artifact detail is selectable
ITF SHALL support an artifact level option (including `full`) that adds a structured event stream to the retained evidence.

#### Scenario: Full artifacts
- **WHEN** a run uses `--itf-artifacts=full`
- **THEN** the structured event stream is retained
