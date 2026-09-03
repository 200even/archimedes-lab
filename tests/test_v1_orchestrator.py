from __future__ import annotations

import pytest

from archimedes_v0.v1_agent_interfaces import V1Conjecturer, V1Critic, V1FlatAgent
from archimedes_v0.v1_broker import V1Broker
from archimedes_v0.v1_orchestrator import (
    FLAT_MAX_CALLS,
    FLAT_MAX_OUTPUT_TOKENS,
    FULL_MAX_CALLS,
    FULL_MAX_OUTPUT_TOKENS,
    V1FlatOrchestrator,
    V1FullOrchestrator,
)
from archimedes_v0.v1_protocol import ENTITIES


TRUE_MAPPING = {entity: i // 4 for i, entity in enumerate(ENTITIES)}


def _pairs():
    pairs = []
    for action in range(4):
        pairs.extend([("entity_00", action), ("entity_01", action)])
    while len(pairs) < 60:
        pairs.append(("entity_00", 7))
    return pairs


class Runtime:
    def __init__(self):
        self.q = TRUE_MAPPING

    def observe(self, paradigm, entity, action, repetition=0):
        q = self.q[entity]
        return (q + action) % 8 if paradigm == "A" else (2 * q + action) % 8


class ScriptedBackend:
    def __init__(self):
        self.calls = []
        self.pairs = _pairs()

    def invoke(self, *, role, system_prompt, payload, response_schema, max_output_tokens):
        self.calls.append((role, payload["task"], max_output_tokens))
        task = payload["task"]
        if task == "generate_partitions":
            return {
                "candidates": [
                    {
                        "schema_version": "1.0",
                        "hypothesis_id": "H-scripted",
                        "group_count": 4,
                        "entity_group": TRUE_MAPPING,
                    }
                ]
            }
        if task == "select_A_interventions":
            r = payload["round_index"]
            rows = []
            for offset, (entity, action) in enumerate(self.pairs[r * 10 : (r + 1) * 10]):
                rows.append(
                    {
                        "experiment_id": f"E-{r}-{offset}",
                        "objective": "discriminate",
                        "paradigm": "A",
                        "entity_id": entity,
                        "action_value": action,
                        "target_hypothesis_ids": ["H-scripted"],
                    }
                )
            return {"experiments": rows}
        if task == "commit_partition_or_abstain":
            return {
                "decision": "commit",
                "partition": {
                    "schema_version": "1.0",
                    "hypothesis_id": "H-scripted",
                    "group_count": 4,
                    "entity_group": TRUE_MAPPING,
                },
            }
        raise AssertionError(task)


def test_full_and_flat_have_exact_same_prospective_compute_envelope():
    assert FULL_MAX_CALLS == FLAT_MAX_CALLS == 13
    assert FULL_MAX_OUTPUT_TOKENS == FLAT_MAX_OUTPUT_TOKENS == 40_960


def test_full_synthetic_pipeline_uses_exact_7_conjecturer_6_critic_calls():
    backend = ScriptedBackend()
    broker = V1Broker(Runtime())
    orchestrator = V1FullOrchestrator(
        broker,
        V1Conjecturer(backend, "conjecturer"),
        V1Critic(backend, "critic"),
    )
    result = orchestrator.run(execution_authorized=True)
    assert result.world_score == 1.0
    assert len(backend.calls) == 13
    assert sum(role == "conjecturer" for role, _, _ in backend.calls) == 7
    assert sum(role == "critic" for role, _, _ in backend.calls) == 6
    assert all(task in {"generate_partitions", "select_A_interventions", "commit_partition_or_abstain"} for _, task, _ in backend.calls)
    assert sum(tokens for _, _, tokens in backend.calls) == 40_960


def test_flat_synthetic_pipeline_uses_exact_13_same_role_calls():
    backend = ScriptedBackend()
    broker = V1Broker(Runtime())
    orchestrator = V1FlatOrchestrator(broker, V1FlatAgent(backend, "flat"))
    result = orchestrator.run(execution_authorized=True)
    assert result.world_score == 1.0
    assert len(backend.calls) == 13
    assert {role for role, _, _ in backend.calls} == {"flat"}
    assert sum(tokens for _, _, tokens in backend.calls) == 40_960


def test_execution_guard_is_locked_by_default():
    backend = ScriptedBackend()
    broker = V1Broker(Runtime())
    orchestrator = V1FlatOrchestrator(broker, V1FlatAgent(backend, "flat"))
    with pytest.raises(RuntimeError, match="execution guard is locked"):
        orchestrator.run()
    assert backend.calls == []
