# The `itf` command line, for agents

Run it as `bazel run //score/itf/cli:itf -- <command>` (paths are relative to where it is run from) or `itf <command>`
after a pip install. The full table is `score/itf/cli/README.md`.

YAML `policies:` explicitly selects Python modules; native CLI, direct Session and pytest load the same
selection, without directory discovery or implicit `found.policy`. Policy paths are absolute or relative to
invocation working directory, not YAML parent; `bazel run` uses `BUILD_WORKING_DIRECTORY` for caller cwd.
`./policy.py` works when invoked where the file lives; `/home/alice/bench/policy.py` is an absolute example.
Run shipped examples from the `examples/` MODULE root, not their target directories. Legacy stays in compat.

## Which command answers which question

| Question | Command | Starts anything |
|---|---|---|
| Is this target file valid? | `itf validate <file>` (exit 1 with the fix) | no |
| What will run, in which order? | `itf plan <file>`; as data: `itf plan --json --output p.json <file>` | no |
| What did my change do to bring-up? | `itf plan --json` before and after, then `itf diff old.json new.json` | no |
| How is it wired? | `itf graph --kind topology\|sequence\|both <file>` (Mermaid) | no |
| Can this host run it? | `itf doctor <file>` | reads the host |
| Which contracts exist, who offers and needs them? | `itf contracts map [files]` | no |
| Does the project follow its contract rules? | `itf contracts check --rules rules.yaml [files]` | no |
| A definition for a contract in use | `itf contracts new <name> --from-usage` | no |
| What does a suite still use of the original API? | `itf compat report tests/ BUILD` | no |
| A target file from the original options | `itf compat target --docker-image=X --out targets/` | no |
| What happened in a run? | `itf evidence <run-dir> [--output f]`; across runs `--summary` | no |
| Try the target by hand | `itf up <file>` (console; leaving takes it down), `--detach` + `itf down` | yes |
| Run the tests on a target file | `itf test <file> -- <pytest args>` | yes |

## Rules for agents

- Prefer the commands that start nothing. Validate and plan before suggesting `itf up` or `itf test`.
- A missing `${NAME}` is not a bug in the target file: it comes from the environment or a `.env` beside the target
  file; under Bazel the `itf_target`'s `env` and `files` supply it.
- Bazel's run directories (`bazel-testlogs/.../test.outputs/itf-run`) are read-only: pass `--output` to
  `itf evidence`.
- `itf doctor` lists as `[manual]` only what no check covers; a `[ FAIL ]` names the fix.
