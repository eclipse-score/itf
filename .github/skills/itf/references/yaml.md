# The target file format

A target file is a YAML (or JSON) document, usually `*.itf.yaml`. Supported keys: `include`,
`policies`, `packs`, `capabilities`, `actions`, `goals`, `relations`, `assume`, `scopes`. Unknown keys are errors naming what
exists. Prefer block style; `policies: []` explicitly clears inherited policies. Words: `docs/concepts/model.md#the-vocabulary`.

This is a whole target file (it passes `itf validate`):

```yaml
capabilities:                     # keyed by role: the name tests use (`target.command`)
  platform:
    factory: docker.platform      # <pack>.<name>
    with:                         # settings, checked against the factory's config dataclass
      image: linuxserver/openssh-server:version-10.2_p1-r0
      command: null
      init: false
      environment: PASSWORD_ACCESS=true,USER_NAME=score,USER_PASSWORD=score
      ports: 2222/tcp
  endpoint:
    factory: docker.endpoint
    with:
      port: 2222
  credentials:
    factory: net.password
    with:
      user: score
      password: score
  shell: ssh.shell                # short form: just the factory
  command: ssh.exec
goals:                            # states to reach; nothing is inferred
  - platform.up
  - shell.open
relations:                        # an order between states that no part states about the other's pack
  - state: shell.open
    after:
      - platform.up
```

The other keys, as fragments (not whole target files):

```yaml
include:                          # merged first, in order; this file wins
  - base.itf.yaml
packs:                            # where a pack that is not installed lives: pack name -> entry point module
  acme: acme.plugin
policies:                         # explicit Python modules; paths relative to invocation working directory
  - policies/common.py
  - policies/ubuntu.py
capabilities:
  shell:
    factory: ssh.shell
    bind:                         # a factory's slot with more than one candidate: slot -> role
      endpoint: lab_endpoint
  platform:
    remove: true                  # takes the role out (stands alone; for overrides and includers)
actions:                          # an action's slot with more than one candidate: slot -> role
  serial.open:                    # an action's label
    bind:
      console: console
goals:
  - state: console.open
    by: serial.open               # only when two actions (of listed packs or the project) could make it true
relations:
  - state: shell.open             # added to the claim of the action that makes it true
    after:
      - platform.up
    breaks:
      - network.reachable
assume:                           # a state that holds without ITF
  - state: rack.ready
    owner: lab
    reason: the rack keeps it on
scopes:                           # one more device
  gw:
    capabilities:
      command: ssh.exec
    goals:
      - shell.open
    actions:                      # same entries as at the root; the roles are this scope's
      acme.open:
        bind:
          endpoint: command
    relations:                    # same entries as at the root
      - state: shell.open
        after:
          - platform.up
    share:
      - platform                  # gw uses the root's platform role
```

- Role = `target.<role>`; factory = `<pack>.<function>` (a part in the project's policy (`policy.py`): `local.<function>`).
  A role entry has `factory`, `with`, `bind` or `remove`.
- `policies:` explicitly selects Python modules, with any filenames and no proximity restriction. Paths
  are absolute or relative to the invocation working directory, never the YAML parent. `./policy.py` works
  when invoked where that file lives; `/home/alice/bench/policy.py` is an absolute example. Under `bazel run`,
  `BUILD_WORKING_DIRECTORY` supplies the caller's working directory. There is no native directory discovery
  or implicit `found.policy`; direct `Session`, CLI and pytest load the same selection. Legacy handling stays
  in compat. Policy contributions do not trigger actions unless goals require their states.
- `with:` values may read the environment, else a `.env` beside the target file: `${NAME}` or `${NAME:-default}`.
  Never write a login or a password into a target file: use `${NAME}` and a `.env.example`; a value that is exactly one reference is
  read as a YAML scalar (`port: ${SSH_PORT:-22}` is an integer); `$${` is a literal `${`.
- Wiring, in order. A factory's slot: `bind:`, else the one role of the slot's contract, else an error. An action's
  slot: `actions:` with `bind:`, else the one role of the slot's contract in the scope, else the action cannot run
  there (it is a candidate for a state only if all its slots can be filled). A goal two candidates could make true:
  `by:`, else an error naming both. The actions considered are those of the packs of the listed factories plus
  the project's own.
- `relations:` (`state`, `after`, `breaks`) states orderings between packs: a pack names no state of another
  pack in its own `after=`. A relation on a state no listed action makes or assumes is an error.
- Scopes: roles of a scope are `target.<scope>.<role>`; a scope never falls back to the root, `share:` lists the
  root roles it uses. A role named like a scope or a handle member is rejected.

## Override files

An override file has the target file's own shape and only what changes. Files merge by role, in order (includes
first, then the target file, then each override): `with:` and `bind:` keys are merged, any other key replaces;
goals and assumptions merge by state, relations of one state are joined, `actions:` binds merge by action and
slot. `remove: true` takes a role out; a different `factory:` starts the role from nothing.

Policies are an exception to replacement: nonempty lists add in deterministic merge order and deduplicate
paths. An omitted key adds no own policies and retains included/inherited policies; explicit `policies: []`
clears the inherited list. Duplicate part labels across distinct modules remain errors. Bazel `itf_target`
`srcs` must bundle the Python files named by the merged YAML, but never selects them; there is no planner
`--policy` selection.

This override points the target file above at a real machine:

```yaml
capabilities:
  platform:
    remove: true
  endpoint:
    factory: net.endpoint
    with:
      host: 10.0.0.7
      port: 22
assume:
  - state: platform.up
    owner: lab
    reason: the machine is powered and booted by the lab
```

## Where a run finds them

The target file: `--itf-target` (pytest) or the `itf` argument, `ITF_TARGET`, `itf_target` (ini),
`[tool.itf] target`. Overrides: `--itf-override` / `--override` (repeatable), `ITF_OVERRIDE`, `itf_override`
(ini), `[tool.itf] override` (several files separated by `os.pathsep`). Bazel: `py_itf_test(target = ":x")`
sets them from the `itf_target`. `Session(target=..., overrides=[...])` without pytest.
`itf validate|plan|graph|up|down|doctor` and `itf test` take the target file as an argument or from the same
configuration.
