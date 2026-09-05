from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from archimedes_v0.v1_protocol import AExperimentBatch
from archimedes_v0.v1_v11_critic import (
    V11Critic,
    V11RawAExperimentBatch,
    canonical_qualification_experiment_id,
    inject_qualification_experiment_ids,
    v11_critic_provider_schema,
)


def _rows(*, offset: int = 0):
    return [
        {
            "objective": "discriminate" if i % 2 == 0 else "estimate",
            "paradigm": "A",
            "entity_id": f"entity_{(i + offset) % 16:02d}",
            "action_value": (i + offset) % 8,
            "target_hypothesis_ids": [f"H-{i % 4}"],
        }
        for i in range(10)
    ]


def _raw(*, offset: int = 0) -> V11RawAExperimentBatch:
    return V11RawAExperimentBatch.model_validate({"experiments": _rows(offset=offset)})


def _semantic_tuples(rows):
    return [
        (
            row["objective"],
            row["paradigm"],
            row["entity_id"],
            row["action_value"],
            row["target_hypothesis_ids"],
        )
        for row in rows
    ]


# A. ID determinism.
def test_v11_id_determinism_and_exact_format():
    expected = [f"E-CQ2-{i:02d}" for i in range(1, 11)]
    assert [canonical_qualification_experiment_id(1, i) for i in range(10)] == expected
    assert [canonical_qualification_experiment_id(1, i) for i in range(10)] == expected


# B. ID independence from scientifically meaningful content.
def test_v11_ids_are_independent_of_semantic_content():
    a = inject_qualification_experiment_ids(_raw(offset=0), round_index=2)
    b = inject_qualification_experiment_ids(_raw(offset=5), round_index=2)
    assert [x.experiment_id for x in a.experiments] == [x.experiment_id for x in b.experiments]


# C. Semantic preservation.
def test_v11_injection_preserves_every_meaningful_field_byte_for_byte():
    raw = _raw()
    before = _semantic_tuples([row.model_dump(mode="json") for row in raw.experiments])
    full = inject_qualification_experiment_ids(raw, round_index=0)
    after = _semantic_tuples([row.model_dump(mode="json") for row in full.experiments])
    assert before == after


# D. No repair beyond IDs.
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("objective", "invent"),
        ("paradigm", "B"),
        ("entity_id", "entity_99"),
        ("action_value", 8),
        ("target_hypothesis_ids", ["H-X", "H-X"]),
    ],
)
def test_v11_malformed_meaningful_fields_remain_invalid(field, value):
    rows = _rows()
    rows[0][field] = value
    with pytest.raises(ValidationError):
        V11RawAExperimentBatch.model_validate({"experiments": rows})


def test_v11_model_cannot_supply_or_smuggle_experiment_id():
    rows = _rows()
    rows[0]["experiment_id"] = "E-MODEL-TRY"
    with pytest.raises(ValidationError):
        V11RawAExperimentBatch.model_validate({"experiments": rows})


# E. No reordering.
def test_v11_injection_preserves_provider_array_order():
    raw = _raw(offset=3)
    full = inject_qualification_experiment_ids(raw, round_index=0)
    assert [x.entity_id for x in full.experiments] == [x.entity_id for x in raw.experiments]
    assert [x.action_value for x in full.experiments] == [x.action_value for x in raw.experiments]


# F. No target/world access by the canonicalizer module.
def test_v11_canonicalizer_has_no_fixture_or_world_dependency():
    text = Path("archimedes_v0/v1_v11_critic.py").read_text(encoding="utf-8")
    forbidden = (
        "V1_CRITIC_QUALIFICATION_FIXTURES.json",
        "trusted_expected_revealing_intervention",
        "archimedes_v0.generator",
        "archimedes_v0.world",
        "latent_q_by_entity",
        "program_a",
        "program_b",
    )
    assert all(token not in text for token in forbidden)


# G. Provider schema excludes ID and forbids undeclared fields.
def test_v11_provider_schema_omits_id_and_forbids_extra_properties():
    schema = v11_critic_provider_schema()
    experiments = schema["properties"]["experiments"]
    assert experiments["minItems"] == 10
    assert experiments["maxItems"] == 10
    item = experiments["items"]
    assert item["additionalProperties"] is False
    assert "experiment_id" not in item["properties"]
    assert "experiment_id" not in item.get("required", [])
    assert {"objective", "paradigm", "entity_id", "action_value", "target_hypothesis_ids"} <= set(item["properties"])


# H. Full downstream normative compatibility.
def test_v11_injected_batch_validates_existing_normative_contract():
    full = inject_qualification_experiment_ids(_raw(), round_index=2)
    reparsed = AExperimentBatch.model_validate(full.model_dump(mode="json"))
    ids = [x.experiment_id for x in reparsed.experiments]
    assert ids == [f"E-CQ3-{i:02d}" for i in range(1, 11)]
    assert len(ids) == len(set(ids)) == 10


class FakeBackend:
    def __init__(self, payload):
        self.payload = payload
        self.schema = None

    def invoke(self, *, role, system_prompt, payload, response_schema, max_output_tokens):
        self.schema = response_schema
        return self.payload


def test_v11_critic_end_to_end_assigns_ids_after_provider_output():
    backend = FakeBackend({"experiments": _rows(offset=4)})
    critic = V11Critic(backend, "critic")
    batch = critic.select({"round_index": 1})
    assert [x.experiment_id for x in batch.experiments] == [f"E-CQ2-{i:02d}" for i in range(1, 11)]
    item = backend.schema["properties"]["experiments"]["items"]
    assert "experiment_id" not in item["properties"]
