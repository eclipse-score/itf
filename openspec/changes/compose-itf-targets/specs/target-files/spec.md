## ADDED Requirements

### Requirement: Target file describes a target as data
ITF SHALL accept a `*.itf.yaml` target file with the keys `include`, `packs`, `capabilities`, `actions`, `goals`, `relations`, `assume`, `scopes` and `policies`. An empty target file SHALL be valid. Unknown keys SHALL be rejected with an error naming the keys that exist.

#### Scenario: Valid target file
- **WHEN** a target file lists a platform factory, a command factory and the goal `platform.up`
- **THEN** `itf validate` accepts it with exit code 0

#### Scenario: Unknown key
- **WHEN** a target file contains a key that is not defined
- **THEN** validation fails and the diagnostic lists the valid keys

#### Scenario: Empty target file
- **WHEN** a target file is empty
- **THEN** validation succeeds and the plan contains no roles and no steps

### Requirement: Everything is explicit
Goals, factories, actions and policy modules SHALL enter a target only when the target file lists them. ITF MUST NOT infer goals and MUST NOT discover policy modules by file name or parent directory.

#### Scenario: Goal not listed
- **WHEN** an action could make a state true but the state is not listed under `goals`
- **THEN** the action does not run

### Requirement: Includes and override files merge by role
ITF SHALL merge `include` files first, in order, and the including file SHALL win. An override file SHALL merge by role over another target file, and a role with `remove: true` SHALL be removed.

#### Scenario: Role override
- **WHEN** an override file sets `with:` settings on role `platform`
- **THEN** the merged target uses the override's settings for that role and keeps all other roles

#### Scenario: Role removal
- **WHEN** an override file marks a role `remove: true`
- **THEN** the merged target has no such role

### Requirement: Scopes model multiple devices
A target file SHALL support `scopes`, each with its own capabilities, actions, goals, relations and shared roles. Roles of a scope SHALL be addressed as `target.<scope>.<role>`.

#### Scenario: Two devices
- **WHEN** a target file declares scopes `gw` and `ecu`, each with a `command` role
- **THEN** tests reach them as `target.gw.command` and `target.ecu.command`

### Requirement: Policies are explicit
A target's `policies:` list SHALL select the project-owned Python modules providing actions, expectations and hooks. Policy paths SHALL be absolute or relative to the invocation working directory. Includes SHALL compose policy lists and `[]` SHALL clear inherited selections. Project parts SHALL carry the label prefix `local.`.

#### Scenario: Cleared policies
- **WHEN** an including file sets `policies: []`
- **THEN** no inherited policy module is loaded

### Requirement: Secrets stay out of files
A target file SHALL be able to reference `${NAME}` values from the environment or a `.env` file. ITF SHALL mask resolved secret values in logs and reports.

#### Scenario: Secret masked
- **WHEN** a credential is supplied as `${PASSWORD}` and a run logs its value
- **THEN** the log and the report show the masked value, never the secret
