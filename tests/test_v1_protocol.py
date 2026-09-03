from __future__ import annotations

import itertools

import pytest
from pydantic import ValidationError

from archimedes_v0.v1_protocol import (
    ACTIONS,
    ENTITIES,
    B_CALIBRATION_BUDGET,
    B_TRANSFER_BUDGET,
    CanonicalPartition,
    PartitionHypothesis,
    ScheduleSlot,
    build_b_calibration_schedule,
    build_b_lookup,
    build_b_transfer_schedule,
    build_transfer_predictions,
    canonical_digest,
    canonicalize_partition,
    score_transfer,
)


def _compositions(total: int, parts: int, minimum: int = 2):
    if parts == 1:
        if total >= minimum:
            yield (total,)
        return
    for first in range(minimum, total - minimum * (parts - 1) + 1):
        for rest in _compositions(total - first, parts - 1, minimum):
            yield (first,) + rest


def _partition_from_sizes(sizes: tuple[int, ...]) -> PartitionHypothesis:
    assignments = {}
    cursor = 0
    for group, size in enumerate(sizes):
        for entity in ENTITIES[cursor : cursor + size]:
            assignments[entity] = group
        cursor += size
    return PartitionHypothesis(hypothesis_id="H-fixture", group_count=len(sizes), entity_group=assignments)


def _reference_calibration(partition: CanonicalPartition):
    cells = [(q, a) for q in range(partition.group_count) for a in ACTIONS]
    rows = []
    for q, a in cells:
        rows.append((partition.members(q)[0], a, q))
    r = 1
    while len(rows) < 32:
        for q, a in cells:
            members = partition.members(q)
            if r < len(members) - 1:
                rows.append((members[r], a, q))
                if len(rows) == 32:
                    return rows
        r += 1
    return rows


def _reference_transfer(partition: CanonicalPartition, calibration):
    calibrated = {(row.entity_id, row.action_value) for row in calibration}
    cells = [(q, a) for q in range(partition.group_count) for a in ACTIONS]
    remaining = {
        (q, a): [entity for entity in partition.members(q) if (entity, a) not in calibrated]
        for q, a in cells
    }
    rows = []
    r = 0
    while len(rows) < 32:
        for q, a in cells:
            if r < len(remaining[(q, a)]):
                rows.append((remaining[(q, a)][r], a, q))
                if len(rows) == 32:
                    return rows
        r += 1
    return rows


def test_exhaustive_legal_group_size_shapes_match_reference_oracle():
    for k in (2, 3, 4):
        for sizes in _compositions(16, k):
            partition = canonicalize_partition(_partition_from_sizes(sizes))
            calibration = build_b_calibration_schedule(partition)
            transfer = build_b_transfer_schedule(partition, calibration)

            assert len(calibration) == B_CALIBRATION_BUDGET
            assert len(transfer) == B_TRANSFER_BUDGET
            cal_pairs = {(row.entity_id, row.action_value) for row in calibration}
            transfer_pairs = {(row.entity_id, row.action_value) for row in transfer}
            assert len(cal_pairs) == 32
            assert len(transfer_pairs) == 32
            assert cal_pairs.isdisjoint(transfer_pairs)

            first_pass = calibration[: 8 * k]
            assert {(row.canonical_group, row.action_value) for row in first_pass} == {
                (q, a) for q in range(k) for a in ACTIONS
            }
            for q in range(k):
                for a in ACTIONS:
                    assert any((entity, a) not in cal_pairs for entity in partition.members(q))

            assert [(r.entity_id, r.action_value, r.canonical_group) for r in calibration] == _reference_calibration(partition)
            assert [(r.entity_id, r.action_value, r.canonical_group) for r in transfer] == _reference_transfer(partition, calibration)


def test_cosmetic_label_permutations_canonicalize_identically():
    base = _partition_from_sizes((4, 4, 4, 4))
    expected = canonicalize_partition(base)
    expected_cal = canonical_digest(build_b_calibration_schedule(expected))
    expected_transfer = canonical_digest(build_b_transfer_schedule(expected, build_b_calibration_schedule(expected)))

    for permutation in itertools.permutations(range(4)):
        relabeled = {entity: permutation[group] for entity, group in base.entity_group.items()}
        candidate = PartitionHypothesis(hypothesis_id="H-relabel", group_count=4, entity_group=relabeled)
        canonical = canonicalize_partition(candidate)
        calibration = build_b_calibration_schedule(canonical)
        transfer = build_b_transfer_schedule(canonical, calibration)
        assert canonical.canonical_json() == expected.canonical_json()
        assert canonical_digest(calibration) == expected_cal
        assert canonical_digest(transfer) == expected_transfer


def test_mapping_insertion_order_does_not_change_schedule():
    base = _partition_from_sizes((3, 5, 8))
    expected = canonicalize_partition(base)
    expected_digest = canonical_digest(build_b_calibration_schedule(expected))
    for order in (ENTITIES, tuple(reversed(ENTITIES)), ENTITIES[::2] + ENTITIES[1::2]):
        mapping = {entity: base.entity_group[entity] for entity in order}
        candidate = PartitionHypothesis(hypothesis_id="H-order", group_count=3, entity_group=mapping)
        canonical = canonicalize_partition(candidate)
        assert canonical_digest(build_b_calibration_schedule(canonical)) == expected_digest


def test_inconsistent_b_cell_forces_failure_even_with_two_to_one_majority():
    # The production 32-slot schedule never places three calibration observations
    # in one cell, but the lookup primitive itself is frozen against any future
    # accidental majority-vote rescue. This independent synthetic fixture verifies
    # that [3,3,5] is still inconsistent.
    calibration = (
        ScheduleSlot(0, "entity_00", 0, 0),
        ScheduleSlot(1, "entity_01", 0, 0),
        ScheduleSlot(2, "entity_02", 0, 0),
    )
    lookup = build_b_lookup(calibration, (3, 3, 5), group_count=2)
    target_cell = (0, 0)
    assert lookup[target_cell].status == "inconsistent"
    assert lookup[target_cell].predicted_y is None

    transfer = (ScheduleSlot(0, "entity_03", 0, 0),)
    predictions = build_transfer_predictions(transfer, lookup)
    assert predictions[0].forced_failure
    assert predictions[0].predicted_y is None
    correct, total, accuracy = score_transfer(predictions, (3,))
    assert (correct, total, accuracy) == (0, 1, 0.0)


@pytest.mark.parametrize(
    "group_count,mapping",
    [
        (1, {entity: 0 for entity in ENTITIES}),
        (5, {entity: i % 5 for i, entity in enumerate(ENTITIES)}),
        (2, {entity: 0 for entity in ENTITIES}),
        (4, {entity: (0 if i < 1 else 1 + ((i - 1) % 3)) for i, entity in enumerate(ENTITIES)}),
    ],
)
def test_invalid_partition_shapes_are_rejected(group_count, mapping):
    with pytest.raises(ValidationError):
        PartitionHypothesis(hypothesis_id="H-invalid", group_count=group_count, entity_group=mapping)


def test_missing_entity_is_rejected():
    mapping = {entity: i % 2 for i, entity in enumerate(ENTITIES[:-1])}
    with pytest.raises(ValidationError):
        PartitionHypothesis(hypothesis_id="H-missing", group_count=2, entity_group=mapping)
