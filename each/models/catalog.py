"""A small, explicit catalog of local models evaluated for M2.

No plugin framework: a model is "available" only if its lawful weights are
already present on disk and its runtime can actually load them on this
Apple Silicon host, and "unavailable" is recorded with the concrete reason
(missing download, unverifiable conversion provenance, or no implemented
adapter) rather than silently omitted.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from each.hashing import sha256_file
from each.model_manifest import ModelManifest, build_manifest_from_snapshot, verify_snapshot_matches
from each.models.base import RepairModel
from each.paths import assert_no_symlink_escape, models_dir

HF_CACHE_DIR = models_dir() / ".hf_cache"
STARCODERBASE_REVISION = "88ec5781ad071a9d9e925cd28f327dea22eb5188"
STARCODERBASE_SOURCE_WEIGHTS = {
    "pytorch_model-00001-of-00007.bin": "dfde5c06da1a9b64727a04b1dd6b2414ead32b8513cef9b54eb12c6ba82b6c86",
    "pytorch_model-00002-of-00007.bin": "437479f655b31775554991fdabec6472244d334354ee03aea3a4c20b5d0b819b",
    "pytorch_model-00003-of-00007.bin": "a27c41541d9584e63f8bf5da6d493c053157b75e69d10928dff5ded809b16604",
    "pytorch_model-00004-of-00007.bin": "f4c16714179039c91190a9bec5935d7c25f7053d0423e3173257163fce16346f",
    "pytorch_model-00005-of-00007.bin": "fdaf103942e2a0757e576c2d64811b7a9f9c093f77bbfb7635235eeca7ece52b",
    "pytorch_model-00006-of-00007.bin": "aa2f8410b362aad53a0dea6511fac7460fd2e64a3c0bbe2c142324ed15587f1a",
    "pytorch_model-00007-of-00007.bin": "a0a6a38cfae8b0418e8b79ec30b6e14a0dfdd24a8237c238e98c80da6f3f5d1c",
}
STARCODERBASE_CONVERSION_SHA256 = "48bc14f9240345e8c81a5586e71a9f0ce7102fdc9ac80ded74199869653dbed7"
STARCODERBASE_MODEL_ID = (
    "bigcode/starcoderbase@88ec5781ad071a9d9e925cd28f327dea22eb5188#sha256:97c8813f705fc8c1"
)
STARCODERBASE_OUTPUT_FILES = {
    "README.md": "d3da47af55f61b85039733235b3697ac62da2f86f9e2e3d267268f282906d26a",
    "config.json": "15388cc9aec122696c90ea09eef715b3eabbb40dbd163e2ef3022558486ef652",
    "generation_config.json": "2cc1aa5aa9e15df6e1aff95c6f47a4dd8dca202b8f607a082a310122436dd6be",
    "merges.txt": "74b0a4bc1a97ebc1d227f69231b18574374ba052fb945b0fa0aa91d3c32504a2",
    "model-00001-of-00007.safetensors": "13aa8525c8cb80dcc4993813e826ee15361718ddbe2304618d9d8363ed0bbc68",
    "model-00002-of-00007.safetensors": "b6ad083c598a003f10c932ede91a509dcd0a394eff11c839d2554d737e4b1a19",
    "model-00003-of-00007.safetensors": "2cde31a23a4765affc9137622eb35e5458af9af897e71846f7b699af91d05b84",
    "model-00004-of-00007.safetensors": "cdf9da38c536b1cc07716226ee5a42f5b5372cbc7ab58bd89967bd8d768da1b6",
    "model-00005-of-00007.safetensors": "4436bd44704e6669ac6f8cc82cf3a6dda380bbfc00f0ec93eae720cb9f7e3b60",
    "model-00006-of-00007.safetensors": "c5fd0f2d564a8a2fdae479f45ef02a1b9c6622de675c52c217ba49ce979d1b9f",
    "model-00007-of-00007.safetensors": "53bcdbb9f6b4b5eaf7af28caab333104a6f7f017ff350409e7e10b03491f2517",
    "model.safetensors.index.json": "aadf1d70d35575587fdfe1dfeb7beda8a63bcd9663ff385818c0bcd2968f6c18",
    "special_tokens_map.json": "0823292e24ea07b89317e9ede9d08da2a1b6c014290c06908a7ad04f1efd6719",
    "tokenizer.json": "42b5a37ba11199f024f2b8873e1ecba98da33166e16f700bf7cb2304b0a5583f",
    "tokenizer_config.json": "95684c52ad9a970dbbb17576ee2237cb62902c1eff6804c7c91a4d6219a4a6d7",
    "vocab.json": "20175afb9f164fad4829aca2279f8df7eeff1e2e3f671378aaa287a740aff09f",
}
STARCODERBASE_LINEAGE = {
    "status": "ELIGIBLE",
    "scope": "documented-inspectable-training-dataset-lineage",
    "modelRepo": "bigcode/starcoderbase",
    "modelRevision": STARCODERBASE_REVISION,
    "datasetRepo": "bigcode/starcoderdata",
    "datasetRevision": "9fc30b578cedaec69e47302df72cf00feed7c8c4",
    "releaseDatasetRevision": "771a4a11d98f975ff1a8d5f29206f4ef57fd25d3",
    "datasetManifestSha256": "3636743c1f4356db564aa82f6379e0e9b59fed59f0e53faf9edac6c1fece7a34",
    "inspectionEvidenceSha256": "45e9fee3103c406069c0d2f752082c5d7b0fce102b904eae0a745c417a004cbd",
    "postTraining": "NONE_FOR_SELECTED_BASE_RELEASE",
    "postTrainingEvidence": "https://arxiv.org/html/2305.06161v2",
    "dossier": "docs/model-qualifications/starcoderbase.md",
    "limitations": [
        "Dataset lineage, not exhaustive per-record original-source attribution.",
        "Processed issue/commit records omit separate repository/license columns.",
        "No legal, originality, memorization or repair-correctness guarantee.",
    ],
}
OCTOCODER_REVISION = "0f863c63e38ba80fc2c4010f34a7f46d537a9eee"
OCTOCODER_SOURCE_WEIGHTS = dict(zip(
    [f"model-{i:05d}-of-00007.safetensors" for i in range(1, 8)],
    [
        "09ac7601c3d2f981714b44d2b52c9caebd0c77b934e56203d6021d91e00bf41c",
        "e983ec634521f4e32fb06de0a37de5a12adf1195f1d56ef662647a20179c2dd8",
        "dc9b7beaba475db0578e79ecc545a2f6c7647c05deab03bed3b92da52b930341",
        "1c3207001107e933840897b7b4f54f89c666115efa47c15e5624be58a8bae189",
        "71f732da4a08546b712eed97021bf29aa7d57f40f817528eab4a46214c6b15e9",
        "e3834928c2ea4919d6fe81e379ff16343f802dd57d9a00d1828c92df89a706ec",
        "b053bc62199e0d4636f6819412fb45065311f71a886194a14309ebbb1608c69b",
    ], strict=True,
))
OCTOCODER_CONVERSION_SHA256 = "6432ad00b631f340dee0665b8b9e29be678ed765c95a42f434184341ef3e0aca"
OCTOCODER_MODEL_ID = (
    "bigcode/octocoder@0f863c63e38ba80fc2c4010f34a7f46d537a9eee#sha256:553d84a480a0c794"
)
OCTOCODER_OUTPUT_FILES = {
    "README.md": "3d935543684971419a2328817b84af5f16b52a218ddf595ffad586c6b62fa072",
    "config.json": "747885d285914374fa4f630e1ecfcd3a35149d86b7598759b0bdcd58334ee439",
    "generation_config.json": "634b0b7323db9a5f1421a068af9f79c9a2b403496a74cd2ce44e6207af41d912",
    "merges.txt": "303127a244b0078878156c17229f36d11b7a3a3f8e47b7cfdbb304ff46be5030",
    "model-00001-of-00007.safetensors": "b7a16a596bea36e9d7bcef51c39606511f7b71a9937765a9f1d31d2c3dac9f54",
    "model-00002-of-00007.safetensors": "3fd47345858ece602413108baef3d378acba6d605637a0239216432dcb5ae4ab",
    "model-00003-of-00007.safetensors": "b8e8f1ffa9650464fbb35463efed64c1cce204f0c249f847b6f7c70211837b15",
    "model-00004-of-00007.safetensors": "c0361b47d87edd118bc3c8988771b12e98d16b228320fd4d7651fa1dfdf5ef91",
    "model-00005-of-00007.safetensors": "385f422c14238b7823d8f69cc55507dc561164140e2325fdf708b60898d97ac2",
    "model-00006-of-00007.safetensors": "6ea998c7c0699315afca94b9e403505faa688f9ba3d6f450b927f3c93cb75e21",
    "model-00007-of-00007.safetensors": "84f561e0893eed749437a8f609c9cf5909a6a3c9a9bc0225321a61c533cf2dbc",
    "model.safetensors.index.json": "25fdee8041250cedc75ff77eb2354b854aa53d4832289ab23ba3939bfe25cb5b",
    "special_tokens_map.json": "0823292e24ea07b89317e9ede9d08da2a1b6c014290c06908a7ad04f1efd6719",
    "tokenizer.json": "9af07a3123a1f4d75dcb85fbdc4c62f9b7873d23fa39c449d2240c3e33eb3ab5",
    "tokenizer_config.json": "4d8a576be1b7a37446e07a524202302c08ddc116e68b2e042d9fe4eaef46192e",
    "vocab.json": "20175afb9f164fad4829aca2279f8df7eeff1e2e3f671378aaa287a740aff09f",
}
OCTOCODER_LINEAGE = {
    "status": "ELIGIBLE",
    "scope": "documented-inspectable-training-dataset-lineage",
    "modelRepo": "bigcode/octocoder",
    "modelRevision": OCTOCODER_REVISION,
    "baseTraining": STARCODERBASE_LINEAGE,
    "pythonContinuation": {
        "tokens": 35_000_000_000,
        "dataset": "same StarCoder training dataset; Python continuation",
        "evidence": "https://arxiv.org/html/2305.06161v2",
    },
    "postTraining": {
        "evidence": "https://arxiv.org/html/2308.07124v2",
        "commitpackft": {
            "repo": "bigcode/commitpackft",
            "revision": "fc56fe33c030c6daa414c2b112c932b8eed085e6",
            "selectedCount": 5000,
            "exactSelectedRowIds": "NOT_RECOVERED",
            "languages": ["Python", "JavaScript", "Java", "Go", "C++", "Rust"],
        },
        "oasst": {
            "repo": "bigcode/oasst-octopack",
            "revision": "1f5db3451c66a64e37158fcdf8c1951db8e90b33",
            "fileSha256": "de45760df5da837d265615a17f23fddefb13c18569481e75a522d2bbb5732ada",
            "conversations": 8587,
            "selectedOriginalMessagesMatched": 17174,
            "originalRepo": "OpenAssistant/oasst1",
            "originalRevision": "fdf72ae0827c1cda404aff25b6603abec9e3399b",
            "originalFileSha256": "2ff4aa8999c911ffec7972ddf70359f220b3da184b731f3649f68b1391e19341",
            "syntheticTrue": 0,
            "syntheticFlagUnknown": 0,
        },
        "processingSource": "bigcode-project/octopack@e17a8f6470264286bc6a52eb8263582083bf3bf6",
    },
    "dossier": "docs/model-qualifications/octocoder-progress.md",
    "limitations": [
        "Dataset-stage eligibility, not exact 5000-row membership or historical training-job reconstruction.",
        "Intermediate guanaco repository returned 404; final-to-original OASST IDs/text hashes matched.",
        "Mixed source licenses, including sampled AGPL-3.0; no blanket permissive or legal certification.",
        "False synthetic metadata is not proof of exclusively human authorship.",
    ],
}

CRYSTAL_REVISION = "34fc9cd58acd87002560379a95b432147cc9135a"
CRYSTAL_SOURCE_WEIGHTS = {
    "pytorch_model-00001-of-00003.bin": "45d3ddd1d30058d55c8ccc250139aeeef318f14c39c53bbfa830fb669ac79ebe",
    "pytorch_model-00002-of-00003.bin": "c1c03da74d41317a7e2c5a799e09a8ee5ce4a94ba19976befa9f1135c48cf93a",
    "pytorch_model-00003-of-00003.bin": "c33c1d1ace28b1ac3a7afa7e82b18322446bacf76f12fd07401879dafd4d6cfe",
}
CRYSTAL_FILES = {
    "README.md": "54ba72133c87c357a9ae6e4b6bf628a7d44810368b6900e177db315bf3c5ca1f",
    "config.json": "f1fd9fba01f1fb3b26a04c8320b126d92602498a9d71fa20460e07e134fd5558",
    "configuration_crystalcoder.py": "dfbcd1553049fe82e893d0ec36314037c7f8c68a660775259abbef74d5b6fbf6",
    "modeling_crystalcoder.py": "f9587615339793b107824188cfe5e2e2a27f1a13c703fddbe20f49e39a89b75c",
    **CRYSTAL_SOURCE_WEIGHTS,
    "pytorch_model.bin.index.json": "ce88084fdcec7c1f5158bd8ccfb846e7251d6e3cc7d5ba182d578af4cb3fe525",
    "special_tokens_map.json": "77650f68e1bb047e9264ea447114e94cded61905308546bd5439062b86572ed9",
    "tokenization_crystalcoder_fast.py": "d8fa4edde1b2b022e93514b6e59da68c3346ed6d5eb855b59c3eb1708c65ff5a",
    "tokenizer.json": "c61adcb4e52988e4ee38ad9871e1f4e43ab128b0b5191225d307c2d022ca9569",
    "tokenizer_config.json": "9ce5cf84759e59cd3ecd63a2602ac130bcf3a63b7cdd76b3c24c2ae02aaf71e2",
}
CRYSTAL_MODEL_ID = (
    "LLM360/Crystal@34fc9cd58acd87002560379a95b432147cc9135a"
    "#sha256:af277cbad887d6d0"
)
CRYSTAL_RUNTIME_FILES = {
    "pyproject.toml": "b92c4a1013562ab224cf6aef6e246a6d60a954432ec9d7c02515d4eb5d30c5ed",
    "uv.lock": "91038254ab4b87f2651de4244fdf1dd4e95386b1907260ce6f734ee366cf3505",
    "crystal_runtime.py": "39c1e0937d6f5513541de3c96afa8fc904240b267aee609246758998903bd6cd",
}
CRYSTAL_RUNTIME_VERSIONS = {
    "python": "3.12.14",
    "torch": "2.14.1",
    "transformers": "4.44.2",
}
CRYSTAL_LINEAGE = {
    "status": "ELIGIBLE",
    "scope": "documented-inspectable-training-dataset-lineage",
    "modelRepo": "LLM360/Crystal",
    "modelRevision": CRYSTAL_REVISION,
    "startsFromScratch": True,
    "datasetRepo": "LLM360/CrystalCoderDatasets",
    "datasetRevision": "e42bace8739ade3b2d73025746bdac8a38345427",
    "processingSource": "LLM360/crystalcoder-data-prep",
    "stages": [
        "Stage 1: first half of SlimPajama",
        "Stage 2: second half of SlimPajama plus two epochs of StarCoderData",
        "Stage 3: selected Python/web StarCoderData plus SlimPajama",
    ],
    "postTraining": "NONE_FOR_SELECTED_BASE_RELEASE",
    "dossier": "docs/model-qualifications/crystalcoder.md",
    "limitations": [
        "Dataset-stage lineage, not exact training-sample or historical training-job reconstruction.",
        "No exhaustive per-record source-license, human-authorship, memorization or legal determination.",
        "Runtime directly imports the exact pinned publisher custom-code files inside a local sandbox.",
    ],
}

K2_REVISION = "400af6cd7de09fc9349cc6b5b24db20f778d5b72"
K2_PROFILE_SHA256 = "8b157bd5a49e8f0fa129c3e0278e0e823f8a4500eeb70adc4795d38bdb4d6d58"
K2_MODEL_ID = (
    "IFM/K2@400af6cd7de09fc9349cc6b5b24db20f778d5b72"
    "#sha256:8266ff62e09c6985"
)
K2_LINEAGE = {
    "status": "ELIGIBLE",
    "scope": "documented-inspectable-training-dataset-lineage",
    "modelRepo": "IFM/K2",
    "modelRevision": K2_REVISION,
    "startsFromScratch": True,
    "datasetRepo": "IFM/K2Datasets",
    "datasetRevision": "17cd6d34bf7d2a5c68df74d3f5fc0b4d19c4bdf4",
    "datasetManifestSha256": "4a731053c01bdcde19a6c97e4341b507c0b698e75f40b5f0f8b2198362dfee84",
    "chunkSourceMapSha256": "726bff67a872a87cc6b1e73924e3e3abf196e25b1a348c546f741c2b86af7878",
    "dataPreparationSource": "LLM360/k2-data-prep@f69878c898dce6bbb4d84c7982d1005132f8562f",
    "trainingSource": "LLM360/k2-train@869fbb9710bbe2c361f56c02a6d58ad83adbc755",
    "postTraining": "NONE_FOR_SELECTED_BASE_RELEASE",
    "dossier": "docs/model-qualifications/k2-progress.md",
    "limitations": [
        "Private bounded research only; no commercial-use or legal certification.",
        "Pile of Law is CC-BY-NC-SA-4.0; other sources retain heterogeneous upstream rights.",
        "Individual public web/code records may contain generated material even though no teacher-generated stage was identified.",
        "Dataset-stage lineage is not exact original-author attribution, lawful-training proof or output-license clearance.",
    ],
}

CODEGEN25_REVISION = "3cfb2194ec55e4a229f2d2184623b747fa24ab94"
CODEGEN25_PROFILE_SHA256 = "11ad1401525a01985c99746ce7fe56f758f9bb19bc98a21fc5c79b4a514eafe2"
CODEGEN25_MODEL_ID = (
    "Salesforce/codegen25-7b-multi_P@3cfb2194ec55e4a229f2d2184623b747fa24ab94"
    "#sha256:e164c1a2b77be037"
)
CODEGEN25_LINEAGE = {
    "status": "ELIGIBLE",
    "scope": "documented-inspectable-training-dataset-lineage",
    "modelRepo": "Salesforce/codegen25-7b-multi_P",
    "modelRevision": CODEGEN25_REVISION,
    "startsFromScratch": True,
    "datasetRepo": "bigcode/starcoderdata",
    "datasetRevision": "9fc30b578cedaec69e47302df72cf00feed7c8c4",
    "datasetManifestSha256": "3636743c1f4356db564aa82f6379e0e9b59fed59f0e53faf9edac6c1fece7a34",
    "trainingTokens": 1_400_000_000_000,
    "trainingRecipe": "more than four epochs with deterministic span-corruption/infill transformations",
    "postTraining": "NONE_FOR_SELECTED_MULTI_RELEASE",
    "dossier": "docs/model-qualifications/codegen25-multi.md",
    "limitations": [
        "The mono checkpoint's unidentified additional Python stage is excluded.",
        "The instruct checkpoint and its research-only license are excluded.",
        "StarCoderData retains heterogeneous source rights and record-level generated-content uncertainty.",
        "No legal, originality, memorization or output-license certification.",
    ],
}


def qualified_profile(name: str) -> dict:
    """Only the two independently assessed original artifacts; no family fallback."""
    if name == "starcoderbase":
        revision, weights, lineage, source_format, conversion_sha256, output_files, model_id = (
            STARCODERBASE_REVISION, STARCODERBASE_SOURCE_WEIGHTS, STARCODERBASE_LINEAGE, "pytorch",
            STARCODERBASE_CONVERSION_SHA256, STARCODERBASE_OUTPUT_FILES, STARCODERBASE_MODEL_ID,
        )
    elif name == "octocoder":
        revision, weights, lineage, source_format, conversion_sha256, output_files, model_id = (
            OCTOCODER_REVISION, OCTOCODER_SOURCE_WEIGHTS, OCTOCODER_LINEAGE, "safetensors",
            OCTOCODER_CONVERSION_SHA256, OCTOCODER_OUTPUT_FILES, OCTOCODER_MODEL_ID,
        )
    else:
        raise UnavailableModelError("training-data provenance is not qualified")
    if (
        lineage.get("status") != "ELIGIBLE"
        or lineage.get("modelRepo") != f"bigcode/{name}"
        or lineage.get("modelRevision") != revision
        or STARCODERBASE_LINEAGE.get("status") != "ELIGIBLE"
    ):
        raise UnavailableModelError("training-data provenance is not qualified")
    return {
        "name": name, "repo": f"bigcode/{name}", "revision": revision,
        "weights": weights, "lineage": lineage, "source_format": source_format,
        "conversion_sha256": conversion_sha256, "output_files": output_files,
        "model_id": model_id,
        "operation": f"{source_format}-fp32-to-safetensors-fp16",
    }


class UnavailableModelError(RuntimeError):
    """Raised with the exact, honest reason a catalog entry cannot be used."""


def _mlx_runtime_version() -> str:
    try:
        return version("mlx-lm")
    except PackageNotFoundError as exc:
        raise UnavailableModelError("MLX-LM is not installed; run uv sync --extra models") from exc


def _starcoderbase_mlx(*, max_tokens: int = 512) -> RepairModel:
    return _qualified_mlx("starcoderbase", max_tokens=max_tokens)


def _octocoder_mlx(*, max_tokens: int = 512) -> RepairModel:
    return _qualified_mlx("octocoder", max_tokens=max_tokens)


def _transformers_runtime_version() -> str:
    return "4.44.2"


def _crystalcoder_transformers(*, max_tokens: int = 512) -> RepairModel:
    if (
        CRYSTAL_LINEAGE.get("status") != "ELIGIBLE"
        or CRYSTAL_LINEAGE.get("modelRepo") != "LLM360/Crystal"
        or CRYSTAL_LINEAGE.get("modelRevision") != CRYSTAL_REVISION
        or CRYSTAL_LINEAGE.get("datasetRepo") != "LLM360/CrystalCoderDatasets"
        or CRYSTAL_LINEAGE.get("datasetRevision") != "e42bace8739ade3b2d73025746bdac8a38345427"
        or CRYSTAL_LINEAGE.get("postTraining") != "NONE_FOR_SELECTED_BASE_RELEASE"
    ):
        raise UnavailableModelError("CrystalCoder training-data provenance is not qualified")
    runtime_project = Path(__file__).resolve().parents[2] / "runtimes" / "crystal"
    runtime_paths = {
        "pyproject.toml": runtime_project / "pyproject.toml",
        "uv.lock": runtime_project / "uv.lock",
        "crystal_runtime.py": Path(__file__).with_name("crystal_runtime.py"),
    }
    runtime_drift = [
        name
        for name, path in runtime_paths.items()
        if not path.is_file() or sha256_file(path) != CRYSTAL_RUNTIME_FILES[name]
    ]
    if runtime_drift:
        raise UnavailableModelError(
            "qualified CrystalCoder runtime is absent or has changed: " + ", ".join(runtime_drift)
        )
    snapshot_dir = models_dir() / f"crystal-{CRYSTAL_REVISION}" / "original"
    assert_no_symlink_escape(snapshot_dir, label="qualified CrystalCoder artifact")
    manifest = ModelManifest(
        repo_id="LLM360/Crystal",
        revision=CRYSTAL_REVISION,
        license="Apache-2.0",
        runtime_name="transformers",
        runtime_version=_transformers_runtime_version(),
        quantization={},
        weights_sha256=dict(CRYSTAL_SOURCE_WEIGHTS),
        tokenizer_sha256=CRYSTAL_FILES["tokenizer.json"],
        conversion_chain="original publisher bfloat16 PyTorch shards; no conversion",
        files_sha256=dict(CRYSTAL_FILES),
        max_position_embeddings=2048,
        training_data_provenance=dict(CRYSTAL_LINEAGE),
    )
    drift = verify_snapshot_matches(snapshot_dir, manifest)
    if drift:
        raise UnavailableModelError(
            "qualified CrystalCoder artifact is absent or has changed: " + "; ".join(drift)
        )
    try:
        config = json.loads((snapshot_dir / "config.json").read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnavailableModelError("qualified CrystalCoder configuration is unreadable") from exc
    if (
        config.get("model_type") != "crystalcoder"
        or config.get("n_positions") != 2048
        or str(config.get("torch_dtype")) != "bfloat16"
    ):
        raise UnavailableModelError("qualified CrystalCoder configuration does not match its trusted profile")
    if manifest.model_id != CRYSTAL_MODEL_ID:
        raise UnavailableModelError("qualified CrystalCoder artifact identity does not match its trusted pin")
    from each.models.transformers_model import TransformersRepairModel

    return TransformersRepairModel(
        snapshot_dir,
        manifest,
        max_tokens=max_tokens,
        runtime_project=runtime_project,
        runtime_files_sha256=CRYSTAL_RUNTIME_FILES,
        runtime_versions=CRYSTAL_RUNTIME_VERSIONS,
    )


def _k2_mlx(*, max_tokens: int = 512) -> RepairModel:
    profile_path = Path(__file__).with_name("k2_profile.json")
    if not profile_path.is_file() or sha256_file(profile_path) != K2_PROFILE_SHA256:
        raise UnavailableModelError("qualified K2 artifact profile is absent or has changed")
    try:
        profile = json.loads(profile_path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnavailableModelError("qualified K2 artifact profile is unreadable") from exc
    if (
        K2_LINEAGE.get("status") != "ELIGIBLE"
        or K2_LINEAGE.get("modelRepo") != "IFM/K2"
        or K2_LINEAGE.get("modelRevision") != K2_REVISION
        or K2_LINEAGE.get("datasetRevision") != profile.get("lineageEvidence", {}).get("datasetRevision")
        or K2_LINEAGE.get("datasetManifestSha256")
        != profile.get("lineageEvidence", {}).get("datasetManifestSha256")
        or K2_LINEAGE.get("chunkSourceMapSha256")
        != profile.get("lineageEvidence", {}).get("chunkSourceMapSha256")
        or K2_LINEAGE.get("postTraining") != "NONE_FOR_SELECTED_BASE_RELEASE"
    ):
        raise UnavailableModelError("K2 training-data provenance is not qualified")
    if (
        profile.get("sourceRepo") != "IFM/K2"
        or profile.get("sourceRevision") != K2_REVISION
        or profile.get("sourceRepositoryManifestSha256")
        != "5566356d8ea8989989ab1258d4324776bf36dde9fac82c66533a5b5a718b5f2d"
        or profile.get("sourceVerificationRecordSha256")
        != "3a422e34687df44aeaad75063e50fa552d14e47e755aaaac0c369a99396e12f3"
        or profile.get("sourceIndexTensorCount") != 723
        or len(profile.get("sourceWeightsSha256", {})) != 27
        or profile.get("operation") != "publisher-fp16-safetensors-to-mlx-affine-int8"
        or profile.get("quantization")
        != {"mode": "affine", "bits": 8, "groupSize": 64, "effectiveBitsPerWeightReported": 8.5}
        or len(profile.get("outputWeightsSha256", {})) != 14
        or profile.get("trainingPerformed") is not False
        or profile.get("generationPerformed") is not False
    ):
        raise UnavailableModelError("K2 conversion does not match its qualified source artifact")

    snapshot_dir = models_dir() / "qualified" / "k2-int8" / K2_REVISION
    assert_no_symlink_escape(snapshot_dir, label="qualified K2 artifact")
    conversion_path = snapshot_dir / "conversion.json"
    if not conversion_path.is_file() or sha256_file(conversion_path) != K2_PROFILE_SHA256:
        raise UnavailableModelError("qualified K2 artifact is not provisioned or conversion evidence changed")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="IFM/K2",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        conversion_chain=(
            "original publisher FP16 safetensors -> local MLX affine 8-bit "
            "(group_size=64); retained conversion.json"
        ),
    )
    if any(
        manifest.files_sha256.get(name) != digest
        for name, digest in profile["outputFilesSha256"].items()
    ):
        raise UnavailableModelError("qualified K2 converted artifact has changed")
    if (
        set(manifest.files_sha256) != set(profile["outputFilesSha256"]) | {"conversion.json"}
        or manifest.weights_sha256 != profile["outputWeightsSha256"]
        or manifest.quantization
        != {"group_size": 64, "bits": 8, "mode": "affine"}
        or manifest.max_position_embeddings != 8192
    ):
        raise UnavailableModelError("qualified K2 converted artifact structure does not match its trusted profile")
    manifest = replace(manifest, training_data_provenance=dict(K2_LINEAGE))
    if manifest.model_id != K2_MODEL_ID:
        raise UnavailableModelError("qualified K2 artifact identity does not match its trusted pin")
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _codegen25_mlx(*, max_tokens: int = 512) -> RepairModel:
    profile_path = Path(__file__).with_name("codegen25_profile.json")
    if not profile_path.is_file() or sha256_file(profile_path) != CODEGEN25_PROFILE_SHA256:
        raise UnavailableModelError("qualified CodeGen2.5 artifact profile is absent or has changed")
    try:
        profile = json.loads(profile_path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnavailableModelError("qualified CodeGen2.5 artifact profile is unreadable") from exc
    if (
        CODEGEN25_LINEAGE.get("status") != "ELIGIBLE"
        or CODEGEN25_LINEAGE.get("modelRepo") != profile.get("sourceRepo")
        or CODEGEN25_LINEAGE.get("modelRevision") != profile.get("sourceRevision")
        or CODEGEN25_LINEAGE.get("datasetRevision")
        != profile.get("lineageEvidence", {}).get("datasetRevision")
        or CODEGEN25_LINEAGE.get("datasetManifestSha256")
        != profile.get("lineageEvidence", {}).get("datasetManifestSha256")
        or CODEGEN25_LINEAGE.get("postTraining") != "NONE_FOR_SELECTED_MULTI_RELEASE"
    ):
        raise UnavailableModelError("CodeGen2.5 training-data provenance is not qualified")
    if (
        profile.get("sourceRepo") != "Salesforce/codegen25-7b-multi_P"
        or profile.get("sourceRevision") != CODEGEN25_REVISION
        or profile.get("sourceRepositoryManifestSha256")
        != "09818758c2f96946748d0036cdc29bba299593ac81637333d36fad8dc546ef35"
        or profile.get("sourceVerificationRecordSha256")
        != "f93fb3edfc99dd76f4e0c95372c0f849dfe8b327e99e5f68deb0840098cf954d"
        or profile.get("sourceIndexTensorCount") != 323
        or len(profile.get("sourceWeightsSha256", {})) != 3
        or profile.get("fp16ConversionSha256")
        != "371d9a9ce1089a16d6bdddfa94b194757001cc10e2e1b23b0b947b94588beec3"
        or profile.get("fp16TensorRoundTripVerified") is not True
        or profile.get("tokenizerCompatibilityPatch", {}).get("outputSha256")
        != "8a6718384a609bcdda49504fb1fa38568940f27a2f96ac99badb945234f2171f"
        or profile.get("operation")
        != "publisher-fp32-pytorch-to-verified-fp16-safetensors-to-mlx-affine-int8"
        or profile.get("quantization")
        != {"mode": "affine", "bits": 8, "groupSize": 64, "effectiveBitsPerWeightReported": 8.5}
        or len(profile.get("outputWeightsSha256", {})) != 2
        or profile.get("runtime", {}).get("tiktoken") != "0.4.0"
        or profile.get("trainingPerformed") is not False
        or profile.get("generationPerformed") is not False
    ):
        raise UnavailableModelError("CodeGen2.5 conversion does not match its qualified source artifact")

    snapshot_dir = models_dir() / "qualified" / "codegen25-multi-int8" / CODEGEN25_REVISION
    assert_no_symlink_escape(snapshot_dir, label="qualified CodeGen2.5 artifact")
    conversion_path = snapshot_dir / "conversion.json"
    if not conversion_path.is_file() or sha256_file(conversion_path) != CODEGEN25_PROFILE_SHA256:
        raise UnavailableModelError(
            "qualified CodeGen2.5 artifact is not provisioned or conversion evidence changed"
        )
    tokenizer_module = Path(__file__).with_name("codegen25_tokenizer.py")
    tokenizer_hash = profile["tokenizerCompatibilityPatch"]["outputSha256"]
    if not tokenizer_module.is_file() or sha256_file(tokenizer_module) != tokenizer_hash:
        raise UnavailableModelError("qualified CodeGen2.5 local tokenizer code has changed")
    for package, expected in {
        "mlx": "0.32.3",
        "mlx-lm": "0.32.0",
        "transformers": "5.18.0",
        "tiktoken": "0.4.0",
        "torch": "2.14.1",
        "safetensors": "0.8.0",
    }.items():
        try:
            actual = version(package)
        except PackageNotFoundError as exc:
            raise UnavailableModelError(f"qualified CodeGen2.5 runtime package is missing: {package}") from exc
        if actual != expected:
            raise UnavailableModelError(
                f"qualified CodeGen2.5 runtime drift: {package} expected {expected}, found {actual}"
            )
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="Salesforce/codegen25-7b-multi_P",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        conversion_chain=(
            "publisher FP32 PyTorch -> verified FP16 safetensors -> local MLX affine 8-bit "
            "(group_size=64); exact tokenizer compatibility patch retained"
        ),
    )
    if any(
        manifest.files_sha256.get(name) != digest
        for name, digest in profile["outputFilesSha256"].items()
    ):
        raise UnavailableModelError("qualified CodeGen2.5 converted artifact has changed")
    if (
        set(manifest.files_sha256) != set(profile["outputFilesSha256"]) | {"conversion.json"}
        or manifest.weights_sha256 != profile["outputWeightsSha256"]
        or manifest.quantization != {"group_size": 64, "bits": 8, "mode": "affine"}
        or manifest.max_position_embeddings != 2048
    ):
        raise UnavailableModelError(
            "qualified CodeGen2.5 converted artifact structure does not match its trusted profile"
        )
    manifest = replace(manifest, training_data_provenance=dict(CODEGEN25_LINEAGE))
    if manifest.model_id != CODEGEN25_MODEL_ID:
        raise UnavailableModelError(
            "qualified CodeGen2.5 artifact identity does not match its trusted pin"
        )
    from each.models.codegen25_model import CodeGen25RepairModel

    return CodeGen25RepairModel(
        snapshot_dir,
        manifest,
        max_tokens=max_tokens,
        tokenizer_provenance={
            "mode": "reviewed-local-code",
            "sha256": tokenizer_hash,
            "sourceRevision": CODEGEN25_REVISION,
            "tiktokenVersion": "0.4.0",
        },
    )


def _qualified_mlx(name: str, *, max_tokens: int) -> RepairModel:
    profile = qualified_profile(name)
    snapshot_dir = models_dir() / "qualified" / f"{name}-fp16" / profile["revision"]
    assert_no_symlink_escape(snapshot_dir, label="qualified model artifact")
    conversion_path = snapshot_dir / "conversion.json"
    if not conversion_path.is_file():
        raise UnavailableModelError(f"qualified {name} artifact is not provisioned; conversion provenance required")
    import json

    try:
        conversion_bytes = conversion_path.read_bytes()
        conversion = json.loads(conversion_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UnavailableModelError(f"{name} conversion record is unreadable") from exc
    if (
        hashlib.sha256(conversion_bytes).hexdigest() != profile["conversion_sha256"]
        or not isinstance(conversion, dict)
        or conversion.get("sourceRepo") != profile["repo"]
        or conversion.get("sourceRevision") != profile["revision"]
        or conversion.get("operation") != profile["operation"]
        or conversion.get("sourceWeightsSha256") != profile["weights"]
        or conversion.get("outputFilesSha256") != profile["output_files"]
        or conversion.get("tensorRoundTripVerified") is not True
        or conversion.get("trainingPerformed") is not False
    ):
        raise UnavailableModelError(f"{name} conversion does not match its qualified source artifact")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id=profile["repo"],
        license="bigcode-openrail-m",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        conversion_chain=(
            "original publisher FP32 "
            + ("PyTorch" if name == "starcoderbase" else "safetensors")
            + " -> local FP16 safetensors; retained conversion.json"
        ),
    )
    if manifest.files_sha256.get("conversion.json") != profile["conversion_sha256"]:
        raise UnavailableModelError(f"qualified {name} conversion changed during verification")
    for filename, expected in conversion["outputFilesSha256"].items():
        if manifest.files_sha256.get(filename) != expected:
            raise UnavailableModelError(f"qualified {name} converted artifact has changed")
    if set(manifest.files_sha256) - {"conversion.json"} != set(conversion["outputFilesSha256"]):
        raise UnavailableModelError(f"qualified {name} conversion does not cover every output artifact")
    expected_weights = {
        f"model-{index:05d}-of-00007.safetensors"
        for index in range(1, 8)
    }
    if set(manifest.weights_sha256) != expected_weights or not expected_weights.issubset(conversion["outputFilesSha256"]):
        raise UnavailableModelError(f"qualified {name} conversion must bind all seven output weight shards")
    model_config = {"tie_word_embeddings": False}
    if name == "octocoder":
        index = json.loads((snapshot_dir / "model.safetensors.index.json").read_text())
        weight_map = index["weight_map"]
        model_config = {"tie_word_embeddings": "lm_head.weight" not in weight_map}
        aliases = conversion.get("sourceIndexOmittedAliases", {})
        if (
            set(weight_map.values()) != expected_weights
            or conversion.get("tensorCount") != len(weight_map)
            or conversion.get("sourceIndexVerified") is not True
            or conversion.get("runtimeModelConfig") != model_config
            or any(conversion.get("sourceFilesSha256", {}).get(k) != v for k, v in profile["weights"].items())
            or aliases not in ({}, {"lm_head.weight": "transformer.wte.weight"})
            or (aliases and (
                not model_config["tie_word_embeddings"] or "transformer.wte.weight" not in weight_map
                or conversion.get("sourceIndexTensorCount") != len(weight_map) + 1
            ))
        ):
            raise UnavailableModelError("OctoCoder conversion does not match its complete source tensor map")
    manifest = replace(manifest, training_data_provenance=dict(profile["lineage"]))
    if manifest.model_id != profile["model_id"]:
        raise UnavailableModelError(f"qualified {name} artifact identity does not match its trusted pin")
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(
        snapshot_dir, manifest, max_tokens=max_tokens,
        model_config=model_config,
        **({"prompt_format": "question-answer"} if name == "octocoder" else {}),
    )


def _granite_3b_code_base_mlx() -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "hub"
        / "models--mlx-community--granite-3b-code-base-4bit"
        / "snapshots"
        / "f55bfe8cccff2ac0285f3d5ad45ab63495a0896e"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="mlx-community/granite-3b-code-base-4bit",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # Verbatim provenance statement from the model card at this exact
        # snapshot (README.md in snapshot_dir), not an assumed chain: "The
        # Model mlx-community/granite-3b-code-base-4bit was converted to
        # MLX format from ibm-granite/granite-3b-code-base using mlx-lm
        # version 0.12.0."
        conversion_chain=(
            "ibm-granite/granite-3b-code-base -> mlx-community/granite-3b-code-base-4bit "
            "via mlx_lm.convert (4-bit, group_size=64), per the model card's own "
            "conversion statement (mlx-lm 0.12.0)"
        ),
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest)


def _granite_3_3_8b_instruct_mlx(*, max_tokens: int = 2048) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--ibm-granite--granite-3.3-8b-instruct"
        / "snapshots"
        / "51dd4bc2ade4059a6bd87649d68aa11e4fb2529b"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="ibm-granite/granite-3.3-8b-instruct",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # ORIGINAL publisher weights (ibm-granite's own repo, bf16
        # safetensors), not a third-party community re-conversion: no
        # conversion chain applies. config.json declares
        # architectures=["GraniteForCausalLM"]/model_type="granite" (a
        # modern, non-deprecated Granite generation, distinct from the
        # gpt_bigcode-family 8B/20B/34B code-instruct checkpoints already
        # catalogued); mlx_lm.utils._get_classes(config) was verified to
        # resolve this to mlx_lm.models.granite.{Model,ModelArgs} before
        # this snapshot was loaded.
        conversion_chain="none; original ibm-granite publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _qwen2_5_coder_14b_instruct_mlx(*, max_tokens: int = 2048) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--Qwen--Qwen2.5-Coder-14B-Instruct"
        / "snapshots"
        / "aedcc2d42b622764e023cf882b6652e646b95671"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="Qwen/Qwen2.5-Coder-14B-Instruct",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # ORIGINAL Qwen publisher weights (Qwen/Qwen2.5-Coder-14B-Instruct's
        # own repo, bf16 safetensors, LICENSE file present in the snapshot),
        # not a third-party community re-conversion: no conversion chain
        # applies. config.json declares model_type="qwen2"; verified
        # mlx_lm.utils._get_classes(config) resolves this to
        # mlx_lm.models.qwen2.{Model,ModelArgs} before this snapshot was
        # loaded. A pragmatic fallback candidate (not a pure-capacity
        # escalation) justified only after the newer, non-deprecated
        # granite-3.3-8b-instruct also failed to produce a verified repair.
        conversion_chain="none; original Qwen publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _granite_8b_code_instruct_128k_mlx(*, max_tokens: int = 512) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--ibm-granite--granite-8b-code-instruct-128k"
        / "snapshots"
        / "bed93d8de15bb9bb55cb1da10ae860e2883f4254"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="ibm-granite/granite-8b-code-instruct-128k",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # These are the ORIGINAL publisher weights (ibm-granite's own repo,
        # bf16 safetensors), not a third-party community re-conversion: no
        # conversion chain applies. mlx_lm.utils._get_classes(config) was
        # verified to resolve this config's declared
        # architectures=["LlamaForCausalLM"]/model_type="llama" to
        # mlx_lm.models.llama.{Model,ModelArgs} before this snapshot was
        # loaded, and mlx_lm.load() loads the original safetensors directly
        # (mlx_lm's Llama-family loader sanitizes/accepts the standard HF
        # safetensors key layout; no separate mlx-community conversion
        # artifact was produced or required).
        conversion_chain="none; original ibm-granite publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _granite_20b_code_instruct_mlx(*, max_tokens: int = 2048) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--ibm-granite--granite-20b-code-instruct"
        / "snapshots"
        / "03d2f3664ed0059eac4d35797b43fb52d551bb5b"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="ibm-granite/granite-20b-code-instruct",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # ORIGINAL publisher weights (ibm-granite's own repo, bf16
        # safetensors), not a third-party community re-conversion: no
        # conversion chain applies. config.json declares
        # architectures=["GPTBigCodeForCausalLM"]/model_type="gpt_bigcode";
        # mlx_lm.utils._get_classes(config) was verified to resolve this to
        # mlx_lm.models.gpt_bigcode.{Model,ModelArgs} before this snapshot
        # was loaded.
        conversion_chain="none; original ibm-granite publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _granite_34b_code_instruct_mlx(*, max_tokens: int = 2048) -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "models--ibm-granite--granite-34b-code-instruct"
        / "snapshots"
        / "4bdfb589ebd261be0942a00dd239175d9d65bc47"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="ibm-granite/granite-34b-code-instruct",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        # ORIGINAL publisher weights (ibm-granite's own repo, bf16
        # safetensors), not a third-party community re-conversion: no
        # conversion chain applies. config.json declares
        # architectures=["GPTBigCodeForCausalLM"]/model_type="gpt_bigcode"
        # (same family as the 20B sibling); mlx_lm.utils._get_classes(config)
        # was verified to resolve this to mlx_lm.models.gpt_bigcode.{Model,
        # ModelArgs} before this snapshot was loaded.
        conversion_chain="none; original ibm-granite publisher bf16 safetensors loaded directly via mlx_lm",
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest, max_tokens=max_tokens)


def _granite_3b_code_instruct_mlx() -> RepairModel:
    snapshot_dir = (
        HF_CACHE_DIR
        / "hub"
        / "models--mlx-community--granite-3b-code-instruct-4bit"
        / "snapshots"
        / "1fe6b1a221a5a79606e7a94604bb1ea5cc512ff0"
    )
    if not snapshot_dir.exists():
        raise UnavailableModelError(f"snapshot not downloaded: {snapshot_dir}")
    manifest = build_manifest_from_snapshot(
        snapshot_dir,
        repo_id="mlx-community/granite-3b-code-instruct-4bit",
        license="Apache-2.0",
        runtime_name="mlx-lm",
        runtime_version=_mlx_runtime_version(),
        conversion_chain=(
            "ibm-granite/granite-3b-code-instruct -> mlx-community/granite-3b-code-instruct-4bit "
            "via mlx_lm.convert (4-bit, group_size=64), per the model card's own "
            "conversion statement (mlx-lm 0.12.0)"
        ),
    )
    from each.models.mlx_model import MLXRepairModel

    return MLXRepairModel(snapshot_dir, manifest)


def _octocoder_transformers_mps() -> RepairModel:
    weights_dir = models_dir() / "bigcode--octocoder"
    index_path = weights_dir / "model.safetensors.index.json"
    if not index_path.exists():
        raise UnavailableModelError(f"weights not downloaded: {weights_dir}")
    import json

    shard_names = sorted(set(json.loads(index_path.read_text())["weight_map"].values()))
    missing = [name for name in shard_names if not (weights_dir / name).exists()]
    if missing:
        raise UnavailableModelError(
            f"download incomplete: {len(missing)}/{len(shard_names)} safetensors shard(s) missing "
            f"({', '.join(missing)}); resume with huggingface_hub.snapshot_download"
        )
    raise UnavailableModelError(
        "no Transformers/MPS RepairModel adapter is implemented yet for OctoCoder "
        "(15.5B dense StarCoder-family); MLX-LM was selected as the initial M2 "
        "Builder backend instead (see docs/EACH_BOOTSTRAP_MANDATE.md M2 evidence)"
    )


def _granite_gguf_llamacpp() -> RepairModel:
    raise UnavailableModelError(
        "no llama.cpp/GGUF conversion with recorded provenance exists for any M2 "
        "candidate model; the mandate requires a recorded conversion chain before "
        "using a converted GGUF artifact, and none was produced or verified"
    )


_CATALOG: dict[str, Callable[..., RepairModel]] = {
    "starcoderbase-mlx": _starcoderbase_mlx,
    "octocoder-mlx": _octocoder_mlx,
    "crystalcoder-transformers": _crystalcoder_transformers,
    "k2-65b-mlx": _k2_mlx,
    "codegen25-7b-multi-mlx": _codegen25_mlx,
    "granite-3b-code-base-mlx": _granite_3b_code_base_mlx,
    "granite-3b-code-instruct-mlx": _granite_3b_code_instruct_mlx,
    "granite-8b-code-instruct-128k-mlx": _granite_8b_code_instruct_128k_mlx,
    "granite-3.3-8b-instruct-mlx": _granite_3_3_8b_instruct_mlx,
    "qwen2.5-coder-14b-instruct-mlx": _qwen2_5_coder_14b_instruct_mlx,
    "granite-20b-code-instruct-mlx": _granite_20b_code_instruct_mlx,
    "granite-34b-code-instruct-mlx": _granite_34b_code_instruct_mlx,
    "octocoder-transformers-mps": _octocoder_transformers_mps,
    "granite-gguf-llamacpp": _granite_gguf_llamacpp,
}


def load_model(key: str, **kwargs) -> RepairModel:
    """Load only an explicitly qualified model; all other entries fail closed.

    Historical builders remain for adapter tests and receipt interpretation;
    their availability is not permission to use them for new target generation.
    """
    if key not in _CATALOG:
        raise UnavailableModelError(f"unknown model key: {key!r}; known keys: {sorted(_CATALOG)}")
    if key in {
        "starcoderbase-mlx",
        "octocoder-mlx",
        "crystalcoder-transformers",
        "k2-65b-mlx",
        "codegen25-7b-multi-mlx",
    }:
        return _CATALOG[key](**kwargs)
    raise UnavailableModelError(
        f"training-data provenance is not qualified for {key!r}; "
        "public weights, artifact hashes and a model license are insufficient. "
        "EACH requires reviewed base-training and post-training dataset lineage "
        "before target generation. This catalog entry has no such qualification."
    )
