load("@rules_cc//cc:defs.bzl", "cc_binary", "cc_test")
load("@rules_pkg//pkg:tar.bzl", "pkg_tar")

cc_binary(
    name = "example-app",
    srcs = ["main.cpp"],
)

cc_test(
    name = "example-test",
    srcs = ["test.cpp"],
    deps = [
        "@googletest//:gtest",
        "@googletest//:gtest_main",
    ],
)

pkg_tar(
    name = "example-app-pkg",
    srcs = [
        "example-app",
    ],
    visibility = ["//examples/docker:__pkg__"],
)
