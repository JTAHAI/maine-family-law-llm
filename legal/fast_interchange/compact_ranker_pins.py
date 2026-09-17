"""Code-owned hashes from pinned acquisitions; a local receipt is not authority.

BERT: ce341fa4fce71a445664ed382fd77ff65fc4806c (narcolepticchicken).
DeBERTa: b5c6e9da73abc3711f593f705371cdbe9e0fe422 (mixedbread-ai).
All tokenizer/config/notice files must match, not just trained weight bytes.
These are research candidates; these pins do not grant production admission.
"""

from .compact_cpu import PinnedFile, fail

BERT_SHA256 = "f5d4bf917d7da08c3c1ec8fa346b64505787abed6e785c4ec8bc9c122568ac86"
MIXEDBREAD_SHA256 = "a29bc212faf59c136ad0fd5712ecd2346e7b32c44a25b690625bc9ecebb14b8f"

RANKER_PINS = {
    BERT_SHA256: {
        "README.md": (4243, "49c72bc8b36c214544b9b5b6c1ad4a4b544bd4bea5675a3921e87e5969bf9caf"),
        "config.json": (844, "467f8983d532c2d51816e75503fb8609b5b2dff83d0bdcf5174c7c37f574bca2"),
        "tokenizer.json": (
            711649,
            "91f1def9b9391fdabe028cd3f3fcc4efd34e5d1f08c3bf2de513ebb5911a1854",
        ),
        "tokenizer_config.json": (
            633,
            "76f289cf6d08d122059207969431fe309b6c7c4ee862fcaa8520599015523047",
        ),
        "model.safetensors": (90866412, BERT_SHA256),
        "config_sentence_transformers.json": (
            253,
            "061b6135a5b20dacb1c150a9f79bccbc19b0b9edcdb3795535564313d033d377",
        ),
    },
    MIXEDBREAD_SHA256: {
        "LICENSE": (10762, "4b0dfefcb74f1e50a8df72a9f2bf0088753f8568bc479387292469b4948705d4"),
        "README.md": (49546, "7d0553b55a91f07a820125a5f4ec547489e50493fa2d2d6624fcc0f5725d1c7f"),
        "config.json": (968, "470a53befc79da411cc04e466770d9f219f3c14adb276bfa0a58df28774ceade"),
        "tokenizer.json": (
            8649139,
            "305674b4d785287feecfb5f73f24aa75e9b57c87c579cfe24fbd207987d4b4c4",
        ),
        "tokenizer_config.json": (
            1447,
            "aafc9f36a056307bf0cbfcbd42fe00d9df89083d23db6114466c8bfaedb09ce5",
        ),
        "special_tokens_map.json": (
            970,
            "b2f1b2f15f29a6b6d9d6ea4eca1675d2c231a71477f151d48f79cc83a625ba21",
        ),
        "added_tokens.json": (
            23,
            "dc046d04c9b0ada7ae6f1dc89c465801799acdf0c9a6aab8c15a1b2d5ca4e91f",
        ),
        "spm.model": (2464616, "c679fbf93643d19aab7ee10c0b99e460bdbc02fedf34b92b05af343b4af586fd"),
        "model.safetensors": (141685186, MIXEDBREAD_SHA256),
    },
}


def verify_ranker_inventory(files):
    if not isinstance(files, tuple) or any(not isinstance(r, PinnedFile) for r in files):
        fail("compact_model_integrity_failed")
    weights = [r.sha256 for r in files if r.path.name == "model.safetensors"]
    if len(weights) != 1 or weights[0] not in RANKER_PINS:
        fail("reranker_candidate_not_allowlisted")
    expected = RANKER_PINS[weights[0]]
    if (
        len(files) != len(expected)
        or len({r.path.parent for r in files}) != 1
        or any(type(r.bytes) is not int or type(r.sha256) is not str for r in files)
        or {r.path.name: (r.bytes, r.sha256) for r in files} != expected
    ):
        fail("compact_model_integrity_failed")
    return weights[0]
