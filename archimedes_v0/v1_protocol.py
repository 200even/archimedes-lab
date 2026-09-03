from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

V1_SCHEMA_VERSION = "1.0"
ENTITIES = tuple(f"entity_{i:02d}" for i in range(16))
ACTIONS = tuple(range(8))
MIN_GROUPS = 2
MAX_GROUPS = 4
MIN_ENTITIES_PER_GROUP = 2
A_DISCOVERY_BUDGET = 60
A_GATE_BUDGET = 4
B_CALIBRATION_BUDGET = 32
B_TRANSFER_BUDGET = 32
TOTAL_BUDGET = 128


class V1ProtocolError(ValueError):
    pass


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PartitionHypothesis(StrictModel):
    schema_version: Literal[V1_SCHEMA_VERSION] = V1_SCHEMA_VERSION
    hypothesis_id: str = Field(pattern=r"^H-[A-Za-z0-9_-]{1,48}$")
    group_count: int = Field(ge=MIN_GROUPS, le=MAX_GROUPS)
    entity_group: dict[str, int]

    @model_validator(mode="after")
    def validate_partition(self):
        if set(self.entity_group) != set(ENTITIES):
            raise ValueError("partition must assign every public entity exactly once")
        if any(type(v) is not int or not 0 <= v < self.group_count for v in self.entity_group.values()):
            raise ValueError("partition assignment outside declared group_count")
        used = set(self.entity_group.values())
        if used != set(range(self.group_count)):
            raise ValueError("all and only labels 0..group_count-1 must be used")
        counts = Counter(self.entity_group.values())
        if any(counts[q] < MIN_ENTITIES_PER_GROUP for q in range(self.group_count)):
            raise ValueError("every group must contain at least two entities")
        return self


