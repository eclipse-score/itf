# ITF - Integration Testing Framework

This module implements support for running [pytest](https://docs.pytest.org/en/latest/contents.html) based tests.

## Usage
MODULE.bazel
```
bazel_dep(name = "itf", version = "0.1")
```

BUILD
```
load("@itf//:defs.bzl", "py_itf_test")

py_itf_test(
    name = "test_my_first_check",
    srcs = [
        "test_my_first_check.py"
    ],
    plugins = [
        # Specify optional plugins, ex:
        "itf.plugins.docker",
    ]
    args = [
        # Specify optional arguments, ex:
        "--docker-image=alpine:latest",
    ]
)
```

## Development

### Regenerating pip dependencies
```
$ bazel run //:requirements.update
```

### Running test
```
$ bazel test //test/...
```

Specify additionally:
- ```--test_arg="-s"``` to get stdout/err from pytest
- ```--test_output=all``` to get stdout/err from bazel
- ```--nocache_test_results``` not to cache test runs
