from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable

from pydantic import ValidationError

from .ast_schema import ExperimentAST, Intervention, LatentVariable, TheoryAST, TheoryPrediction
from .constants import (
    BROKER_BUDGET_TOTAL,
    BUDGET_A_DISCOVERY,
    BUDGET_A_THEORY_EVAL,
    BUDGET_B_CALIBRATION,
    BUDGET_B_THEORY_EVAL,
    BUDGET_B_TRANSFER_EVAL,
    D4_TRANSFER_ACCURACY_MIN,
    D4_VISIBLE_FIT_ACCURACY_MIN,
    DOMAIN_SIZE,
    MAX_A_THEORY_GATE_ATTEMPTS,
    MAX_B_THEORY_GATE_ATTEMPTS,
    MAX_EPISTEMIC_CYCLES,
    MAX_EXPRESSION_DEPTH,
    NUM_ENTITIES,
    SCHEMA_VERSION,
)
from .smt_isomorphism import IsomorphismResult, programs_are_isomorphic
from .theory_eval import (
    TheoryEvaluationError,
    expression_depth,
    operator_signature,
    predict,
    program_for,
    score_observations,
    validate_program_structure,
)
from .world import HiddenWorldRuntime


class BrokerError(RuntimeError):
    """Raised when an action would violate the frozen V0.1.3 contract."""


class Phase(str, Enum):
    A_DISCOVERY = "A_DISCOVERY"
    A_FROZEN = "A_FROZEN"
    B_CALIBRATION = "B_CALIBRATION"
    B_TRANSFER = "B_TRANSFER"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class Observation:
    experiment_id: str
    paradigm: str
    entity_id: str
    action_value: int
    repetition: int
    y: int


@dataclass(frozen=True)
class TransferChallenge:
    challenge_id: str
    entity_id: str
    action_value: int


@dataclass(frozen=True)
class NoConceptResult:
    outcome: str
    a_interventions: int
    unused_budget: int


@dataclass(frozen=True)
class GateFailureResult:
    outcome: str
    gate: str
    reason: str
    spent_budget: int
    unused_budget: int


@dataclass(frozen=True)
class D4Result:
    theory_id: str
    latent_cardinality: int
    a_fit_accuracy: float
    b_calibration_fit_accuracy: float
    operator_diverse: bool
    smt_nonisomorphic: bool
    correct: int
    total: int
    exact_accuracy: float
    qualifies: bool


class HashChainLedger:
    GENESIS = "0" * 64

    def __init__(self, path: str | Path | None = None):
        self._records: list[dict[str, Any]] = []
        self._path = Path(path) if path is not None else None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            if self._path.exists() and self._path.stat().st_size:
                raise BrokerError("ledger path must be new/empty for a V0 run")

    @staticmethod
    def _canonical(value: Any) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

    def append(self, event_type: str, payload: dict[str, Any], *, sealed: bool = False) -> dict[str, Any]:
        prev_hash = self._records[-1]["record_hash"] if self._records else self.GENESIS
        body = {
            "sequence": len(self._records),
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "sealed": sealed,
            "payload": payload,
            "prev_hash": prev_hash,
        }
        record = {**body, "record_hash": hashlib.sha256(self._canonical(body)).hexdigest()}
        self._records.append(record)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
        return dict(record)

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        return tuple(json.loads(json.dumps(r)) for r in self._records)

    def verify(self) -> bool:
        prev = self.GENESIS
        for expected_sequence, record in enumerate(self._records):
            if record["sequence"] != expected_sequence or record["prev_hash"] != prev:
                return False
            body = {k: record[k] for k in ("sequence", "timestamp_utc", "event_type", "sealed", "payload", "prev_hash")}
            if hashlib.sha256(self._canonical(body)).hexdigest() != record["record_hash"]:
                return False
            prev = record["record_hash"]
        return True


