load("@rules_oci//oci:defs.bzl", "oci_image", "oci_tarball")

oci_image(
    name = "image",
    base = "@ubuntu_24_04",
    tars = [
        "//examples/cpp:example-app-pkg",
    ],
)

oci_tarball(
    name = "image_tarball",
    image = ":image",
    repo_tags = ["score_itf_examples:latest"],
    visibility = ["//examples/itf:__pkg__"],
)
