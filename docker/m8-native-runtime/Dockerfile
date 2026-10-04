# M8 native-validation execution image.
#
# The M1 default executor image (python:3.12-slim) has no C compiler; the
# M8 xgameruntime#22 shadow demonstration's build_check.py harness compiles
# an isolated C function with a host C compiler. This image adds exactly
# gcc + libc headers, built and pinned here before any sealed (no-network)
# run -- "provision dependencies before sealed run where possible" (mandate
# section 128), matching the exact precedent of docker/benchmark-runtime.
# No other packages are added; no target source is baked into this image.
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*
