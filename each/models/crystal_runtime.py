"""Private stdin/stdout runtime helper for the exact CrystalCoder checkpoint."""

from __future__ import annotations

import argparse
import errno
import json
import platform
import shutil
import socket
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, required=True)
    parser.add_argument("--max-position-embeddings", type=int, required=True)
    parser.add_argument("--device", choices=["mps", "cpu"], required=True)
    parser.add_argument("--temperature", type=float, required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--probe-denied-path", type=Path, action="append", required=True)
    parser.add_argument("--probe-write-path", type=Path, required=True)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--stage-path", type=Path, required=True)
    args = parser.parse_args()
    prompt = sys.stdin.read()
    args.stage_path.write_text(json.dumps({"generationAttempted": False}))

    isolation = {"networkDenied": False, "privateFilesDenied": 0, "outsideWriteDenied": False}
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=0.2)
    except OSError as exc:
        isolation["networkDenied"] = exc.errno in {errno.EPERM, errno.EACCES}
    for denied_path in args.probe_denied_path:
        try:
            denied_path.read_bytes()
        except OSError as exc:
            if exc.errno in {errno.EPERM, errno.EACCES}:
                isolation["privateFilesDenied"] += 1
    try:
        args.probe_write_path.write_text("sandbox write probe")
    except OSError as exc:
        isolation["outsideWriteDenied"] = exc.errno in {errno.EPERM, errno.EACCES}
    if (
        isolation["networkDenied"] is not True
        or isolation["privateFilesDenied"] != len(args.probe_denied_path)
        or isolation["outsideWriteDenied"] is not True
    ):
        print(json.dumps({
            "schemaVersion": "1",
            "status": "ISOLATION_UNVERIFIED",
            "generationAttempted": False,
            "isolation": isolation,
            "detail": "network or private-file denial probe did not fail closed",
        }))
        return 3

    code_dir = args.stage_path.parent / "crystal_publisher_code"
    code_dir.mkdir()
    (code_dir / "__init__.py").write_text("")
    for name in (
        "configuration_crystalcoder.py",
        "modeling_crystalcoder.py",
        "tokenization_crystalcoder_fast.py",
    ):
        shutil.copyfile(args.snapshot / name, code_dir / name)
    sys.path.insert(0, str(args.site_packages))
    sys.path.insert(0, str(code_dir.parent))

    import torch
    import transformers
    from crystal_publisher_code.configuration_crystalcoder import CrystalCoderConfig
    from crystal_publisher_code.modeling_crystalcoder import CrystalCoderLMHeadModel
    from crystal_publisher_code.tokenization_crystalcoder_fast import CrystalCoderTokenizerFast

    runtime = {
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
    }

    if args.device == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS is unavailable")
    tokenizer = CrystalCoderTokenizerFast.from_pretrained(
        args.snapshot,
        local_files_only=True,
    )
    input_token_count = len(tokenizer.encode(prompt))
    if (
        args.max_position_embeddings > 0
        and input_token_count + args.max_tokens > args.max_position_embeddings
    ):
        print(json.dumps({
            "schemaVersion": "1",
            "status": "CONTEXT_BUDGET_EXCEEDED",
            "generationAttempted": False,
            "isolation": isolation,
            "runtime": runtime,
            "inputTokenCount": input_token_count,
            "detail": (
                f"rendered prompt ({input_token_count} tokens) + reserved output "
                f"({args.max_tokens} tokens) = {input_token_count + args.max_tokens} tokens "
                "exceeds this checkpoint's declared max_position_embeddings "
                f"({args.max_position_embeddings})"
            ),
        }))
        return 2

    config = CrystalCoderConfig.from_pretrained(args.snapshot, local_files_only=True)
    model = CrystalCoderLMHeadModel.from_pretrained(
        args.snapshot,
        config=config,
        local_files_only=True,
        torch_dtype=torch.bfloat16,
    )
    model.to(args.device)
    model.eval()
    if args.seed is not None:
        torch.manual_seed(args.seed)
    inputs = tokenizer(prompt, return_tensors="pt").to(args.device)
    generation_args = {
        "max_new_tokens": args.max_tokens,
        "pad_token_id": tokenizer.eos_token_id,
        "do_sample": args.temperature > 0.0,
    }
    if args.temperature > 0.0:
        generation_args["temperature"] = args.temperature
    args.stage_path.write_text(json.dumps({"generationAttempted": True}))
    with torch.inference_mode():
        output = model.generate(**inputs, **generation_args)
    generated = output[0][inputs.input_ids.shape[1]:]
    print(json.dumps({
        "schemaVersion": "1",
        "status": "OK",
        "generationAttempted": True,
        "isolation": isolation,
        "runtime": runtime,
        "inputTokenCount": input_token_count,
        "completion": tokenizer.decode(generated, skip_special_tokens=False),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
