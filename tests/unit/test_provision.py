"""Tiny synthetic tensors only: these fixtures do not qualify a neural model."""
import json
from types import SimpleNamespace

import pytest

from each.hashing import sha256_file
from each.models import provision_starcoderbase as provisioning


@pytest.fixture
def source(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")
    safetensors = pytest.importorskip("safetensors.torch")
    hub = pytest.importorskip("huggingface_hub")
    snapshot = tmp_path / "source"
    snapshot.mkdir()
    weights, weight_map = {}, {}
    for i in range(1, 8):
        filename = f"model-{i:05d}-of-00007.safetensors"
        key = "lm_head.weight" if i == 7 else f"layer.{i}"
        safetensors.save_file({key: torch.tensor([1.234567], dtype=torch.float32)}, snapshot / filename)
        weights[filename] = sha256_file(snapshot / filename)
        weight_map[key] = filename
    (snapshot / "model.safetensors.index.json").write_text(json.dumps({"weight_map": weight_map}))
    (snapshot / "config.json").write_text('{"torch_dtype":"float32","n_positions":8192}')
    (snapshot / "tokenizer.json").write_text("{}")
    root = tmp_path / "models"
    root.mkdir()
    profile = {
        "repo": "fixture/only", "revision": "a" * 40, "weights": weights,
        "source_format": "safetensors", "operation": "safetensors-fp32-to-safetensors-fp16",
    }
    monkeypatch.setattr(provisioning, "qualified_profile", lambda name: profile)
    monkeypatch.setattr(provisioning, "models_dir", lambda: root)
    monkeypatch.setattr(provisioning.shutil, "disk_usage", lambda _: SimpleNamespace(free=121 * 1024**3))
    monkeypatch.setattr(provisioning, "version", lambda name: "fixture")
    info = SimpleNamespace(sha=profile["revision"], siblings=[
        SimpleNamespace(rfilename=k, lfs=SimpleNamespace(sha256=v)) for k, v in weights.items()
    ])
    monkeypatch.setattr(hub, "HfApi", lambda: SimpleNamespace(model_info=lambda *a, **k: info))
    requests = []
    monkeypatch.setattr(hub, "snapshot_download", lambda *a, **k: requests.append(k) or str(snapshot))
    return snapshot, root, profile, requests, info


def test_conversion_roundtrip_index_and_no_duplicate_bin_download(source):
    snapshot, _root, profile, requests, _ = source
    destination = provisioning.provision("octocoder")
    record = json.loads((destination / "conversion.json").read_text())
    assert record["tensorCount"] == 7
    assert record["tensorRoundTripVerified"] is True
    assert record["sourceIndexVerified"] is True
    assert record["runtimeModelConfig"] == {"tie_word_embeddings": False}
    assert record["trainingPerformed"] is False
    assert record["sourceWeightsSha256"] == profile["weights"]
    assert requests[0]["ignore_patterns"] == ["*.bin*"]
    assert set(record["outputFilesSha256"]) == {p.name for p in destination.iterdir()} - {"conversion.json"}
    assert json.loads((destination / "config.json").read_text())["torch_dtype"] == "float16"
    assert all(sha256_file(snapshot / k) == v for k, v in profile["weights"].items())
    with pytest.raises(ValueError, match="already exists"):
        provisioning.provision("octocoder")


@pytest.mark.parametrize("failure", ["hash", "metadata", "index", "partial", "disk"])
def test_provision_fails_closed_and_preserves_originals(source, monkeypatch, failure):
    snapshot, root, profile, requests, info = source
    destination = root / "qualified" / "octocoder-fp16" / profile["revision"]
    if failure == "hash":
        (snapshot / next(iter(profile["weights"]))).write_bytes(b"corrupt fixture")
    elif failure == "metadata":
        info.sha = "b" * 40
    elif failure == "index":
        (snapshot / "model.safetensors.index.json").write_text('{"weight_map":{}}')
    elif failure == "partial":
        destination.mkdir(parents=True)
        (destination / "preserve").write_bytes(b"partial")
    else:
        monkeypatch.setattr(provisioning.shutil, "disk_usage", lambda _: SimpleNamespace(free=119 * 1024**3))
    with pytest.raises(ValueError):
        provisioning.provision("octocoder")
    assert not (destination / "conversion.json").exists()
    if failure in {"metadata", "partial", "disk"}:
        assert requests == []
    if failure == "partial":
        assert (destination / "preserve").read_bytes() == b"partial"