class CandidatePartitionSet(StrictModel):
    candidates: list[PartitionHypothesis] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [candidate.hypothesis_id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("hypothesis_id values must be unique")
        return self


class AInterventionProposal(StrictModel):
    experiment_id: str = Field(pattern=r"^E-[A-Za-z0-9_-]{1,48}$")
    objective: Literal["discriminate", "estimate"]
    paradigm: Literal["A"] = "A"
    entity_id: str
    action_value: int = Field(ge=0, le=7)
    target_hypothesis_ids: list[str] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def legal_entity(self):
        if self.entity_id not in ENTITIES:
            raise ValueError("unknown entity_id")
        if len(self.target_hypothesis_ids) != len(set(self.target_hypothesis_ids)):
            raise ValueError("target_hypothesis_ids must be unique")
        return self


class AExperimentBatch(StrictModel):
    experiments: list[AInterventionProposal] = Field(min_length=10, max_length=10)

    @model_validator(mode="after")
    def unique_experiment_ids(self):
        ids = [experiment.experiment_id for experiment in self.experiments]
        if len(ids) != len(set(ids)):
            raise ValueError("experiment_id values must be unique within batch")
        return self


class ACommitDecision(StrictModel):
    decision: Literal["commit", "abstain"]
    partition: PartitionHypothesis | None = None

    @model_validator(mode="after")
    def decision_matches_payload(self):
        if self.decision == "commit" and self.partition is None:
            raise ValueError("commit requires partition")
        if self.decision == "abstain" and self.partition is not None:
            raise ValueError("abstain requires partition=null")
        return self


@dataclass(frozen=True)
class CanonicalPartition:
    group_count: int
    entity_group: dict[str, int]

    def members(self, group: int) -> tuple[str, ...]:
        return tuple(entity for entity in ENTITIES if self.entity_group[entity] == group)

    def canonical_json(self) -> str:
        return json.dumps(
            {"group_count": self.group_count, "entity_group": self.entity_group},
            sort_keys=True,
            separators=(",", ":"),
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


@dataclass(frozen=True)
class Observation:
    experiment_id: str
    paradigm: str
    entity_id: str
    action_value: int
    repetition: int
    y: int


@dataclass(frozen=True)
class ScheduleSlot:
    slot: int
    entity_id: str
    action_value: int
    canonical_group: int


@dataclass(frozen=True)
class AGateChallenge:
    slot: int
    entity_id: str
    action_value: int
    canonical_group: int
    predicted_y: int
    source_cell_support_entities: tuple[str, ...]
    source_cell_support_count: int


@dataclass(frozen=True)
class LookupCell:
    canonical_group: int
    action_value: int
    status: Literal["defined", "inconsistent", "missing"]
    predicted_y: int | None
    support_count: int


@dataclass(frozen=True)
class TransferPrediction:
    slot: int
    entity_id: str
    action_value: int
    canonical_group: int
    cell_status: Literal["defined", "inconsistent", "missing"]
    predicted_y: int | None
    forced_failure: bool


def canonicalize_partition(partition: PartitionHypothesis) -> CanonicalPartition:
    groups: dict[int, list[str]] = defaultdict(list)
    for entity in ENTITIES:
        groups[partition.entity_group[entity]].append(entity)
    ordered_old_labels = sorted(groups, key=lambda label: min(groups[label]))
    relabel = {old: new for new, old in enumerate(ordered_old_labels)}
    canonical = {entity: relabel[partition.entity_group[entity]] for entity in ENTITIES}
    return CanonicalPartition(group_count=partition.group_count, entity_group=canonical)


def canonical_digest(records: Iterable[object]) -> str:
    rows = []
    for record in records:
        if hasattr(record, "__dataclass_fields__"):
            rows.append(asdict(record))
        else:
            rows.append(record)
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def reduce_a_entity_action(observations: Iterable[Observation]) -> dict[tuple[str, int], int]:
    values: dict[tuple[str, int], list[int]] = defaultdict(list)
    for observation in observations:
        if observation.paradigm != "A":
            continue
        values[(observation.entity_id, observation.action_value)].append(observation.y)

    reduced: dict[tuple[str, int], int] = {}
    for pair, ys in values.items():
        counts = Counter(ys)
        maximum = max(counts.values())
        winners = [y for y, count in counts.items() if count == maximum]
        if len(winners) == 1:
            reduced[pair] = winners[0]
    return reduced


def build_a_empirical_cells(
    partition: CanonicalPartition,
    observations: Iterable[Observation],
) -> dict[tuple[int, int], tuple[int, tuple[str, ...]]]:
    reduced = reduce_a_entity_action(observations)
    cells: dict[tuple[int, int], tuple[int, tuple[str, ...]]] = {}
    for group in range(partition.group_count):
        members = partition.members(group)
        for action in ACTIONS:
            supported = [(entity, reduced[(entity, action)]) for entity in members if (entity, action) in reduced]
            if len(supported) < 2:
                continue
            counts = Counter(value for _, value in supported)
            value, count = min(counts.items(), key=lambda item: (-item[1], item[0]))
            if count * 2 <= len(supported):
                continue
            support_entities = tuple(entity for entity, _ in supported)
            cells[(group, action)] = (value, support_entities)
    return cells


def construct_a_gate_challenges(
    partition: CanonicalPartition,
    discovery_observations: Iterable[Observation],
) -> tuple[AGateChallenge, ...]:
    observations = tuple(discovery_observations)
    seen_pairs = {(o.entity_id, o.action_value) for o in observations if o.paradigm == "A"}
    cells = build_a_empirical_cells(partition, observations)
    challenges: list[AGateChallenge] = []

    for group in range(partition.group_count):
        for action in ACTIONS:
            cell = cells.get((group, action))
            if cell is None:
                continue
            prediction, support_entities = cell
            candidates = [entity for entity in partition.members(group) if (entity, action) not in seen_pairs]
            if not candidates:
                continue
            entity = candidates[0]
            # Because (entity, action) is unobserved, all cell support necessarily
            # comes from different entities. Keep this assertion as a hard firewall.
            if entity in support_entities:
                raise AssertionError("A gate support leaked held-out entity/action")
            challenges.append(
                AGateChallenge(
                    slot=len(challenges),
                    entity_id=entity,
                    action_value=action,
                    canonical_group=group,
                    predicted_y=prediction,
                    source_cell_support_entities=support_entities,
                    source_cell_support_count=len(support_entities),
                )
            )
            if len(challenges) == A_GATE_BUDGET:
                return tuple(challenges)
    return tuple(challenges)


def build_b_calibration_schedule(partition: CanonicalPartition) -> tuple[ScheduleSlot, ...]:
    cells = [(group, action) for group in range(partition.group_count) for action in ACTIONS]
    selected: list[ScheduleSlot] = []

    # Pass 0: one observation for every inferred cell.
    for group, action in cells:
        entity = partition.members(group)[0]
        selected.append(ScheduleSlot(len(selected), entity, action, group))

    # Additional passes leave the final member in every cell uncalibrated.
    member_index = 1
    while len(selected) < B_CALIBRATION_BUDGET:
        added = False
        for group, action in cells:
            members = partition.members(group)
            if member_index < len(members) - 1:
                selected.append(ScheduleSlot(len(selected), members[member_index], action, group))
                added = True
                if len(selected) == B_CALIBRATION_BUDGET:
                    break
        if not added:
            raise V1ProtocolError("legal partition cannot fill frozen B calibration budget")
        member_index += 1

    _validate_schedule(selected, partition, B_CALIBRATION_BUDGET)
    return tuple(selected)


def build_b_transfer_schedule(
    partition: CanonicalPartition,
    calibration_schedule: Iterable[ScheduleSlot],
) -> tuple[ScheduleSlot, ...]:
    calibration_pairs = {(slot.entity_id, slot.action_value) for slot in calibration_schedule}
    cells = [(group, action) for group in range(partition.group_count) for action in ACTIONS]
    remaining: dict[tuple[int, int], tuple[str, ...]] = {}
    for group, action in cells:
        remaining[(group, action)] = tuple(
            entity for entity in partition.members(group) if (entity, action) not in calibration_pairs
        )
        if not remaining[(group, action)]:
            raise V1ProtocolError("calibration consumed every member of a transfer cell")

    selected: list[ScheduleSlot] = []
    member_index = 0
    while len(selected) < B_TRANSFER_BUDGET:
        added = False
        for group, action in cells:
            members = remaining[(group, action)]
            if member_index < len(members):
                selected.append(ScheduleSlot(len(selected), members[member_index], action, group))
                added = True
                if len(selected) == B_TRANSFER_BUDGET:
                    break
        if not added:
            raise V1ProtocolError("legal partition cannot fill frozen B transfer budget")
        member_index += 1

    _validate_schedule(selected, partition, B_TRANSFER_BUDGET)
    transfer_pairs = {(slot.entity_id, slot.action_value) for slot in selected}
    if transfer_pairs & calibration_pairs:
        raise AssertionError("B calibration/transfer pair overlap")
    return tuple(selected)


def _validate_schedule(slots: Iterable[ScheduleSlot], partition: CanonicalPartition, expected: int) -> None:
    slots = tuple(slots)
    if len(slots) != expected:
        raise AssertionError("schedule length mismatch")
    pairs = [(slot.entity_id, slot.action_value) for slot in slots]
    if len(pairs) != len(set(pairs)):
        raise AssertionError("duplicate entity/action pair in schedule")
    for expected_slot, slot in enumerate(slots):
        if slot.slot != expected_slot:
            raise AssertionError("noncanonical slot numbering")
        if slot.entity_id not in ENTITIES or slot.action_value not in ACTIONS:
            raise AssertionError("illegal public intervention")
        if partition.entity_group[slot.entity_id] != slot.canonical_group:
            raise AssertionError("schedule cell does not match partition")


def build_b_lookup(
    calibration_schedule: Iterable[ScheduleSlot],
    outcomes: Iterable[int],
    *,
    group_count: int,
) -> dict[tuple[int, int], LookupCell]:
    slots = tuple(calibration_schedule)
    ys = tuple(outcomes)
    if len(slots) != len(ys):
        raise V1ProtocolError("calibration schedule/outcome length mismatch")
    values: dict[tuple[int, int], list[int]] = defaultdict(list)
    for slot, y in zip(slots, ys, strict=True):
        if y not in ACTIONS:
            raise V1ProtocolError("B outcome outside public domain")
        values[(slot.canonical_group, slot.action_value)].append(y)

    lookup: dict[tuple[int, int], LookupCell] = {}
    for group in range(group_count):
        for action in ACTIONS:
            cell_values = values.get((group, action), [])
            if not cell_values:
                lookup[(group, action)] = LookupCell(group, action, "missing", None, 0)
            elif len(set(cell_values)) == 1:
                lookup[(group, action)] = LookupCell(group, action, "defined", cell_values[0], len(cell_values))
            else:
                lookup[(group, action)] = LookupCell(group, action, "inconsistent", None, len(cell_values))
    return lookup


def build_transfer_predictions(
    transfer_schedule: Iterable[ScheduleSlot],
    lookup: dict[tuple[int, int], LookupCell],
) -> tuple[TransferPrediction, ...]:
    predictions = []
    for slot in transfer_schedule:
        cell = lookup.get((slot.canonical_group, slot.action_value))
        if cell is None:
            cell = LookupCell(slot.canonical_group, slot.action_value, "missing", None, 0)
        predictions.append(
            TransferPrediction(
                slot=slot.slot,
                entity_id=slot.entity_id,
                action_value=slot.action_value,
                canonical_group=slot.canonical_group,
                cell_status=cell.status,
                predicted_y=cell.predicted_y if cell.status == "defined" else None,
                forced_failure=cell.status != "defined",
            )
        )
    return tuple(predictions)


def score_transfer(predictions: Iterable[TransferPrediction], outcomes: Iterable[int]) -> tuple[int, int, float]:
    predictions = tuple(predictions)
    outcomes = tuple(outcomes)
    if len(predictions) != len(outcomes):
        raise V1ProtocolError("transfer prediction/outcome length mismatch")
    correct = sum(
        1
        for prediction, outcome in zip(predictions, outcomes, strict=True)
        if not prediction.forced_failure and prediction.predicted_y == outcome
    )
    total = len(predictions)
    return correct, total, correct / total if total else 0.0
