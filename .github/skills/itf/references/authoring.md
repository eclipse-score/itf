# Authoring a target file and tests from requirements

Worked example: `test/integration` runs one role-gated suite (`suite/`) against many target files (`targets/`: host,
container, container plus SSH, DLT with a project action, QEMU with the console opened before boot), and its README
shows which tests each target file selects. `examples/examples/exec_everywhere` is the small version.

## 1. Decompose a requirement

| Requirement says | Look for | Lands in |
|---|---|---|
| a device or core ("the gateway") | | a **scope** (`gw`) |
| "runs in a container / on a VM / on the board" | `platform.instance` factories | role `platform` (`docker.platform`, `qemu.platform`, `localhost.platform`) |
| "run a command" | `exec.command` | role `command` (`docker.exec`, `ssh.exec`, `serial.exec`, `localhost.exec`) |
| "copy a file" | `files.transfer` | role `files` |
| "start the app and watch it" | `exec.process` | role `process`, `WrappedProcess` |
| "log in over SSH" | `exec.shell` with `descriptor.endpoint` and `descriptor.credentials` | roles `shell`, `endpoint`, `credentials` |
| "read the boot log" | `exec.console` | role `console` |
| "receive DLT" | `observe.logs` | role `logs`; a `by:` for `logs.active` (several actions make it true) |
| "the machine is up / the session is open" | state contracts | `goals:` (`platform.up`, `shell.open`) |
| "the rack keeps it powered" | something outside ITF | `assume:` with owner and reason |
| "this setup has another image / login" | what differs in one setup | an override file |
| "open the session only after the platform runs" | an order between states | `relations:` |
| "wait for the daemon, then subscribe" | project code | a `@state` in the policy |

Each pack README has its label table; read it instead of the pack's source.

## 2. Write, validate, read

1. Write the target file (`references/yaml.md`). Start from the nearest starter.
2. `itf validate` (or build the `itf_target`). Fix what it names: a slot with no candidate or two (`bind:`
   for a factory's slot, `actions:` for an action's), a state two actions could make true (`by:`), a setting that
   does not fit its schema, a label whose pack is not in `packs`.
3. `itf graph`: is the bring-up order what you meant?
4. Tests: `@itf.requires("<role>", shape=YourProtocol)`; `target.<role>`. A test must run on every
   target file that has the role.
5. Explicit YAML `policies:` modules: `itf_verify` for readiness (a named `session.check`), `itf_teardown` for evidence. Project parts:
   `@capability`/`@state` with your own Protocols (`__contract__`), a probe per action taking the same slots.
6. `itf test` or `bazel test`. Read deselections: the reason names what the target has.

## 3. A project part

For strict test requirements, declare the API the test consumes rather than a list of member names:

```python
from typing import Protocol
import score.itf as itf

class WaitingConsole(Protocol):
    __contract__ = "exec.console"

    def wait_for(
        self, pattern: str, timeout: float = 30, *, since: int = 0, regex: bool = False
    ) -> str | None: ...

@itf.requires("console", shape=WaitingConsole)
def test_boot_message(target):
    assert target.console.wait_for("ready", timeout=10, since=0, regex=False)
```

The contract is inferred from the Protocol. Before construction, gating checks that each required
method is callable and accepts the Protocol's positional and keyword arguments, including optional
arguments. Additional optional provider parameters are allowed; additional required parameters are not.
This checks call structure, not annotation assignability, return values, or implementation semantics.
Those still need static typing and behavioral tests. Older member-name lists remain supported but do
not provide this guarantee. Plans without callable metadata cannot satisfy a strict Protocol requirement.

Infrastructure-wide API baselines belong in the policy as `itf_expect = [YourProtocol]`. Every
capability offering the Protocol's `__contract__`, in every scope, is checked during resolution,
including roles no test consumes. This is conditional on the contract being present: it does not
create or require missing roles. Multiple declarations compose; each must hold independently.
An unversioned name applies to all majors, while `name@1` applies only to explicitly offered major 1
and refuses matching providers without major metadata. A policy violation always rejects resolution;
strict/loose test-gating policy does not weaken infrastructure invariants. A module declaring only
`itf_expect` is a contributor; select shared modules explicitly through YAML `policies:`, not native
directory discovery or `pytest_plugins`. Policy paths follow invocation working directory, not the YAML
parent; see `references/yaml.md` for merging and reset semantics. Bazel `srcs` bundles the selected modules.

Collection preflight groups exact consumer profiles by scope, role, contract and required major without
merging different signatures. Default gating deselects incompatible or unknown tests and logs the grouped
result. `--itf-strict-gating` rejects the whole collection before bring-up when an applicable API is
incompatible or unverifiable. Missing roles/scopes and explicit contract/major differences remain not
applicable. An undeclared provider major does not satisfy a versioned requirement. `--itf-plan` prints the
report, and full artifacts include `preflight.json` alongside the existing per-test `gating.json`.

```python
class Endpoint(Protocol):
    __contract__ = "descriptor.endpoint"
    host: str
    port: int

class Console(Protocol):
    __contract__ = "exec.console"
    def open(self) -> None: ...
    def is_open(self) -> bool: ...

@state("console.open", after=("platform.up",), label="open_when_ecu_answers")
def open_when_ecu_answers(endpoint: Endpoint, console: Console) -> None:
    wait_for(endpoint)
    console.open()

@open_when_ecu_answers.probe
def console_is_open(endpoint: Endpoint, console: Console) -> bool:
    return console.is_open()
```

It is `local.open_when_ecu_answers`; target files that need `console.open` and also list `serial` choose with
`by:`. A project's own action may state `after=`: it knows the target files of its own project; a pack does not. A slot parameter is the only kind of parameter besides `config: <dataclass>`.

## 4. Gaps

If no factory gives what the requirement needs: say so, name the contract the new part would fulfil (any name
two parts agree on), write the factory in the project (`local.<name>`) or a pack (`docs/how-to/plugins.md`), and
run `itf contracts map` to see who offers and who expects it.
