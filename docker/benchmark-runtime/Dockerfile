# M6 historical-benchmark execution image.
#
# The M1 default executor image (python:3.12-slim, pinned by digest in
# each/executor/container.py) has no test runner beyond the stdlib
# unittest module. Most real-world historical repair tasks use pytest, so
# this image adds exactly that one dependency, built and pinned here
# before any sealed (no-network) benchmark run -- "provision dependencies
# before sealed run where possible" (mandate section 128). No other
# packages are added; task-specific runtime dependencies (if any) remain
# an honest per-task limitation, not silently bundled in.
FROM python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
RUN pip install --no-cache-dir pytest==8.3.4
