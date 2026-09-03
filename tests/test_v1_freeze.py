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


def test_provider_partition_schema_is_bound_to_authorized_static_freeze():
    root = authorized_response_schema("CandidatePartitionSet")
    defs = root["$defs"]
    partition = defs["PartitionHypothesis"]
    assert partition["properties"]["group_count"] == {"type": "integer", "minimum": 2, "maximum": 4}
    entity_group = partition["properties"]["entity_group"]
    assert entity_group["additionalProperties"] is False
    assert len(entity_group["required"]) == 16
    assert entity_group["required"][0] == "entity_00"
    assert entity_group["required"][-1] == "entity_15"
    assert root["$ref"] == "#/$defs/CandidatePartitionSet"


def test_provider_batch_schema_requires_exactly_ten_A_interventions():
    root = authorized_response_schema("AExperimentBatch")
    experiments = root["$defs"]["AExperimentBatch"]["properties"]["experiments"]
    assert experiments["minItems"] == 10
    assert experiments["maxItems"] == 10
    intervention = root["$defs"]["AInterventionProposal"]
    assert intervention["properties"]["paradigm"] == {"const": "A"}
    assert intervention["properties"]["action_value"] == {"type": "integer", "minimum": 0, "maximum": 7}


def test_schedule_digest_manifest_matches_current_production_code():
    from scripts.v1_schedule_digest import fixture_manifest

    expected = json.loads(Path("V1_SCHEDULE_DIGEST_MANIFEST.json").read_text(encoding="utf-8"))
    assert fixture_manifest() == expected
