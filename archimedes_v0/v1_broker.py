from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Protocol

from pydantic import ValidationError

from .broker_v013 import HashChainLedger
from .v1_protocol import (
    A_DISCOVERY_BUDGET,
    A_GATE_BUDGET,
    B_CALIBRATION_BUDGET,
    B_TRANSFER_BUDGET,
    TOTAL_BUDGET,
    ACommitDecision,
    AExperimentBatch,
    CanonicalPartition,
    Observation,
    TransferPrediction,
    build_b_calibration_schedule,
    build_b_lookup,
    build_b_transfer_schedule,
    build_transfer_predictions,
    canonical_digest,
    canonicalize_partition,
    construct_a_gate_challenges,
    score_transfer,
)


class V1BrokerError(RuntimeError):
    pass


class RuntimeProtocol(Protocol):
    def observe(self, paradigm: str, entity: str, action: int, repetition: int = 0) -> int:
        ...


class V1Phase(str, Enum):
    A_DISCOVERY = "A_DISCOVERY"
    B_CALIBRATION = "B_CALIBRATION"
    B_TRANSFER = "B_TRANSFER"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class V1Result:
    outcome: str
    world_score: float
    a_gate_accuracy: float | None
    b_correct: int
    b_total: int
    transfer_accuracy: float
    qualifies_090: bool
    partition_digest: str | None
    a_gate_prediction_digest: str | None
    b_calibration_schedule_digest: str | None
    b_transfer_prediction_digest: str | None
    inconsistent_b_cells: int
    spent_budget: int
    unused_budget: int


