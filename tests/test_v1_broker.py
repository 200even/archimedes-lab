from __future__ import annotations

from pathlib import Path

from archimedes_v0.v1_broker import V1Broker, V1Phase
from archimedes_v0.v1_protocol import (
    ENTITIES,
    ACommitDecision,
    AExperimentBatch,
    AInterventionProposal,
    PartitionHypothesis,
)


def _true_partition() -> PartitionHypothesis:
    return PartitionHypothesis(
        hypothesis_id="H-true",
        group_count=4,
        entity_group={entity: i // 4 for i, entity in enumerate(ENTITIES)},
    )


class DeterministicRuntime:
    def __init__(self):
        self.q = {entity: i // 4 for i, entity in enumerate(ENTITIES)}
        self.calls = []
        self.broker = None

    def observe(self, paradigm: str, entity: str, action: int, repetition: int = 0) -> int:
        if paradigm == "B" and sum(call[0] == "B" for call in self.calls) >= 32 and self.broker is not None:
            event_types = [record["event_type"] for record in self.broker.ledger]
            assert "b_transfer_predictions_frozen" in event_types
        self.calls.append((paradigm, entity, action, repetition))
        q = self.q[entity]
        return (q + action) % 8 if paradigm == "A" else (2 * q + action) % 8


def _discovery_pairs():
    # Four held-out gate cells: group 0, actions 0..3. entity_00 and entity_01
    # provide cross-entity support; entity_02 remains unseen for those actions.
    pairs = []
    for action in range(4):
        pairs.extend([("entity_00", action), ("entity_01", action)])
    while len(pairs) < 60:
        pairs.append(("entity_00", 7))
    return pairs


def _run_discovery(broker: V1Broker):
    pairs = _discovery_pairs()
    for round_index in range(6):
        experiments = []
        for offset, (entity, action) in enumerate(pairs[round_index * 10 : (round_index + 1) * 10]):
            experiments.append(
                AInterventionProposal(
                    experiment_id=f"E-r{round_index}-{offset}",
                    objective="discriminate",
                    entity_id=entity,
                    action_value=action,
                    target_hypothesis_ids=["H-true"],
                )
            )
        broker.execute_a_batch(AExperimentBatch(experiments=experiments))


def test_complete_synthetic_v1_pipeline_is_budget_exact_and_perfect():
    runtime = DeterministicRuntime()
    broker = V1Broker(runtime)
    runtime.broker = broker
    _run_discovery(broker)
    assert len(broker.visible_a_observations) == 60

    early = broker.submit_a_commit(ACommitDecision(decision="commit", partition=_true_partition()))
    assert early is None
    assert broker.phase == V1Phase.B_CALIBRATION

    result = broker.run_b()
    assert result.outcome == "completed"
    assert result.a_gate_accuracy == 1.0
    assert result.b_correct == 32
    assert result.b_total == 32
    assert result.transfer_accuracy == 1.0
    assert result.world_score == 1.0
    assert result.spent_budget == 128
    assert result.unused_budget == 0
    assert result.partition_digest
    assert result.a_gate_prediction_digest
    assert result.b_calibration_schedule_digest
    assert result.b_transfer_prediction_digest

    event_types = [record["event_type"] for record in broker.ledger]
    prediction_freeze = event_types.index("b_transfer_predictions_frozen")
    first_transfer = event_types.index("b_transfer_outcome")
    assert prediction_freeze < first_transfer


def test_a_gate_predictions_use_other_entities_only():
    runtime = DeterministicRuntime()
    broker = V1Broker(runtime)
    _run_discovery(broker)
    broker.submit_a_commit(ACommitDecision(decision="commit", partition=_true_partition()))
    freeze = next(record for record in broker.ledger if record["event_type"] == "a_gate_predictions_frozen")
    challenges = freeze["payload"]["challenges"]
    assert len(challenges) == 4
    for challenge in challenges:
        assert challenge["source_cell_support_count"] >= 2
        assert challenge["entity_id"] not in challenge["source_cell_support_entities"]
        assert challenge["entity_id"] == "entity_02"


def test_invalid_committed_cardinality_is_charged_then_rejected_without_retry():
    runtime = DeterministicRuntime()
    broker = V1Broker(runtime)
    _run_discovery(broker)
    invalid = {
        "decision": "commit",
        "partition": {
            "schema_version": "1.0",
            "hypothesis_id": "H-invalid",
            "group_count": 5,
            "entity_group": {entity: i % 5 for i, entity in enumerate(ENTITIES)},
        },
    }
    result = broker.submit_a_commit(invalid)
    assert result is not None
    assert result.outcome == "invalid_commit"
    assert result.spent_budget == 64
    assert result.world_score == 0.0
    assert broker.phase == V1Phase.CLOSED


def test_v1_scheduler_source_has_no_forbidden_hidden_world_dependencies():
    source = Path("archimedes_v0/v1_protocol.py").read_text(encoding="utf-8")
    forbidden = (
        "latent_q_by_entity",
        "program_a",
        "program_b",
        "b_calibration_entities",
        "b_transfer_entities",
        "generate_world",
    )
    for token in forbidden:
        assert token not in source