class ExperimentBroker:
    """Trusted V0.1.3 boundary around the hidden runtime.

    Visible-fit evaluation is a one-shot resource-consuming act. A failed A or B
    theory gate closes the world and cannot be retried. The broker object itself is
    trusted-side only and must never be placed into an LLM context.
    """

    def __init__(
        self,
        public_world: dict[str, Any] | Any,
        runtime: HiddenWorldRuntime,
        *,
        b_calibration_entities: Iterable[str],
        b_transfer_entities: Iterable[str],
        ledger_path: str | Path | None = None,
    ):
        self.public = asdict(public_world) if hasattr(public_world, "__dataclass_fields__") else dict(public_world)
        self._runtime = runtime
        self._calibration_entities = frozenset(b_calibration_entities)
        self._transfer_entities = frozenset(b_transfer_entities)
        self._entities = frozenset(self.public["entities"])
        self._legal_actions = frozenset(self.public["legal_action_values"])
        self._validate_boundary_configuration()

        self._phase = Phase.A_DISCOVERY
        self._ledger = HashChainLedger(ledger_path)
        self._seen_experiment_ids: set[str] = set()
        self._repetitions: dict[tuple[str, str, int], int] = {}
        self._visible_observations: list[dict[str, Any]] = []
        self._a_count = 0
        self._b_cal_count = 0
        self._transfer_count = 0
        self._a_gate_attempts = 0
        self._b_gate_attempts = 0
        self._a_gate_spent = 0
        self._b_gate_spent = 0
        self._epistemic_cycles = 0
        self._frozen_theory: TheoryAST | None = None
        self._frozen_latent: LatentVariable | None = None
        self._a_fit_accuracy: float | None = None
        self._b_theory: TheoryAST | None = None
        self._b_fit_accuracy: float | None = None
        self._operator_diverse = False
        self._smt_result: IsomorphismResult | None = None
        self._transfer_challenges: tuple[TransferChallenge, ...] = ()
        self._transfer_outcomes: list[dict[str, Any]] = []
        self._closed_result: D4Result | NoConceptResult | GateFailureResult | None = None

        self._ledger.append(
            "run_opened",
            {
                "schema_version": SCHEMA_VERSION,
                "world_id": self.public["world_id"],
                "world_kind": self.public["world_kind"],
                "budget": {
                    "A_discovery": BUDGET_A_DISCOVERY,
                    "A_theory_eval": BUDGET_A_THEORY_EVAL,
                    "B_calibration": BUDGET_B_CALIBRATION,
                    "B_theory_eval": BUDGET_B_THEORY_EVAL,
                    "B_transfer_eval": BUDGET_B_TRANSFER_EVAL,
                    "total": BROKER_BUDGET_TOTAL,
                },
                "gate_attempt_caps": {
                    "A": MAX_A_THEORY_GATE_ATTEMPTS,
                    "B": MAX_B_THEORY_GATE_ATTEMPTS,
                },
            },
        )

    @classmethod
    def from_generated_world(cls, public_world: Any, hidden_spec: Any, *, ledger_path: str | Path | None = None) -> "ExperimentBroker":
        hidden = asdict(hidden_spec) if hasattr(hidden_spec, "__dataclass_fields__") else dict(hidden_spec)
        return cls(
            public_world,
            HiddenWorldRuntime(hidden),
            b_calibration_entities=hidden["b_calibration_entities"],
            b_transfer_entities=hidden["b_transfer_entities"],
            ledger_path=ledger_path,
        )

    def _validate_boundary_configuration(self) -> None:
        if self.public.get("schema_version") != SCHEMA_VERSION:
            raise BrokerError("public world schema version mismatch")
        if self.public.get("world_kind") != "experimental":
            raise BrokerError("agent-visible world condition must be blinded")
        if len(self._entities) != NUM_ENTITIES:
            raise BrokerError("unexpected entity count")
        if self._calibration_entities | self._transfer_entities != self._entities:
            raise BrokerError("B calibration/transfer sets must partition all entities")
        if self._calibration_entities & self._transfer_entities:
            raise BrokerError("B calibration/transfer sets must be disjoint")
        if len(self._calibration_entities) != NUM_ENTITIES // 2 or len(self._transfer_entities) != NUM_ENTITIES // 2:
            raise BrokerError("B calibration/transfer sets must be balanced")
        if self._legal_actions != frozenset(range(DOMAIN_SIZE)):
            raise BrokerError("unexpected V0 action domain")

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def remaining_budget(self) -> dict[str, int]:
        spent_total = self._a_count + self._a_gate_spent + self._b_cal_count + self._b_gate_spent + self._transfer_count
        return {
            "A_discovery": BUDGET_A_DISCOVERY - self._a_count,
            "A_theory_eval": BUDGET_A_THEORY_EVAL - self._a_gate_spent,
            "B_calibration": BUDGET_B_CALIBRATION - self._b_cal_count,
            "B_theory_eval": BUDGET_B_THEORY_EVAL - self._b_gate_spent,
            "B_transfer_eval": BUDGET_B_TRANSFER_EVAL - self._transfer_count,
            "total": BROKER_BUDGET_TOTAL - spent_total,
        }

    @property
    def epistemic_cycles(self) -> int:
        return self._epistemic_cycles

    def start_epistemic_cycle(self) -> int:
        if self._phase == Phase.CLOSED:
            raise BrokerError("run is closed")
        if self._epistemic_cycles >= MAX_EPISTEMIC_CYCLES:
            raise BrokerError("maximum epistemic cycles exceeded")
        self._epistemic_cycles += 1
        self._ledger.append("epistemic_cycle_started", {"cycle": self._epistemic_cycles})
        return self._epistemic_cycles

    @staticmethod
    def _parse_experiment(value: ExperimentAST | dict[str, Any]) -> ExperimentAST:
        if isinstance(value, ExperimentAST):
            return value
        try:
            return ExperimentAST.model_validate(value)
        except ValidationError as exc:
            raise BrokerError(f"invalid Experiment AST: {exc}") from exc

    @staticmethod
    def _parse_theory(value: TheoryAST | dict[str, Any]) -> TheoryAST:
        if isinstance(value, TheoryAST):
            return value
        try:
            return TheoryAST.model_validate(value)
        except ValidationError as exc:
            raise BrokerError(f"invalid Theory AST: {exc}") from exc

    def _claim_experiment_id(self, experiment_id: str) -> None:
        if experiment_id in self._seen_experiment_ids:
            raise BrokerError("experiment_id already used")
        self._seen_experiment_ids.add(experiment_id)

    def _next_repetition(self, paradigm: str, entity: str, action: int) -> int:
        key = (paradigm, entity, action)
        repetition = self._repetitions.get(key, 0)
        self._repetitions[key] = repetition + 1
        return repetition

    def _validate_common_experiment(self, exp: ExperimentAST) -> None:
        if exp.intervention.entity_id not in self._entities:
            raise BrokerError("unknown entity")
        if exp.intervention.action_value not in self._legal_actions:
            raise BrokerError("illegal action")
        if len(set(exp.target_theory_ids)) != len(exp.target_theory_ids):
            raise BrokerError("target_theory_ids must be unique")
        pred_ids = [p.theory_id for p in exp.predictions]
        if len(set(pred_ids)) != len(pred_ids):
            raise BrokerError("one prediction per theory_id")
        if any(tid not in exp.target_theory_ids for tid in pred_ids):
            raise BrokerError("prediction theory must be a target theory")
        if any(r.theory_id not in exp.target_theory_ids for r in exp.falsification_rules):
            raise BrokerError("falsification-rule theory must be a target theory")

    def run_visible_experiment(self, value: ExperimentAST | dict[str, Any]) -> Observation:
        exp = self._parse_experiment(value)
        self._validate_common_experiment(exp)
        if self._phase == Phase.A_DISCOVERY:
            if exp.paradigm != "A":
                raise BrokerError("only Paradigm A is available during A discovery")
            if self._a_count >= BUDGET_A_DISCOVERY:
                raise BrokerError("A discovery budget exhausted; commit a theory or abstain")
        elif self._phase == Phase.B_CALIBRATION:
            if exp.paradigm != "B":
                raise BrokerError("only Paradigm B is available during B calibration")
            if exp.intervention.entity_id not in self._calibration_entities:
                raise BrokerError("entity is not available for B calibration")
            if self._b_cal_count >= BUDGET_B_CALIBRATION:
                raise BrokerError("B calibration budget exhausted; commit the B theory")
        else:
            raise BrokerError(f"visible experiments are not permitted during phase {self._phase.value}")

        self._claim_experiment_id(exp.experiment_id)
        repetition = self._next_repetition(exp.paradigm, exp.intervention.entity_id, exp.intervention.action_value)
        y = self._runtime.observe(exp.paradigm, exp.intervention.entity_id, exp.intervention.action_value, repetition)
        obs = Observation(exp.experiment_id, exp.paradigm, exp.intervention.entity_id, exp.intervention.action_value, repetition, y)
        self._visible_observations.append(asdict(obs))
        if self._phase == Phase.A_DISCOVERY:
            self._a_count += 1
        else:
            self._b_cal_count += 1
        self._ledger.append(
            "visible_experiment",
            {"experiment": exp.model_dump(mode="json"), "observation": asdict(obs), "phase": self._phase.value, "remaining_budget": self.remaining_budget},
        )
        return obs

    @staticmethod
    def _assignment_digest(latent: LatentVariable) -> str:
        canonical = json.dumps(
            {
                "domain_kind": latent.domain_kind,
                "geometry": latent.geometry,
                "cardinality": latent.cardinality,
                "assignments": latent.assignments,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(canonical).hexdigest()

    def _fail_gate(self, gate: str, reason: str, spent: int) -> None:
        result = GateFailureResult(
            outcome="theory_gate_failure",
            gate=gate,
            reason=reason,
            spent_budget=spent,
            unused_budget=self.remaining_budget["total"],
        )
        self._closed_result = result
        self._phase = Phase.CLOSED
        self._ledger.append("run_closed_gate_failure", {"result": asdict(result), "ledger_valid": self._ledger.verify()})

    def freeze_a_theory(self, value: TheoryAST | dict[str, Any]) -> TheoryAST:
        if self._phase != Phase.A_DISCOVERY or self._a_count != BUDGET_A_DISCOVERY:
            raise BrokerError(f"A theory freeze requires exactly {BUDGET_A_DISCOVERY} A interventions")
        if self._a_gate_attempts >= MAX_A_THEORY_GATE_ATTEMPTS:
            raise BrokerError("A theory gate attempt budget exhausted")

        # Charge before parsing/scoring: even malformed or low-fit theories consume
        # the preregistered gate budget and cannot be rejection-sampled for free.
        self._a_gate_attempts += 1
        self._a_gate_spent = BUDGET_A_THEORY_EVAL
        try:
            theory = self._parse_theory(value)
            if len(theory.latent_variables) != 1:
                raise BrokerError("V0 D4 candidate must contain exactly one latent variable")
            latent = theory.latent_variables[0]
            if set(latent.assignments) != self._entities:
                raise BrokerError("frozen latent assignments must cover every entity exactly once")
            a_program = program_for(theory, "A")
            if len(theory.programs) != 1:
                raise TheoryEvaluationError("A freeze must contain only the A program")
            validate_program_structure(a_program, latent.name, "x")
            if expression_depth(a_program.expression) > MAX_EXPRESSION_DEPTH:
                raise TheoryEvaluationError(f"A program exceeds frozen depth limit {MAX_EXPRESSION_DEPTH}")
            fit = score_observations(theory, "A", self._visible_observations)
            if fit.exact_accuracy < D4_VISIBLE_FIT_ACCURACY_MIN:
                raise BrokerError(f"A theory fit {fit.exact_accuracy:.3f} is below frozen threshold {D4_VISIBLE_FIT_ACCURACY_MIN:.3f}")
        except (BrokerError, TheoryEvaluationError) as exc:
            self._fail_gate("A", str(exc), BUDGET_A_THEORY_EVAL)
            raise BrokerError(f"A theory gate failed irreversibly: {exc}") from exc

        frozen_latent = latent.model_copy(update={"frozen": True})
        frozen_theory = theory.model_copy(update={"latent_variables": [frozen_latent]})
        self._frozen_latent = frozen_latent
        self._frozen_theory = frozen_theory
        self._a_fit_accuracy = fit.exact_accuracy
        self._phase = Phase.A_FROZEN
        self._ledger.append(
            "a_theory_frozen",
            {
                "theory": frozen_theory.model_dump(mode="json"),
                "assignment_digest": self._assignment_digest(frozen_latent),
                "a_fit": asdict(fit),
                "gate_budget_spent": BUDGET_A_THEORY_EVAL,
                "remaining_budget": self.remaining_budget,
            },
        )
        return frozen_theory

    def declare_no_concept(self) -> NoConceptResult:
        if self._phase != Phase.A_DISCOVERY or self._a_count != BUDGET_A_DISCOVERY:
            raise BrokerError(f"no-concept declaration requires exactly {BUDGET_A_DISCOVERY} A interventions")
        if self._a_gate_attempts:
            raise BrokerError("no-concept declaration is unavailable after attempting the A theory gate")
        result = NoConceptResult(
            outcome="no_concept",
            a_interventions=self._a_count,
            unused_budget=self.remaining_budget["total"],
        )
        self._closed_result = result
        self._phase = Phase.CLOSED
        self._ledger.append("run_closed_no_concept", {"result": asdict(result), "ledger_valid": self._ledger.verify()})
        return result

    def open_b_calibration(self) -> tuple[str, ...]:
        if self._phase != Phase.A_FROZEN:
            raise BrokerError("B calibration opens only after the A theory is frozen")
        self._phase = Phase.B_CALIBRATION
        available = tuple(sorted(self._calibration_entities))
        self._ledger.append("b_calibration_opened", {"available_entity_ids": list(available)})
        return available

    def submit_b_theory(self, value: TheoryAST | dict[str, Any]) -> TheoryAST:
        if self._phase != Phase.B_CALIBRATION or self._b_cal_count != BUDGET_B_CALIBRATION:
            raise BrokerError(f"B theory submission requires exactly {BUDGET_B_CALIBRATION} B calibration interventions")
        if self._b_gate_attempts >= MAX_B_THEORY_GATE_ATTEMPTS:
            raise BrokerError("B theory gate attempt budget exhausted")
        if self._frozen_theory is None or self._frozen_latent is None:
            raise BrokerError("internal freeze invariant violated")

        self._b_gate_attempts += 1
        self._b_gate_spent = BUDGET_B_THEORY_EVAL
        try:
            theory = self._parse_theory(value)
            if theory.theory_id != self._frozen_theory.theory_id:
                raise BrokerError("theory_id cannot change after A freeze")
            if len(theory.latent_variables) != 1 or theory.latent_variables[0].model_copy(update={"frozen": True}) != self._frozen_latent:
                raise BrokerError("frozen latent domain, geometry, cardinality, or assignments changed during B calibration")

            a_program = program_for(theory, "A")
            b_program = program_for(theory, "B")
            if len(theory.programs) != 2:
                raise TheoryEvaluationError("final D4 theory must contain exactly A and B programs")
            if a_program != program_for(self._frozen_theory, "A"):
                raise TheoryEvaluationError("frozen A explanatory program changed after B data")
            validate_program_structure(b_program, self._frozen_latent.name, "u")
            if expression_depth(b_program.expression) > MAX_EXPRESSION_DEPTH:
                raise TheoryEvaluationError(f"B program exceeds frozen depth limit {MAX_EXPRESSION_DEPTH}")
            b_fit = score_observations(theory, "B", self._visible_observations)
            if b_fit.exact_accuracy < D4_VISIBLE_FIT_ACCURACY_MIN:
                raise BrokerError(f"B calibration fit {b_fit.exact_accuracy:.3f} is below frozen threshold {D4_VISIBLE_FIT_ACCURACY_MIN:.3f}")

            a_ops = operator_signature(a_program.expression)
            b_ops = operator_signature(b_program.expression)
            if not (a_ops and b_ops and a_ops.isdisjoint(b_ops)):
                raise BrokerError(f"D4 operator-signature separation failed: A={sorted(a_ops)}, B={sorted(b_ops)}")

            iso = programs_are_isomorphic(a_program, b_program, self._frozen_latent)
            if iso.isomorphic or iso.solver_status != "unsat":
                raise BrokerError(f"SMT structural-isomorphism check failed: {iso.solver_status}")
        except (BrokerError, TheoryEvaluationError) as exc:
            self._fail_gate("B", str(exc), BUDGET_B_THEORY_EVAL)
            raise BrokerError(f"B theory gate failed irreversibly: {exc}") from exc

        self._b_theory = theory.model_copy(update={"latent_variables": [self._frozen_latent]})
        self._b_fit_accuracy = b_fit.exact_accuracy
        self._operator_diverse = True
        self._smt_result = iso
        self._phase = Phase.B_TRANSFER
        self._transfer_challenges = self._build_transfer_challenges()
        self._ledger.append(
            "b_theory_committed",
            {
                "theory": self._b_theory.model_dump(mode="json"),
                "assignment_digest": self._assignment_digest(self._frozen_latent),
                "b_calibration_fit": asdict(b_fit),
                "operator_signature_A": sorted(a_ops),
                "operator_signature_B": sorted(b_ops),
                "smt_nonisomorphism": asdict(iso),
                "gate_budget_spent": BUDGET_B_THEORY_EVAL,
                "transfer_challenges": [asdict(c) for c in self._transfer_challenges],
                "remaining_budget": self.remaining_budget,
            },
        )
        return self._b_theory

    def _build_transfer_challenges(self) -> tuple[TransferChallenge, ...]:
        challenges: list[TransferChallenge] = []
        hidden_key = self._runtime.noise_key
        for entity in sorted(self._transfer_entities):
            scored = []
            for action in range(DOMAIN_SIZE):
                digest = hashlib.sha256(f"archimedes-v0-transfer|{hidden_key}|{entity}|{action}".encode()).digest()
                scored.append((digest, action))
            chosen = sorted(action for _, action in sorted(scored)[:4])
            for action in chosen:
                challenges.append(TransferChallenge(f"C-{len(challenges):02d}", entity, action))
        if len(challenges) != BUDGET_B_TRANSFER_EVAL:
            raise BrokerError("transfer challenge cardinality invariant violated")
        return tuple(challenges)

    def transfer_challenges(self) -> tuple[TransferChallenge, ...]:
        if self._phase != Phase.B_TRANSFER:
            raise BrokerError("transfer challenge set is not available in this phase")
        return tuple(self._transfer_challenges)

    def execute_transfer_evaluation(self) -> D4Result:
        if self._phase != Phase.B_TRANSFER or self._b_theory is None:
            raise BrokerError("transfer evaluation is not available in this phase")
        if self._transfer_count != 0:
            raise BrokerError("transfer evaluation may execute only once")

        committed: list[dict[str, Any]] = []
        for i, challenge in enumerate(self._transfer_challenges):
            try:
                predicted_y = predict(self._b_theory, "B", challenge.entity_id, challenge.action_value)
            except TheoryEvaluationError as exc:
                raise BrokerError(f"committed B theory cannot produce transfer prediction: {exc}") from exc
            probs = [1.0 if y == predicted_y else 0.0 for y in range(DOMAIN_SIZE)]
            exp = ExperimentAST(
                experiment_id=f"E-TRANSFER-{i:02d}",
                objective="estimate",
                paradigm="B",
                intervention=Intervention(entity_id=challenge.entity_id, action_value=challenge.action_value),
                target_theory_ids=[self._b_theory.theory_id],
                predictions=[TheoryPrediction(theory_id=self._b_theory.theory_id, categorical_probabilities=probs)],
            )
            self._claim_experiment_id(exp.experiment_id)
            committed.append({"challenge_id": challenge.challenge_id, "experiment": exp.model_dump(mode="json"), "predicted_y": predicted_y})

        self._ledger.append("transfer_predictions_committed", {"predictions": committed})

        for item, challenge in zip(committed, self._transfer_challenges, strict=True):
            repetition = self._next_repetition("B", challenge.entity_id, challenge.action_value)
            observed_y = self._runtime.observe("B", challenge.entity_id, challenge.action_value, repetition)
            predicted_y = item["predicted_y"]
            outcome = {
                "challenge_id": challenge.challenge_id,
                "experiment_id": item["experiment"]["experiment_id"],
                "entity_id": challenge.entity_id,
                "action_value": challenge.action_value,
                "repetition": repetition,
                "predicted_y": predicted_y,
                "observed_y": observed_y,
                "correct": predicted_y == observed_y,
            }
            self._transfer_outcomes.append(outcome)
            self._transfer_count += 1
            self._ledger.append(
                "sealed_transfer_observation",
                {
                    "challenge_id": challenge.challenge_id,
                    "observation": {"repetition": repetition, "y": observed_y, "correct": predicted_y == observed_y},
                    "remaining_budget": self.remaining_budget,
                },
                sealed=True,
            )

        return self._close_run()

    def _close_run(self) -> D4Result:
        if self._transfer_count != BUDGET_B_TRANSFER_EVAL or self.remaining_budget["total"] != 0:
            raise BrokerError("run closure requires exact exhaustion of the frozen 128-unit resource budget")
        if self._b_theory is None or self._frozen_latent is None or self._a_fit_accuracy is None or self._b_fit_accuracy is None or self._smt_result is None:
            raise BrokerError("internal D4 scoring invariant violated")
        correct = sum(int(o["correct"]) for o in self._transfer_outcomes)
        accuracy = correct / BUDGET_B_TRANSFER_EVAL
        smt_nonisomorphic = (not self._smt_result.isomorphic and self._smt_result.solver_status == "unsat")
        qualifies = (
            self._a_fit_accuracy >= D4_VISIBLE_FIT_ACCURACY_MIN
            and self._b_fit_accuracy >= D4_VISIBLE_FIT_ACCURACY_MIN
            and self._operator_diverse
            and smt_nonisomorphic
            and accuracy >= D4_TRANSFER_ACCURACY_MIN
        )
        result = D4Result(
            theory_id=self._b_theory.theory_id,
            latent_cardinality=self._frozen_latent.cardinality,
            a_fit_accuracy=self._a_fit_accuracy,
            b_calibration_fit_accuracy=self._b_fit_accuracy,
            operator_diverse=self._operator_diverse,
            smt_nonisomorphic=smt_nonisomorphic,
            correct=correct,
            total=BUDGET_B_TRANSFER_EVAL,
            exact_accuracy=accuracy,
            qualifies=qualifies,
        )
        self._closed_result = result
        self._phase = Phase.CLOSED
        self._ledger.append("run_closed", {"d4_result": asdict(result), "ledger_valid": self._ledger.verify()})
        return result

    def agent_ledger(self) -> tuple[dict[str, Any], ...]:
        records = []
        for record in self._ledger.snapshot():
            if record["sealed"] and self._phase != Phase.CLOSED:
                record["payload"] = {"observation": "SEALED_UNTIL_RUN_CLOSE"}
                record["projection_note"] = "sealed payload redacted; verify trusted ledger after close"
            records.append(record)
        return tuple(records)

    def trusted_ledger(self) -> tuple[dict[str, Any], ...]:
        return self._ledger.snapshot()

    def verify_ledger(self) -> bool:
        return self._ledger.verify()

    def closed_transfer_outcomes(self) -> tuple[dict[str, Any], ...]:
        if self._phase != Phase.CLOSED:
            raise BrokerError("transfer outcomes remain sealed until run closure")
        return tuple(json.loads(json.dumps(o)) for o in self._transfer_outcomes)
