from __future__ import annotations

from pathlib import Path

import pytest

from archimedes_v0.v1_agent_interfaces import V1AgentInterfaceError
from archimedes_v0.v1_v11_benchmark_agents import (
    V11BenchmarkSelector,
    canonical_benchmark_experiment_id,
    inject_benchmark_experiment_ids,
)
from archimedes_v0.v1_v11_critic import V11RawAExperimentBatch


def _rows(offset: int = 0):
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


class FakeBackend:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return self.output


def test_benchmark_ids_exact_and_deterministic():
    assert [canonical_benchmark_experiment_id(0, i) for i in range(10)] == [
        f"E-R01-{i:02d}" for i in range(1, 11)
    ]
    assert canonical_benchmark_experiment_id(5, 9) == "E-R06-10"


def test_benchmark_ids_independent_of_semantic_content():
    a = V11RawAExperimentBatch.model_validate({"experiments": _rows(0)})
    b = V11RawAExperimentBatch.model_validate({"experiments": _rows(5)})
    ia = inject_benchmark_experiment_ids(a, round_index=3)
    ib = inject_benchmark_experiment_ids(b, round_index=3)
    assert [x.experiment_id for x in ia.experiments] == [x.experiment_id for x in ib.experiments]


def test_full_and_flat_selectors_receive_same_provider_schema_shape():
    output = {"experiments": _rows()}
    critic_backend = FakeBackend(output)
    flat_backend = FakeBackend(output)
    critic = V11BenchmarkSelector(critic_backend, "critic", role="critic")
    flat = V11BenchmarkSelector(flat_backend, "flat", role="flat")
    c = critic.select({"round_index": 2})
    f = flat.select({"round_index": 2})
    assert c.model_dump(mode="json") == f.model_dump(mode="json")
    cs = critic_backend.calls[0]["response_schema"]
    fs = flat_backend.calls[0]["response_schema"]
    assert cs == fs
    item = cs["properties"]["experiments"]["items"]
    assert item["additionalProperties"] is False
    assert "experiment_id" not in item["properties"]


def test_semantic_invalidity_is_not_repaired():
    rows = _rows()
    rows[0]["entity_id"] = "entity_99"
    backend = FakeBackend({"experiments": rows})
    selector = V11BenchmarkSelector(backend, "critic", role="critic")
    with pytest.raises(V1AgentInterfaceError):
        selector.select({"round_index": 0})


def test_selector_has_no_world_or_target_dependency():
    text = Path("archimedes_v0/v1_v11_benchmark_agents.py").read_text(encoding="utf-8")
    forbidden = (
        "V1_CRITIC_QUALIFICATION_FIXTURES.json",
        "trusted_expected_revealing_intervention",
        "HiddenWorldRuntime",
        "latent_q_by_entity",
        "program_a",
        "program_b",
        "world_kind",
        "null_world",
    )
    assert all(token not in text for token in forbidden)
