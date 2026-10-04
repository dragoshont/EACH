from __future__ import annotations

import pytest

pytest.importorskip("tiktoken")
pytest.importorskip("transformers")

from each.models.codegen25_tokenizer import CodeGen25Tokenizer

PUBLISHER_SOURCE_SHA256 = "965c68328a5d2d810f585f0528ea80da2dc48fabc37bea9186168f072794b6cf"
PUBLISHER_VECTORS = {
    "int add(int a, int b) { return a + b; }\nπ": [
        600, 751, 7, 600, 257, 11, 493, 275, 8, 1391, 1441, 257, 1343, 275, 26, 1782, 198, 46582,
    ],
    "<fim_prefix>abc<fim_suffix>xyz<fim_middle>": [50295, 39305, 50297, 5431, 89, 50296],
    "prefix<mask_1>suffix<|endoftext|><sep><mask_1>": [
        40290, 51199, 37333, 844, 50256, 50317, 51199,
    ],
}


def test_codegen25_tokenizer_round_trips_code_and_byte_tokens() -> None:
    tokenizer = CodeGen25Tokenizer()
    for text, publisher_ids in PUBLISHER_VECTORS.items():
        assert tokenizer.encode(text) == publisher_ids
        assert tokenizer.decode(publisher_ids) == text
    assert tokenizer.vocab_size == 51200
    assert tokenizer.get_vocab()


def test_codegen25_tokenizer_preserves_infill_special_tokens() -> None:
    tokenizer = CodeGen25Tokenizer()
    publisher_ids = {
        "<mask_1>": 51199,
        "<sep>": 50317,
        "<eom>": 50318,
        "<fim_prefix>": 50295,
        "<fim_middle>": 50296,
        "<fim_suffix>": 50297,
    }
    for token, token_id in publisher_ids.items():
        assert tokenizer.convert_tokens_to_ids(token) == token_id
        assert tokenizer.decode([token_id]) == token


def test_codegen25_tokenizer_add_special_flag_remains_effective() -> None:
    with_special = CodeGen25Tokenizer(add_special_tokens=True)
    without_special = CodeGen25Tokenizer(add_special_tokens=False)
    assert with_special.vocab_size == 51200
    assert without_special.vocab_size < with_special.vocab_size
