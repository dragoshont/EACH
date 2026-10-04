# M6 mixed-language historical-benchmark execution image: C/C++/Rust.
#
# Section 128's historical-repair task set is explicitly "a mix of
# C/C++/Rust/Python" (section 121 makes this authoritative). The
# existing M1 default image (python:3.12-slim) and the pytest-only
# docker/benchmark-runtime image have no compiled-language toolchain.
# This image adds exactly the compiler/build tools these three native
# language families need, from Debian's own apt repository, built and
# pinned here before any sealed (no-network) benchmark run --
# "provision dependencies before sealed run where possible" (mandate
# section 128). No target source is baked into this image; no other
# packages are added.
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libc6-dev \
        rustc \
        cargo \
    && rm -rf /var/lib/apt/lists/*
