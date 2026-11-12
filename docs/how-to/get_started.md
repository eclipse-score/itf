# Get Started

This guide walks you through setting up ITF in a new Bazel workspace from scratch.

## Prerequisites

- [Bazel](https://bazel.build/install) 7.x or later
- Docker (for Docker-based tests)
- Python 3.12+

## 1. Add ITF to your workspace

In your `MODULE.bazel`, declare the dependency using the latest published
registry version:

```starlark
bazel_dep(name = "score_itf", version = "0.2.0")
```

To get unreleased fixes from the main branch, add a `git_override` directly
after the `bazel_dep`:

```starlark
git_override(
    module_name = "score_itf",
    remote = "https://github.com/eclipse-score/itf.git",
    commit = "<COMMIT_HASH>",
)
```

Replace `<COMMIT_HASH>` with the full SHA of the desired commit from the
[score_itf repository](https://github.com/eclipse-score/itf).

## 2. Configure `.bazelrc`

Add the S-CORE Bazel registry so Bazel can resolve the `score_itf` module:

```
common --registry=https://raw.githubusercontent.com/eclipse-score/bazel_registry/main/
common --registry=https://bcr.bazel.build
```

If you also want to build the ITF documentation locally (optional), add the
Java configuration required by PlantUML:

```
build --java_language_version=17
build --java_runtime_version=remotejdk_17
build --tool_java_language_version=17
build --tool_java_runtime_version=remotejdk_17
```

## 3. Write your first test

Create a test file `test_hello.py`:

```python
def test_hello(target):
    exit_code, output = target.execute("echo 'Hello from target!'")
    assert exit_code == 0
    assert b"Hello from target!" in output
```

Create a `BUILD` file in the same directory:

```starlark
load("@score_itf//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_hello",
    srcs = ["test_hello.py"],
    args = ["--docker-image=ubuntu:24.04"],
    plugins = ["@score_itf//score/itf/plugins:docker_plugin"],
)
```

> **Note:** All `load()` calls and plugin labels must use the `@score_itf`
> prefix. Using `//:defs.bzl` without the prefix would look for that file
> in your own workspace and fail with `no such file`.

## 4. Run the test

```bash
bazel test //path/to:test_hello
```

To see full test output:

```bash
bazel test //path/to:test_hello --test_output=all
```

## 5. Link tests to requirements

ITF integrates with the S-CORE docs-as-code traceability system. The
`@add_test_properties` decorator writes requirement links and test
classification metadata into the JUnit XML report, which Sphinx can then
pick up to create bidirectional traceability between test results and
requirements.

```python
from attribute_plugin import add_test_properties

@add_test_properties(
    fully_verifies=["REQ-001", "REQ-002"],
    test_type="requirements-based",
    derivation_technique="requirements-analysis",
)
def test_hello(target):
    exit_code, output = target.execute("echo 'Hello from target!'")
    assert exit_code == 0
    assert b"Hello from target!" in output
```

Add `attribute_plugin` to the `plugins` list in your `BUILD` file:

```starlark
py_itf_test(
    name = "test_hello",
    srcs = ["test_hello.py"],
    args = ["--docker-image=ubuntu:24.04"],
    plugins = [
        "@score_itf//score/itf/plugins:docker_plugin",
        "@score_itf//score/itf/plugins:attribute_plugin",
    ],
)
```

## Next steps

- **Write more tests**: See [Write Tests](write_tests.md) for Docker, QEMU,
  and DLT examples.
- **Use plugins**: See [Using Plugins](plugins.md) for configuring and
  combining built-in plugins.
- **Understand the design**: See the [Concepts](../concepts/index.rst)
  section for the architecture and plugin system.

## For ITF contributors

Build this documentation site locally:

```bash
bazel run //:docs
```

Open `_build/index.html` in your browser.
