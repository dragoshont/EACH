#!/usr/bin/env python3
"""M8 bounded validation harness for xgameruntime#22 (XSystemGetXboxLiveSandboxId).

Human/coordinator-authored scaffold (never Builder input, never part of the
generated candidate). It mechanically extracts exactly the one function the
spec's ``allowed_paths`` scopes Builder's edit to, from the (candidate-
patched) ``xsystem.c``, by signature text matching only -- never using the
human-known fix location/diff to find it, consistent with the mandate's
"source excerpts chosen by public contract/function name, not changed-line
position" rule carried over from the M6 benchmark harness.

Two subcommands, invoked as two separate spec commands so a genuine build
failure and a genuine acceptance failure remain distinguishable, exactly
like every other EACH spec's build_commands/acceptance_commands split:

  build  -- extract the function, wrap it with winstubs.h and a tiny test
            driver, and compile it with the host C compiler. A compile
            failure here means the candidate patch is not even valid C.
  run    -- execute the compiled binary. A nonzero exit means the patched
            function did not satisfy the three asserted behavioral cases.

This proves only what mandate section 63 says an unproven native-isolation
Xodus validation can honestly prove: structural patch correctness and
function-level behavior in a tiny standalone harness -- NOT a full native
winelib/Wine build, NOT execution of the real DLL, NOT a real Xbox/GDK
service round-trip. The receipt built on top of this must say so plainly.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

_FUNCTION_NAME = "x_system_XSystemGetXboxLiveSandboxId"
_HERE = Path(__file__).resolve().parent
_BUILD_DIR = _HERE / ".build"
_BINARY = _BUILD_DIR / "check_sandbox_id"

_DRIVER_MAIN = r"""
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Pulled in verbatim below: the extracted, patched function body. */

int main(void)
{
    char buf[64];
    SIZE_T used;
    HRESULT hr;

    /* Case 1 (the bug being fixed): sandboxIdUsed is NULL, sandboxId is a
     * valid, sufficiently-sized buffer -> per the public GDK docs
     * (sandboxIdUsed is _Out_opt_), this must succeed, not E_POINTER. */
    memset(buf, 0, sizeof(buf));
    hr = x_system_XSystemGetXboxLiveSandboxId(NULL, (INT32)sizeof(buf), buf, NULL);
    if (hr != S_OK) { fprintf(stderr, "FAIL case1: expected S_OK, got 0x%08lx\n", (unsigned long)hr); return 1; }
    if (strcmp(buf, "RETAIL") != 0) { fprintf(stderr, "FAIL case1: sandboxId not written correctly\n"); return 1; }

    /* Case 2 (regression safeguard): sandboxId itself is NULL -> it is
     * documented _Out_writes_bytes_to_(...), i.e. NOT optional, so this
     * must still be E_POINTER, with or without sandboxIdUsed set. */
    used = 0;
    hr = x_system_XSystemGetXboxLiveSandboxId(NULL, (INT32)sizeof(buf), NULL, &used);
    if (hr != E_POINTER) { fprintf(stderr, "FAIL case2: expected E_POINTER, got 0x%08lx\n", (unsigned long)hr); return 1; }

    /* Case 3 (regression safeguard): buffer too small -> unchanged existing
     * behavior (HRESULT_FROM_WIN32(ERROR_INSUFFICIENT_BUFFER)), not
     * accidentally bypassed by the NULL-tolerance fix. */
    used = 0;
    hr = x_system_XSystemGetXboxLiveSandboxId(NULL, 1, buf, &used);
    if (hr != HRESULT_FROM_WIN32(ERROR_INSUFFICIENT_BUFFER)) {
        fprintf(stderr, "FAIL case3: expected ERROR_INSUFFICIENT_BUFFER, got 0x%08lx\n", (unsigned long)hr);
        return 1;
    }

    fprintf(stderr, "PASS: all 3 cases\n");
    return 0;
}
"""


def _extract_function(source_path: Path) -> str:
    text = source_path.read_text(encoding="utf-8")
    # Mechanical signature match only -- never the known fix/diff location.
    signature_re = re.compile(
        r"static\s+HRESULT\s+WINAPI\s+" + re.escape(_FUNCTION_NAME) + r"\s*\([^)]*\)\s*\{",
        re.MULTILINE,
    )
    match = signature_re.search(text)
    if not match:
        raise SystemExit(f"build_check: could not locate function signature for {_FUNCTION_NAME!r}")
    start = match.start()
    depth = 0
    index = match.end() - 1  # position of the opening brace
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                break
    else:
        raise SystemExit("build_check: unterminated function body (unbalanced braces)")
    return text[start : index + 1]


def cmd_build(source_arg: str) -> int:
    source_path = Path(source_arg).resolve()
    if not source_path.is_file():
        raise SystemExit(f"build_check: source file not found: {source_path}")
    function_text = _extract_function(source_path)

    _BUILD_DIR.mkdir(parents=True, exist_ok=True)
    harness_c = _BUILD_DIR / "harness.c"
    harness_c.write_text(
        f'#include "{_HERE / "winstubs.h"}"\n\n{function_text}\n\n{_DRIVER_MAIN}\n',
        encoding="utf-8",
    )

    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        raise SystemExit("build_check: no C compiler (cc/gcc/clang) found on PATH")
    result = subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-o", str(_BINARY), str(harness_c)],
        capture_output=True,
        text=True,
    )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def cmd_run() -> int:
    if not _BINARY.is_file():
        raise SystemExit("build_check: compiled binary not found; run the build step first")
    result = subprocess.run([str(_BINARY)], capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


def main(argv: list[str]) -> int:
    if not argv:
        raise SystemExit("usage: build_check.py <build SOURCE_PATH | run>")
    if argv[0] == "build":
        if len(argv) != 2:
            raise SystemExit("usage: build_check.py build SOURCE_PATH")
        return cmd_build(argv[1])
    if argv[0] == "run":
        return cmd_run()
    raise SystemExit(f"unknown subcommand: {argv[0]!r}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