class V1Broker:
    """Trusted deterministic V1 boundary.

    The model may influence only A discovery interventions and the submitted
    partition. Once the partition passes the sealed empirical A gate, all B
    scheduling, lookup construction, prediction freezing, and scoring are trusted
    deterministic operations.
    """

    def __init__(self, runtime: RuntimeProtocol, *, ledger_path: str | None = None):
        self._runtime = runtime
        self._ledger = HashChainLedger(ledger_path)
        self._phase = V1Phase.A_DISCOVERY
        self._seen_experiment_ids: set[str] = set()
        self._repetitions: dict[tuple[str, str, int], int] = {}
        self._a_observations: list[Observation] = []
        self._a_gate_observations: list[Observation] = []
        self._a_gate_charged = 0
        self._b_calibration_observations: list[Observation] = []
        self._b_transfer_observations: list[Observation] = []
        self._partition: CanonicalPartition | None = None
        self._partition_digest: str | None = None
        self._a_gate_prediction_digest: str | None = None
        self._b_calibration_schedule = ()
        self._b_calibration_schedule_digest: str | None = None
        self._b_transfer_schedule = ()
        self._b_transfer_predictions: tuple[TransferPrediction, ...] = ()
        self._b_transfer_prediction_digest: str | None = None
        self._closed_result: V1Result | None = None
        self._ledger.append(
            "v1_run_opened",
            {
                "budget": {
                    "A_discovery": A_DISCOVERY_BUDGET,
                    "A_gate": A_GATE_BUDGET,
                    "B_calibration": B_CALIBRATION_BUDGET,
                    "B_transfer": B_TRANSFER_BUDGET,
                    "total": TOTAL_BUDGET,
                }
            },
        )

    @property
    def phase(self) -> V1Phase:
        return self._phase

    @property
    def visible_a_observations(self) -> tuple[dict[str, Any], ...]:
        return tuple(asdict(observation) for observation in self._a_observations)

    @property
    def partition(self) -> CanonicalPartition | None:
        return self._partition

    @property
    def ledger(self) -> tuple[dict[str, Any], ...]:
        return self._ledger.snapshot()

    @property
    def result(self) -> V1Result | None:
        return self._closed_result

    @property
    def spent_budget(self) -> int:
        return (
            len(self._a_observations)
            + self._a_gate_charged
            + len(self._b_calibration_observations)
            + len(self._b_transfer_observations)
        )

    def close_external_failure(self, outcome: str = "semantic_output_failure") -> V1Result:
        """Close an arm after an agent-interface failure; no scientific retry."""
        return self._close(outcome, a_gate_accuracy=None)

    def execute_a_batch(self, raw_batch: AExperimentBatch | dict[str, Any]) -> tuple[Observation, ...]:
        if self._phase != V1Phase.A_DISCOVERY:
            raise V1BrokerError("A discovery is closed")
        if len(self._a_observations) >= A_DISCOVERY_BUDGET:
            raise V1BrokerError("A discovery budget exhausted")
        try:
            batch = raw_batch if isinstance(raw_batch, AExperimentBatch) else AExperimentBatch.model_validate(raw_batch)
        except ValidationError as exc:
            self._close("schema_failure", a_gate_accuracy=None)
            raise V1BrokerError("schema-invalid A experiment batch") from exc
        if len(self._a_observations) + len(batch.experiments) > A_DISCOVERY_BUDGET:
            self._close("schedule_failure", a_gate_accuracy=None)
            raise V1BrokerError("A discovery batch exceeds frozen budget")

        rows: list[Observation] = []
        for experiment in batch.experiments:
            if experiment.experiment_id in self._seen_experiment_ids:
                self._close("schedule_failure", a_gate_accuracy=None)
                raise V1BrokerError("experiment_id reused within run")
            self._seen_experiment_ids.add(experiment.experiment_id)
            repetition = self._next_repetition("A", experiment.entity_id, experiment.action_value)
            y = self._runtime.observe("A", experiment.entity_id, experiment.action_value, repetition)
            row = Observation(
                experiment_id=experiment.experiment_id,
                paradigm="A",
                entity_id=experiment.entity_id,
                action_value=experiment.action_value,
                repetition=repetition,
                y=y,
            )
            self._a_observations.append(row)
            rows.append(row)
            self._ledger.append("a_observation", asdict(row))
        return tuple(rows)

    def submit_a_commit(self, raw_decision: ACommitDecision | dict[str, Any]) -> V1Result | None:
        if self._phase != V1Phase.A_DISCOVERY or len(self._a_observations) != A_DISCOVERY_BUDGET:
            raise V1BrokerError("A commit requires exactly 60 discovery observations")

        if isinstance(raw_decision, ACommitDecision):
            shallow_decision = raw_decision.decision
        elif isinstance(raw_decision, dict):
            shallow_decision = raw_decision.get("decision")
        else:
            shallow_decision = None

        # Charge before semantic validation of a stated commit.
        if shallow_decision == "commit":
            self._a_gate_charged = A_GATE_BUDGET
            self._ledger.append("a_gate_budget_charged", {"units": A_GATE_BUDGET}, sealed=True)

        try:
            decision = raw_decision if isinstance(raw_decision, ACommitDecision) else ACommitDecision.model_validate(raw_decision)
        except (ValidationError, AttributeError, TypeError):
            return self._close("invalid_commit", a_gate_accuracy=None)

        if decision.decision == "abstain":
            return self._close("abstain", a_gate_accuracy=None)
        assert decision.partition is not None
        if self._a_gate_charged != A_GATE_BUDGET:
            raise AssertionError("commit reached A gate without prepaid four-unit charge")

        self._partition = canonicalize_partition(decision.partition)
        self._partition_digest = self._partition.digest()
        self._ledger.append(
            "a_partition_frozen",
            {
                "partition": json.loads(self._partition.canonical_json()),
                "partition_digest": self._partition_digest,
            },
            sealed=True,
        )

        challenges = construct_a_gate_challenges(self._partition, self._a_observations)
        if len(challenges) != A_GATE_BUDGET:
            return self._close("a_gate_insufficient_coverage", a_gate_accuracy=0.0)

        self._a_gate_prediction_digest = canonical_digest(challenges)
        self._ledger.append(
            "a_gate_predictions_frozen",
            {
                "prediction_digest": self._a_gate_prediction_digest,
                "challenges": [asdict(challenge) for challenge in challenges],
            },
            sealed=True,
        )

        correct = 0
        for challenge in challenges:
            repetition = self._next_repetition("A", challenge.entity_id, challenge.action_value)
            y = self._runtime.observe("A", challenge.entity_id, challenge.action_value, repetition)
            observation = Observation(
                experiment_id=f"A-GATE-{challenge.slot}",
                paradigm="A",
                entity_id=challenge.entity_id,
                action_value=challenge.action_value,
                repetition=repetition,
                y=y,
            )
            self._a_gate_observations.append(observation)
            correct += int(y == challenge.predicted_y)
            self._ledger.append("a_gate_outcome", asdict(observation), sealed=True)

        accuracy = correct / A_GATE_BUDGET
        self._ledger.append("a_gate_adjudicated", {"correct": correct, "total": A_GATE_BUDGET, "accuracy": accuracy}, sealed=True)
        if correct != A_GATE_BUDGET:
            return self._close("a_gate_failure", a_gate_accuracy=accuracy)

        self._b_calibration_schedule = build_b_calibration_schedule(self._partition)
        self._b_calibration_schedule_digest = canonical_digest(self._b_calibration_schedule)
        self._ledger.append(
            "b_calibration_schedule_frozen",
            {
                "schedule_digest": self._b_calibration_schedule_digest,
                "schedule": [asdict(slot) for slot in self._b_calibration_schedule],
            },
            sealed=True,
        )
        self._phase = V1Phase.B_CALIBRATION
        return None

    def run_b(self) -> V1Result:
        if self._phase != V1Phase.B_CALIBRATION or self._partition is None:
            raise V1BrokerError("B can run only after a successful A gate")

        calibration_outcomes: list[int] = []
        for slot in self._b_calibration_schedule:
            repetition = self._next_repetition("B", slot.entity_id, slot.action_value)
            y = self._runtime.observe("B", slot.entity_id, slot.action_value, repetition)
            calibration_outcomes.append(y)
            observation = Observation(
                experiment_id=f"B-CAL-{slot.slot}",
                paradigm="B",
                entity_id=slot.entity_id,
                action_value=slot.action_value,
                repetition=repetition,
                y=y,
            )
            self._b_calibration_observations.append(observation)
            self._ledger.append("b_calibration_outcome", asdict(observation), sealed=True)

        lookup = build_b_lookup(
            self._b_calibration_schedule,
            calibration_outcomes,
            group_count=self._partition.group_count,
        )
        inconsistent_count = sum(cell.status == "inconsistent" for cell in lookup.values())
        self._ledger.append(
            "b_lookup_frozen",
            {
                "cells": [asdict(lookup[key]) for key in sorted(lookup)],
                "inconsistent_cells": inconsistent_count,
            },
            sealed=True,
        )

        self._b_transfer_schedule = build_b_transfer_schedule(self._partition, self._b_calibration_schedule)
        self._b_transfer_predictions = build_transfer_predictions(self._b_transfer_schedule, lookup)
        self._b_transfer_prediction_digest = canonical_digest(self._b_transfer_predictions)
        self._ledger.append(
            "b_transfer_predictions_frozen",
            {
                "prediction_digest": self._b_transfer_prediction_digest,
                "predictions": [asdict(prediction) for prediction in self._b_transfer_predictions],
            },
            sealed=True,
        )
        self._phase = V1Phase.B_TRANSFER

        transfer_outcomes: list[int] = []
        for slot in self._b_transfer_schedule:
            repetition = self._next_repetition("B", slot.entity_id, slot.action_value)
            y = self._runtime.observe("B", slot.entity_id, slot.action_value, repetition)
            transfer_outcomes.append(y)
            observation = Observation(
                experiment_id=f"B-TRANSFER-{slot.slot}",
                paradigm="B",
                entity_id=slot.entity_id,
                action_value=slot.action_value,
                repetition=repetition,
                y=y,
            )
            self._b_transfer_observations.append(observation)
            self._ledger.append("b_transfer_outcome", asdict(observation), sealed=True)

        correct, total, _ = score_transfer(self._b_transfer_predictions, transfer_outcomes)
        return self._close(
            "completed",
            a_gate_accuracy=1.0,
            b_correct=correct,
            b_total=total,
            inconsistent_b_cells=inconsistent_count,
        )

    def _next_repetition(self, paradigm: str, entity: str, action: int) -> int:
        key = (paradigm, entity, action)
        repetition = self._repetitions.get(key, 0)
        self._repetitions[key] = repetition + 1
        return repetition

    def _close(
        self,
        outcome: str,
        *,
        a_gate_accuracy: float | None,
        b_correct: int = 0,
        b_total: int = 0,
        inconsistent_b_cells: int = 0,
    ) -> V1Result:
        if self._closed_result is not None:
            return self._closed_result
        transfer_accuracy = b_correct / b_total if b_total else 0.0
        world_score = transfer_accuracy if outcome == "completed" else 0.0
        result = V1Result(
            outcome=outcome,
            world_score=world_score,
            a_gate_accuracy=a_gate_accuracy,
            b_correct=b_correct,
            b_total=b_total,
            transfer_accuracy=transfer_accuracy,
            qualifies_090=bool(outcome == "completed" and transfer_accuracy >= 0.90),
            partition_digest=self._partition_digest,
            a_gate_prediction_digest=self._a_gate_prediction_digest,
            b_calibration_schedule_digest=self._b_calibration_schedule_digest,
            b_transfer_prediction_digest=self._b_transfer_prediction_digest,
            inconsistent_b_cells=inconsistent_b_cells,
            spent_budget=self.spent_budget,
            unused_budget=TOTAL_BUDGET - self.spent_budget,
        )
        self._closed_result = result
        self._phase = V1Phase.CLOSED
        self._ledger.append("v1_run_closed", asdict(result), sealed=True)
        return result
