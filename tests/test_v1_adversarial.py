from __future__ import annotations

from archimedes_v0.v1_broker import V1Broker
from archimedes_v0.v1_protocol import (
    ENTITIES,
    ACommitDecision,
    AExperimentBatch,
    AInterventionProposal,
    Observation,
    PartitionHypothesis,
    build_a_empirical_cells,
    build_b_calibration_schedule,
    build_b_lookup,
    build_b_transfer_schedule,
    canonical_digest,
    canonicalize_partition,
    reduce_a_entity_action,
)


def _partition(k: int) -> PartitionHypothesis:
    if k == 2:
        mapping = {entity: i // 8 for i, entity in enumerate(ENTITIES)}
    elif k == 4:
        mapping = {entity: i // 4 for i, entity in enumerate(ENTITIES)}
    else:
        raise AssertionError(k)
    return PartitionHypothesis(hypothesis_id=f"H-k{k}", group_count=k, entity_group=mapping)


def test_repeated_measurements_of_one_entity_do_not_outvote_distinct_entities():
    partition = canonicalize_partition(_partition(4))
    observations = []
    for repetition in range(10):
        observations.append(Observation(f"e0-{repetition}", "A", "entity_00", 0, repetition, 1))
    observations.append(Observation("e1", "A", "entity_01", 0, 0, 2))
    observations.append(Observation("e2", "A", "entity_02", 0, 0, 2))
    cells = build_a_empirical_cells(partition, observations)
    assert cells[(0, 0)][0] == 2
    assert cells[(0, 0)][1] == ("entity_00", "entity_01", "entity_02")


def test_tied_repetitions_make_entity_action_value_undefined():
    observations = (
        Observation("x0", "A", "entity_00", 0, 0, 1),
        Observation("x1", "A", "entity_00", 0, 1, 2),
        Observation("x2", "A", "entity_01", 0, 0, 1),
    )
    reduced = reduce_a_entity_action(observations)
    assert ("entity_00", 0) not in reduced
    assert reduced[("entity_01", 0)] == 1


def test_B_pair_schedule_is_identical_under_radically_different_outcomes():
    partition = canonicalize_partition(_partition(2))
    calibration = build_b_calibration_schedule(partition)
    transfer_digest = canonical_digest(build_b_transfer_schedule(partition, calibration))
    outcome_sets = (
        [0] * 32,
        [0] * 16 + [1] * 16,  # every two-representative cell is contradictory
        [i % 8 for i in range(16)] + [((i + 3) % 8) for i in range(16)],
        [(i * 5 + 3) % 8 for i in range(16)] + [((i * 5 + 4) % 8) for i in range(16)],
    )
    lookup_statuses = []
    for outcomes in outcome_sets:
        lookup = build_b_lookup(calibration, outcomes, group_count=partition.group_count)
        lookup_statuses.append(tuple(cell.status for _, cell in sorted(lookup.items())))
        # Selection never consumes lookup or outcomes; its digest must not move.
        assert canonical_digest(build_b_transfer_schedule(partition, calibration)) == transfer_digest
    assert len(set(lookup_statuses)) > 1


class K2Runtime:
    def __init__(self, *, gate_miss: bool = False, inconsistent_B: bool = False):
        self.q = {entity: i // 8 for i, entity in enumerate(ENTITIES)}
        self.gate_miss = gate_miss
        self.inconsistent_B = inconsistent_B

    def observe(self, paradigm, entity, action, repetition=0):
        q = self.q[entity]
        if paradigm == "A":
            y = (q + action) % 8
            if self.gate_miss and entity == "entity_02" and action == 0:
                return (y + 1) % 8
            return y
        y = (2 * q + action) % 8
        if self.inconsistent_B and entity == "entity_01" and action == 0:
            return (y + 1) % 8
        return y


def _run_k2_discovery(broker: V1Broker):
    pairs = []
    for action in range(4):
        pairs.extend([("entity_00", action), ("entity_01", action)])
    while len(pairs) < 60:
        pairs.append(("entity_00", 7))
    for round_index in range(6):
        experiments = [
            AInterventionProposal(
                experiment_id=f"E-{round_index}-{offset}",
                objective="discriminate",
                entity_id=entity,
                action_value=action,
                target_hypothesis_ids=["H-k2"],
            )
            for offset, (entity, action) in enumerate(pairs[round_index * 10 : (round_index + 1) * 10])
        ]
        broker.execute_a_batch(AExperimentBatch(experiments=experiments))


def _run_k2(runtime: K2Runtime):
    broker = V1Broker(runtime)
    _run_k2_discovery(broker)
    early = broker.submit_a_commit(ACommitDecision(decision="commit", partition=_partition(2)))
    if early is not None:
        return broker, early
    return broker, broker.run_b()


def test_one_sealed_A_gate_error_closes_world_at_four_of_four_threshold():
    broker, result = _run_k2(K2Runtime(gate_miss=True))
    assert result.outcome == "a_gate_failure"
    assert result.a_gate_accuracy == 0.75
    assert result.world_score == 0.0
    assert result.spent_budget == 64
    assert all(record["event_type"] != "b_calibration_outcome" for record in broker.ledger)


def test_production_B_inconsistency_forces_transfer_loss_without_majority_rescue():
    _, result = _run_k2(K2Runtime(inconsistent_B=True))
    assert result.outcome == "completed"
    assert result.inconsistent_b_cells == 1
    assert result.b_correct < 32
    assert result.transfer_accuracy < 1.0


def test_complete_scientific_digest_replay_is_stable_across_fresh_brokers():
    _, first = _run_k2(K2Runtime())
    _, second = _run_k2(K2Runtime())
    assert first.outcome == second.outcome == "completed"
    assert first.partition_digest == second.partition_digest
    assert first.a_gate_prediction_digest == second.a_gate_prediction_digest
    assert first.b_calibration_schedule_digest == second.b_calibration_schedule_digest
    assert first.b_transfer_prediction_digest == second.b_transfer_prediction_digest
    assert first.b_correct == second.b_correct == 32
    assert first.world_score == second.world_score == 1.0
