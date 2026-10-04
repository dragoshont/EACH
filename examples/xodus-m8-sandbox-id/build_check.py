"""Bounded validation harness for xgameruntime#22 and #26.

Independent scaffold, never Builder input. Select sandbox, console, or both
from the approved command. Each public-source C function is compiled with ABI
stubs; a protected Python parent checks six returned-value cases per function.

Two subcommands, invoked as two separate spec commands so a genuine build
failure and a genuine acceptance failure remain distinguishable, exactly
like every other EACH spec's build_commands/acceptance_commands split:

  build -- extract the selected functions and compile them inside the container.
  run   -- launch one fresh child per case and check actual return/output data.
           Exit zero without case data is a failure, not a completed test.

This proves only what mandate section 63 says an unproven native-isolation
Xodus validation can honestly prove: structural patch correctness and
two-function behavior in a tiny standalone harness -- NOT a full native
winelib/Wine build, NOT execution of the real DLL, NOT a real Xbox/GDK
service round-trip. The receipt built on top of this must say so plainly.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

_FUNCTION_NAMES = (
    "x_system_XSystemGetConsoleId",
    "x_system_XSystemGetXboxLiveSandboxId",
)
_HERE = Path(__file__).resolve().parent
_BUILD_DIR = _HERE / ".build"
_APIS = {
    "sandbox": (_FUNCTION_NAMES[1], "RETAIL"),
    "console": (_FUNCTION_NAMES[0], "00000000.00000000.00000000.00000000.00"),
}

_VALUE_DRIVER = r"""
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv)
{
    char buffer[64];
    SIZE_T used = 1234567;
    HRESULT hr;
    int test;
    size_t i;
    if (argc != 2) return 2;
    memset(buffer, 0xa5, sizeof(buffer));
    test = atoi(argv[1]);
    if (test == 0) hr = FUNCTION(NULL, 64, buffer, NULL);
    else if (test == 1) hr = FUNCTION(NULL, 64, buffer, &used);
    else if (test == 2) hr = FUNCTION(NULL, 64, NULL, &used);
    else if (test == 3) hr = FUNCTION(NULL, 64, NULL, NULL);
    else if (test == 4) hr = FUNCTION(NULL, 1, buffer, &used);
    else if (test == 5) hr = FUNCTION(NULL, 1, buffer, NULL);
    else return 2;
    printf("EACH_VALUE:%u:%zu:", (unsigned int)hr, used);
    for (i = 0; i < sizeof(buffer); i++) printf("%02x", (unsigned char)buffer[i]);
    printf("\n");
    return 0;
}
"""
_CASE_NAMES = (
    "optional_size_output_null",
    "value_and_size_output",
    "required_buffer_null",
    "both_outputs_null",
    "short_buffer_with_size_output",
    "short_buffer_without_size_output",
)


def _selected_apis(selector: str) -> tuple[str, ...]:
    if selector == "both":
        return tuple(_APIS)
    if selector not in _APIS:
        raise SystemExit("API selector must be sandbox, console, or both")
    return (selector,)


def _code_mask(text: str) -> str:
    """Mask C comments/literals without changing source offsets."""
    masked = list(text)
    state = "code"
    index = 0
    while index < len(text):
        char = text[index]
        nxt = text[index + 1:index + 2]
        if state == "code":
            if char == "/" and nxt in {"/", "*"}:
                state = "line-comment" if nxt == "/" else "block-comment"
                masked[index:index + 2] = [" ", " "]
                index += 2
                continue
            if char in {'"', "'"}:
                state = "string" if char == '"' else "character"
                masked[index] = " "
        else:
            if char not in {"\r", "\n"}:
                masked[index] = " "
            if state == "block-comment" and char == "*" and nxt == "/":
                masked[index:index + 2] = [" ", " "]
                state = "code"
                index += 2
                continue
            if state == "line-comment":
                if char == "\\" and nxt in {"\r", "\n"}:
                    index += 3 if text[index + 1:index + 3] == "\r\n" else 2
                    continue
                if char in {"\r", "\n"}:
                    state = "code"
            elif state in {"string", "character"}:
                if char == "\\":
                    if index + 1 < len(text):
                        masked[index + 1] = " "
                    index += 2
                    continue
                if (state == "string" and char == '"') or (state == "character" and char == "'"):
                    state = "code"
        index += 1
    return "".join(masked)


def _extract_function(text: str, function_name: str) -> str:
    # Mechanical signature match only -- never the known fix/diff location.
    signature_re = re.compile(
        r"static\s+HRESULT\s+WINAPI\s+" + re.escape(function_name) + r"\s*\([^)]*\)\s*\{",
        re.MULTILINE,
    )
    code = _code_mask(text)
    matches = list(signature_re.finditer(code))
    if len(matches) != 1:
        raise SystemExit(f"build_check: expected exactly one function definition for {function_name!r}")
    match = matches[0]
    start = match.start()
    depth = 0
    index = match.end() - 1  # position of the opening brace
    for index in range(match.end() - 1, len(code)):
        if code[index] == "{":
            depth += 1
        elif code[index] == "}":
            depth -= 1
            if depth == 0:
                break
    else:
        raise SystemExit("build_check: unterminated function body (unbalanced braces)")
    return text[start : index + 1]


def cmd_build(source_arg: str, selector: str = "both") -> int:
    source_path = Path(source_arg).resolve()
    if not source_path.is_file():
        raise SystemExit(f"build_check: source file not found: {source_path}")
    source_text = source_path.read_text(encoding="utf-8")
    _BUILD_DIR.mkdir(parents=True, exist_ok=True)
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        raise SystemExit("build_check: no C compiler (cc/gcc/clang) found on PATH")
    for api in _selected_apis(selector):
        function_name, _expected = _APIS[api]
        function_text = _extract_function(source_text, function_name)
        harness_c = _BUILD_DIR / f"{api}.c"
        binary = _BUILD_DIR / f"check_{api}"
        harness_c.write_text(
            f'#include "{_HERE / "winstubs.h"}"\n\n{function_text}\n\n'
            + _VALUE_DRIVER.replace("FUNCTION", function_name),
            encoding="utf-8",
        )
        result = subprocess.run(
            [cc, "-std=c11", "-Wall", "-Wextra", "-o", str(binary), str(harness_c)],
            capture_output=True, text=True, check=False,
        )
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode:
            return result.returncode
    return 0


def cmd_run(selector: str = "both") -> int:
    results = []
    for api in _selected_apis(selector):
        binary = _BUILD_DIR / f"check_{api}"
        if not binary.is_file():
            raise SystemExit("build_check: compiled binary not found; run the build step first")
        _function, expected = _APIS[api]
        for case, name in enumerate(_CASE_NAMES):
            try:
                result = subprocess.run(
                    [str(binary), str(case)], capture_output=True, text=True, check=False, timeout=5,
                )
            except subprocess.TimeoutExpired:
                results.append({"api": api, "case": name, "status": "FAIL", "reason": "case_timeout"})
                continue
            passed = False
            reason = "case_data_missing_or_invalid"
            if result.returncode == 0:
                value = re.fullmatch(r"EACH_VALUE:([0-9]+):([0-9]+):([0-9a-f]{128})\n", result.stdout)
                if value:
                    hr = int(value[1])
                    used = int(value[2])
                    buffer = bytes.fromhex(value[3])
                    data = buffer.split(b"\0", 1)[0]
                    expected_hr = 0 if case < 2 else (0x80004003 if case < 4 else 0x8007007A)
                    passed = hr == expected_hr
                    if case < 2:
                        expected_bytes = expected.encode()
                        passed = passed and data == expected_bytes and buffer[len(expected_bytes)] == 0
                    if case == 1:
                        passed = passed and used == len(expected.encode()) + 1
                    reason = "behavior_matches" if passed else "behavior_mismatch"
            else:
                reason = "case_process_failed"
            results.append({"api": api, "case": name, "status": "PASS" if passed else "FAIL", "reason": reason})
    print("EACH_CASE_RESULTS:" + json.dumps(results, separators=(",", ":")))
    return 0 if all(item["status"] == "PASS" for item in results) else 1


def main(argv: list[str]) -> int:
    if not argv:
        raise SystemExit("usage: build_check.py <build SOURCE_PATH | run>")
    if argv[0] == "build":
        if len(argv) not in {2, 3}:
            raise SystemExit("usage: build_check.py build SOURCE_PATH [sandbox|console|both]")
        return cmd_build(argv[1], argv[2] if len(argv) == 3 else "both")
    if argv[0] == "run":
        if len(argv) > 2:
            raise SystemExit("usage: build_check.py run [sandbox|console|both]")
        return cmd_run(argv[1] if len(argv) == 2 else "both")
    raise SystemExit(f"unknown subcommand: {argv[0]!r}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
