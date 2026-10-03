"""Provision either qualified original GPT-BigCode artifact locally.

Run on the development Mac with the models extra after Hugging Face access
has been granted. Original publisher shards are retained; no inference runs.
"""

from __future__ import annotations

import json
import shutil
from importlib.metadata import version
from pathlib import Path

from each.hashing import sha256_file
from each.models.catalog import qualified_profile
from each.paths import FileLock, assert_no_symlink_escape, models_dir


def provision(name: str = "starcoderbase") -> Path:
    profile = qualified_profile(name)  # Fail closed before download or tensor loading.
    import torch
    from huggingface_hub import HfApi, snapshot_download
    from safetensors import safe_open
    from safetensors.torch import load_file, save_file

    root = models_dir()
    destination = root / "qualified" / f"{name}-fp16" / profile["revision"]
    assert_no_symlink_escape(destination, label="qualified model conversion")
    with FileLock(root / f"{name}-provision.lock"):
        if destination.exists():
            raise ValueError("Conversion or partial destination already exists; preserve it rather than overwriting it")
        if shutil.disk_usage(root).free < 120 * 1024**3:
            raise ValueError("Original and converted artifacts require at least 120 GiB free disk")
        info = HfApi().model_info(profile["repo"], revision=profile["revision"], files_metadata=True)
        publisher_hashes = {f.rfilename: f.lfs.sha256 for f in info.siblings if f.lfs}
        if info.sha != profile["revision"] or any(
            publisher_hashes.get(k) != v for k, v in profile["weights"].items()
        ):
            raise ValueError("Publisher metadata does not match qualified source pins")
        snapshot = Path(snapshot_download(
            profile["repo"],
            revision=profile["revision"],
            cache_dir=str(root / ".hf_cache"),
            allow_patterns=[
                "*.json", "merges.txt", "vocab.json", "README.md",
                *profile["weights"],
            ],
            ignore_patterns=["*.bin*"] if profile["source_format"] == "safetensors" else ["*.safetensors*"],
            max_workers=2,
        ))
        original_files = {
            path.name: sha256_file(path)
            for path in snapshot.iterdir()
            if path.is_file()
        }
        if any(original_files.get(k) != v for k, v in profile["weights"].items()):
            raise ValueError("Downloaded original weights do not match the pinned publisher identities")
        source_index_name = (
            "model.safetensors.index.json" if profile["source_format"] == "safetensors"
            else "pytorch_model.bin.index.json"
        )
        source_map = json.loads((snapshot / source_index_name).read_text())["weight_map"]
        if set(source_map.values()) != set(profile["weights"]):
            raise ValueError("Original tensor index does not cover exactly the qualified shards")
        omitted_aliases = {}
        original_index_count = len(source_map)
        if profile["source_format"] == "safetensors":
            actual_map = {}
            for shard_name in profile["weights"]:
                with safe_open(snapshot / shard_name, framework="pt", device="cpu") as shard:
                    for key in shard.keys():  # noqa: SIM118 - safe_open is not an iterable dict
                        if key in actual_map:
                            raise ValueError("Duplicate tensor name across original shards")
                        actual_map[key] = shard_name
            if actual_map != source_map:
                # The pinned OctoCoder index lists a head absent from its
                # actual safetensors. Original GPTBigCode configuration ties
                # that alias to the stored input embedding. Admit precisely
                # this inspected discrepancy, never arbitrary missing weights.
                from transformers import GPTBigCodeConfig

                config = json.loads((snapshot / "config.json").read_text())
                if (
                    name != "octocoder"
                    or config.get("model_type") != "gpt_bigcode"
                    or not GPTBigCodeConfig.from_dict(config).tie_word_embeddings
                    or "transformer.wte.weight" not in actual_map
                    or set(source_map) - set(actual_map) != {"lm_head.weight"}
                    or actual_map != {k: v for k, v in source_map.items() if k != "lm_head.weight"}
                ):
                    raise ValueError("Original shard tensors do not match the publisher index")
                omitted_aliases = {"lm_head.weight": "transformer.wte.weight"}
                source_map = actual_map
        destination.mkdir(parents=True, exist_ok=False, mode=0o700)
        outputs = {}
        weight_map = {}
        tensor_count = 0
        for index, shard_name in enumerate(profile["weights"], start=1):
            output_name = f"model-{index:05d}-of-00007.safetensors"
            output = destination / output_name
            if output.exists():
                raise ValueError("Partial conversion exists; preserve it and inspect before retrying")
            state = (
                load_file(snapshot / shard_name, device="cpu") if profile["source_format"] == "safetensors"
                else torch.load(snapshot / shard_name, map_location="cpu", weights_only=True, mmap=True)
            )
            if set(state) != {k for k, v in source_map.items() if v == shard_name}:
                raise ValueError("Original shard tensors do not match the publisher index")
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
            if not path.is_file() or path.suffix in {".bin", ".safetensors"} or path.name.endswith(".index.json"):
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
            "sourceRepo": profile["repo"],
            "sourceRevision": profile["revision"],
            "operation": profile["operation"],
            "sourceWeightsSha256": profile["weights"],
            "sourceFilesSha256": original_files,
            "outputFilesSha256": outputs,
            "torchVersion": version("torch"),
            "safetensorsVersion": version("safetensors"),
            "mlxLmVersion": version("mlx-lm"),
            "transformersVersion": version("transformers"),
            "sourceDtype": "float32",
            "outputDtype": "float16",
            "tensorCount": tensor_count,
            "tensorRoundTripVerified": True,
            "sourceIndexVerified": True,
            "sourceIndexTensorCount": original_index_count,
            "sourceIndexOmittedAliases": omitted_aliases,
            "runtimeModelConfig": {"tie_word_embeddings": "lm_head.weight" not in source_map},
            "precisionChange": "FP32 to FP16; explicit rounding, not byte-identical weights",
            "trainingPerformed": False,
            "inferencePerformed": False,
        }
        with (destination / "conversion.json").open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2)
        (destination / "conversion.json").chmod(0o600)
        return destination


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["starcoderbase", "octocoder"], default="starcoderbase")
    print(provision(parser.parse_args().model))
