"""Explicitly provision the qualified original StarCoderBase artifact locally.

Run on the development Mac with the models extra after Hugging Face access
has been granted. Original publisher shards are retained; no inference runs.
"""

from __future__ import annotations

import json
import shutil
from importlib.metadata import version
from pathlib import Path

from each.hashing import sha256_file
from each.models.catalog import STARCODERBASE_REVISION, STARCODERBASE_SOURCE_WEIGHTS
from each.paths import FileLock, assert_no_symlink_escape, models_dir


def provision() -> Path:
    import torch
    from huggingface_hub import snapshot_download
    from safetensors import safe_open
    from safetensors.torch import save_file

    root = models_dir()
    destination = root / "qualified" / "starcoderbase-fp16" / STARCODERBASE_REVISION
    assert_no_symlink_escape(destination, label="qualified model conversion")
    with FileLock(root / "starcoderbase-provision.lock"):
        if (destination / "conversion.json").exists():
            raise ValueError("StarCoderBase conversion already exists; verify it rather than overwriting it")
        if shutil.disk_usage(root).free < 120 * 1024**3:
            raise ValueError("StarCoderBase original and converted artifacts require at least 120 GiB free disk")
        snapshot = Path(snapshot_download(
            "bigcode/starcoderbase",
            revision=STARCODERBASE_REVISION,
            cache_dir=str(root / ".hf_cache"),
            allow_patterns=[
                "*.json", "merges.txt", "vocab.json", "README.md",
                "pytorch_model-*.bin",
            ],
            max_workers=2,
        ))
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        original_files = {
            path.name: sha256_file(path)
            for path in snapshot.iterdir()
            if path.is_file()
        }
        if any(original_files.get(name) != expected for name, expected in STARCODERBASE_SOURCE_WEIGHTS.items()):
            raise ValueError("Downloaded original StarCoderBase weights do not match the pinned publisher identities")
        outputs = {}
        weight_map = {}
        tensor_count = 0
        for index, name in enumerate(STARCODERBASE_SOURCE_WEIGHTS, start=1):
            output_name = f"model-{index:05d}-of-00007.safetensors"
            output = destination / output_name
            if output.exists():
                raise ValueError("Partial conversion exists; preserve it and inspect before retrying")
            state = torch.load(snapshot / name, map_location="cpu", weights_only=True, mmap=True)
            converted = {}
            for key, value in state.items():
                if not isinstance(key, str) or not isinstance(value, torch.Tensor):
                    raise TypeError("Publisher weight shard contains an unsupported object")
                if value.is_floating_point() and value.dtype != torch.float32:
                    raise ValueError("Expected original FP32 floating-point tensors")
                converted[key] = value.to(dtype=torch.float16).contiguous() if value.is_floating_point() else value.contiguous()
                if key in weight_map:
                    raise ValueError("Duplicate tensor name across original shards")
                weight_map[key] = output_name
            save_file(converted, str(output), metadata={"format": "pt"})
            output.chmod(0o600)
            with safe_open(output, framework="pt", device="cpu") as saved:
                if set(saved.keys()) != set(converted):
                    raise ValueError("Converted tensor names do not match the original shard")
                for key, expected in converted.items():
                    if not torch.equal(saved.get_tensor(key), expected):
                        raise ValueError("Converted tensor round-trip verification failed")
            tensor_count += len(converted)
            outputs[output_name] = sha256_file(output)
            del converted, state
            print(f"Converted and verified shard {index}/7", flush=True)

        for path in snapshot.iterdir():
            if not path.is_file() or path.suffix == ".bin" or path.name == "pytorch_model.bin.index.json":
                continue
            target = destination / path.name
            if target.exists():
                raise ValueError("Conversion metadata destination already exists")
            data = path.read_bytes()
            if path.name == "config.json":
                config = json.loads(data)
                config["torch_dtype"] = "float16"
                data = (json.dumps(config, indent=2) + "\n").encode()
            with target.open("xb") as stream:
                stream.write(data)
            target.chmod(0o600)
            outputs[target.name] = sha256_file(target)
        index_path = destination / "model.safetensors.index.json"
        with index_path.open("x", encoding="utf-8") as stream:
            json.dump({"metadata": {}, "weight_map": weight_map}, stream, indent=2)
        index_path.chmod(0o600)
        outputs[index_path.name] = sha256_file(index_path)
        record = {
            "sourceRepo": "bigcode/starcoderbase",
            "sourceRevision": STARCODERBASE_REVISION,
            "operation": "pytorch-fp32-to-safetensors-fp16",
            "sourceWeightsSha256": STARCODERBASE_SOURCE_WEIGHTS,
            "sourceFilesSha256": original_files,
            "outputFilesSha256": outputs,
            "torchVersion": version("torch"),
            "safetensorsVersion": version("safetensors"),
            "tensorCount": tensor_count,
            "tensorRoundTripVerified": True,
            "precisionChange": "FP32 to FP16; explicit rounding, not byte-identical weights",
            "trainingPerformed": False,
            "inferencePerformed": False,
        }
        with (destination / "conversion.json").open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2)
        (destination / "conversion.json").chmod(0o600)
        return destination


if __name__ == "__main__":
    print(provision())
