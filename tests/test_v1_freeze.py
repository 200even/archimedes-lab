from __future__ import annotations

import hashlib
import json
from pathlib import Path

from archimedes_v0.v1_agent_interfaces import authorized_response_schema


def test_v1_prompt_manifest_matches_exact_files():
    manifest = json.loads(Path("V1_PROMPT_MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "FROZEN_PRE_EXPOSURE_NOT_AUTHORIZED_FOR_BENCHMARK"
    for role, row in manifest["prompts"].items():
        raw = Path(row["path"]).read_bytes()
        assert len(raw) == row["utf8_bytes"], role
        assert hashlib.sha256(raw).hexdigest() == row["sha256"], role
    assert manifest["compute_envelope"] == {
        "full_calls": 13,
        "flat_calls": 13,
        "full_max_output_tokens": 40960,
        "flat_max_output_tokens": 40960,
        "B_side_model_calls": 0,
    }


def _walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def test_provider_partition_schema_preserves_scientific_cardinality_constraints():
    root = authorized_response_schema("CandidatePartitionSet")
    candidates = root["properties"]["candidates"]
    assert candidates["minItems"] == 0
    assert candidates["maxItems"] == 4
    partition = candidates["items"]
    assert partition["properties"]["group_count"] == {"type": "integer", "minimum": 2, "maximum": 4}
    assert partition["properties"]["schema_version"] == {"enum": ["1.0"], "type": "string"}
    entity_group = partition["properties"]["entity_group"]
    assert entity_group["additionalProperties"] is False
    assert len(entity_group["required"]) == 16
    assert entity_group["required"][0] == "entity_00"
    assert entity_group["required"][-1] == "entity_15"


def test_provider_batch_schema_requires_exactly_ten_A_interventions():
    root = authorized_response_schema("AExperimentBatch")
    experiments = root["properties"]["experiments"]
    assert experiments["minItems"] == 10
    assert experiments["maxItems"] == 10
    intervention = experiments["items"]
    assert intervention["properties"]["paradigm"] == {"enum": ["A"], "type": "string"}
    assert intervention["properties"]["action_value"] == {"type": "integer", "minimum": 0, "maximum": 7}
    assert len(intervention["properties"]["entity_id"]["enum"]) == 16


def test_provider_projection_contains_only_preregistered_supported_subset_keywords():
    forbidden = {"$ref", "$defs", "oneOf", "const", "pattern", "uniqueItems"}
    for schema_name in ("CandidatePartitionSet", "AExperimentBatch", "ACommitDecision"):
        root = authorized_response_schema(schema_name)
        for node in _walk(root):
            if isinstance(node, dict):
                assert forbidden.isdisjoint(node.keys()), (schema_name, node)


def test_commit_projection_uses_anyof_but_trusted_validation_remains_normative():
    root = authorized_response_schema("ACommitDecision")
    assert root["properties"]["decision"] == {
        "enum": ["commit", "abstain"],
        "type": "string",
    }
    branches = root["properties"]["partition"]["anyOf"]
    assert len(branches) == 2
    assert branches[0]["properties"]["group_count"]["maximum"] == 4
    assert branches[1] == {"type": ["null"]}


def test_schedule_digest_manifest_matches_current_production_code():
    from scripts.v1_schedule_digest import fixture_manifest

    expected = json.loads(Path("V1_SCHEDULE_DIGEST_MANIFEST.json").read_text(encoding="utf-8"))
    assert fixture_manifest() == expected
