from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .agent_interfaces import StatelessConjecturer, StatelessCritic, StatelessFlatAgent
from .agent_protocol import ExperimentBatch
from .ast_schema import ExperimentAST, TheoryAST
from .broker import D4Result, ExperimentBroker, GateFailureResult, NoConceptResult
from .constants import DOMAIN_SIZE
from .diagnostics import FunctionalMinimalityResult, functional_minimality
from .neutral import neutral_theories, neutral_theory, observation_view
from .synthesis import CandidateSynthesizer, NoSynthesis


A_BATCH_SIZES = (10, 10, 10, 10, 10, 10)
B_BATCH_SIZES = (7, 7, 7, 7)
assert sum(A_BATCH_SIZES) == 60
assert sum(B_BATCH_SIZES) == 28


class OrchestrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OrchestrationAudit:
    arm: str
    conjecturer_calls: int
    critic_calls: int
    flat_calls: int
    epistemic_cycles: int
    a_minimality: FunctionalMinimalityResult | None


@dataclass(frozen=True)
class OrchestrationResult:
    result: D4Result | NoConceptResult | GateFailureResult
    audit: OrchestrationAudit


def _validate_batch(
    batch: ExperimentBatch,
    *,
    expected_count: int,
    paradigm: str,
    allowed_entities: Iterable[str],
    allowed_targets: set[str],
) -> tuple[ExperimentAST, ...]:
    experiments = tuple(batch.experiments)
    if len(experiments) != expected_count:
        raise OrchestrationError(f"expected exactly {expected_count} experiments")
    entity_set = set(allowed_entities)
    seen_ids: set[str] = set()
    for exp in experiments:
        if exp.experiment_id in seen_ids:
            raise OrchestrationError("experiment ids must be unique within a batch")
        seen_ids.add(exp.experiment_id)
        if exp.paradigm != paradigm:
            raise OrchestrationError(f"expected paradigm {paradigm}")
        if exp.intervention.entity_id not in entity_set:
            raise OrchestrationError("experiment uses an unavailable entity")
        if not 0 <= exp.intervention.action_value < DOMAIN_SIZE:
            raise OrchestrationError("experiment uses an illegal action")
        if not set(exp.target_theory_ids).issubset(allowed_targets):
            raise OrchestrationError("experiment targets a model not supplied to the selector")
    return experiments


def _common_payload(broker: ExperimentBroker, *, phase: str, round_index: int) -> dict[str, Any]:
    return {
        "phase": phase,
        "round_index": round_index,
        "public_world": broker.public,
        "observations": list(observation_view(broker.agent_ledger())),
        "remaining_budget": broker.remaining_budget,
    }


def _selection_models(synthesized: tuple[TheoryAST, ...], proposed: tuple[TheoryAST, ...]) -> tuple[TheoryAST, ...]:
    return synthesized if synthesized else proposed


def _target_ids(models: tuple[TheoryAST, ...]) -> set[str]:
    return {theory.theory_id for theory in models} or {"T-explore"}


class ArchimedesOrchestrator:
    """Deterministic Full schedule: Conjecturer -> synthesis -> isolated Critic."""

    def __init__(
        self,
        *,
        broker: ExperimentBroker,
        conjecturer: StatelessConjecturer,
        critic: StatelessCritic,
        synthesizer: CandidateSynthesizer | None = None,
        execution_authorized: bool = False,
    ):
        self.broker = broker
        self.conjecturer = conjecturer
        self.critic = critic
        self.synthesizer = synthesizer or NoSynthesis()
        self.execution_authorized = execution_authorized

    def run(self) -> OrchestrationResult:
        if not self.execution_authorized:
            raise OrchestrationError("benchmark execution is blocked pending pre-exposure referee authorization")

        conjecturer_calls = 0
        critic_calls = 0
        a_minimality: FunctionalMinimalityResult | None = None
        previous_synthesized: tuple[TheoryAST, ...] = ()

        for round_index, batch_size in enumerate(A_BATCH_SIZES, start=1):
            self.broker.start_epistemic_cycle()
            base = _common_payload(self.broker, phase="A", round_index=round_index)
            proposal = self.conjecturer.propose_candidates(
                {
                    **base,
                    "prior_synthesis_results": list(neutral_theories(previous_synthesized)),
                }
            )
            conjecturer_calls += 1
            proposed = tuple(proposal.candidates)
            synthesized = self.synthesizer.synthesize(
                paradigm="A",
                observations=tuple(base["observations"]),
                candidate_theories=proposed,
                frozen_a_theory=None,
                limit=32,
            )
            previous_synthesized = synthesized
            selection_models = _selection_models(synthesized, proposed)
            targets = _target_ids(selection_models)

            batch = self.critic.propose_experiments(
                {
                    **base,
                    "candidate_models": list(neutral_theories(selection_models)),
                    "allowed_entity_ids": sorted(self.broker.public["entities"]),
                    "legal_action_values": list(range(DOMAIN_SIZE)),
                    "allowed_target_ids": sorted(targets),
                    "required_batch_size": batch_size,
                }
            )
            critic_calls += 1
            experiments = _validate_batch(
                batch,
                expected_count=batch_size,
                paradigm="A",
                allowed_entities=self.broker.public["entities"],
                allowed_targets=targets,
            )
            for experiment in experiments:
                self.broker.run_visible_experiment(experiment)

        a_decision = self.conjecturer.decide_a(
            {
                **_common_payload(self.broker, phase="A_COMMIT", round_index=7),
                "synthesis_results": list(neutral_theories(previous_synthesized)),
                "instruction": "Return one executable model or abstain.",
            }
        )
        conjecturer_calls += 1
        if a_decision.decision == "abstain":
            result = self.broker.declare_no_concept()
            return OrchestrationResult(
                result=result,
                audit=OrchestrationAudit(
                    arm="full",
                    conjecturer_calls=conjecturer_calls,
                    critic_calls=critic_calls,
                    flat_calls=0,
                    epistemic_cycles=self.broker.epistemic_cycles,
                    a_minimality=None,
                ),
            )

        frozen_a = self.broker.freeze_a_theory(a_decision.theory)
        a_minimality = functional_minimality(frozen_a, "A")
        calibration_entities = self.broker.open_b_calibration()
        previous_synthesized = ()

        for offset, batch_size in enumerate(B_BATCH_SIZES, start=1):
            round_index = len(A_BATCH_SIZES) + offset
            self.broker.start_epistemic_cycle()
            base = _common_payload(self.broker, phase="B", round_index=round_index)
            proposal = self.conjecturer.propose_candidates(
                {
                    **base,
                    "frozen_a_model": neutral_theory(frozen_a),
                    "prior_synthesis_results": list(neutral_theories(previous_synthesized)),
                }
            )
            conjecturer_calls += 1
            proposed = tuple(proposal.candidates)
            synthesized = self.synthesizer.synthesize(
                paradigm="B",
                observations=tuple(base["observations"]),
                candidate_theories=proposed,
                frozen_a_theory=frozen_a,
                limit=32,
            )
            previous_synthesized = synthesized
            selection_models = _selection_models(synthesized, proposed)
            targets = _target_ids(selection_models)

            batch = self.critic.propose_experiments(
                {
                    **base,
                    "frozen_a_model": neutral_theory(frozen_a),
                    "candidate_models": list(neutral_theories(selection_models)),
                    "allowed_entity_ids": list(calibration_entities),
                    "legal_action_values": list(range(DOMAIN_SIZE)),
                    "allowed_target_ids": sorted(targets),
                    "required_batch_size": batch_size,
                }
            )
            critic_calls += 1
            experiments = _validate_batch(
                batch,
                expected_count=batch_size,
                paradigm="B",
                allowed_entities=calibration_entities,
                allowed_targets=targets,
            )
            for experiment in experiments:
                self.broker.run_visible_experiment(experiment)

        b_decision = self.conjecturer.decide_b(
            {
                **_common_payload(self.broker, phase="B_COMMIT", round_index=11),
                "frozen_a_model": neutral_theory(frozen_a),
                "synthesis_results": list(neutral_theories(previous_synthesized)),
                "instruction": "Return one executable model preserving every broker-frozen field.",
            }
        )
        conjecturer_calls += 1
        self.broker.submit_b_theory(b_decision.theory)
        result = self.broker.execute_transfer_evaluation()
        return OrchestrationResult(
            result=result,
            audit=OrchestrationAudit(
                arm="full",
                conjecturer_calls=conjecturer_calls,
                critic_calls=critic_calls,
                flat_calls=0,
                epistemic_cycles=self.broker.epistemic_cycles,
                a_minimality=a_minimality,
            ),
        )


class FlatBaselineOrchestrator:
    """Compute-matched Flat schedule: same-role Generate -> synthesis -> Select."""

    def __init__(
        self,
        *,
        broker: ExperimentBroker,
        agent: StatelessFlatAgent,
        synthesizer: CandidateSynthesizer | None = None,
        execution_authorized: bool = False,
    ):
        self.broker = broker
        self.agent = agent
        self.synthesizer = synthesizer or NoSynthesis()
        self.execution_authorized = execution_authorized

    def run(self) -> OrchestrationResult:
        if not self.execution_authorized:
            raise OrchestrationError("benchmark execution is blocked pending pre-exposure referee authorization")

        flat_calls = 0
        a_minimality: FunctionalMinimalityResult | None = None
        previous_synthesized: tuple[TheoryAST, ...] = ()

        for round_index, batch_size in enumerate(A_BATCH_SIZES, start=1):
            self.broker.start_epistemic_cycle()
            base = _common_payload(self.broker, phase="A", round_index=round_index)

            proposal = self.agent.propose_candidates(
                {
                    **base,
                    "prior_synthesis_results": list(neutral_theories(previous_synthesized)),
                }
            )
            flat_calls += 1
            proposed = tuple(proposal.candidates)
            synthesized = self.synthesizer.synthesize(
                paradigm="A",
                observations=tuple(base["observations"]),
                candidate_theories=proposed,
                frozen_a_theory=None,
                limit=32,
            )
            previous_synthesized = synthesized
            selection_models = _selection_models(synthesized, proposed)
            targets = _target_ids(selection_models)

            batch = self.agent.propose_experiments(
                {
                    **base,
                    "candidate_models": list(neutral_theories(selection_models)),
                    "allowed_entity_ids": sorted(self.broker.public["entities"]),
                    "legal_action_values": list(range(DOMAIN_SIZE)),
                    "allowed_target_ids": sorted(targets),
                    "required_batch_size": batch_size,
                }
            )
            flat_calls += 1
            experiments = _validate_batch(
                batch,
                expected_count=batch_size,
                paradigm="A",
                allowed_entities=self.broker.public["entities"],
                allowed_targets=targets,
            )
            for experiment in experiments:
                self.broker.run_visible_experiment(experiment)

        decision = self.agent.decide_a(
            {
                **_common_payload(self.broker, phase="A_COMMIT", round_index=7),
                "synthesis_results": list(neutral_theories(previous_synthesized)),
                "instruction": "Return one executable model or abstain.",
            }
        )
        flat_calls += 1
        if decision.decision == "abstain":
            result = self.broker.declare_no_concept()
            return OrchestrationResult(
                result=result,
                audit=OrchestrationAudit(
                    arm="flat",
                    conjecturer_calls=0,
                    critic_calls=0,
                    flat_calls=flat_calls,
                    epistemic_cycles=self.broker.epistemic_cycles,
                    a_minimality=None,
                ),
            )

        frozen_a = self.broker.freeze_a_theory(decision.theory)
        a_minimality = functional_minimality(frozen_a, "A")
        calibration_entities = self.broker.open_b_calibration()
        previous_synthesized = ()

        for offset, batch_size in enumerate(B_BATCH_SIZES, start=1):
            round_index = len(A_BATCH_SIZES) + offset
            self.broker.start_epistemic_cycle()
            base = _common_payload(self.broker, phase="B", round_index=round_index)

            proposal = self.agent.propose_candidates(
                {
                    **base,
                    "frozen_a_model": neutral_theory(frozen_a),
                    "prior_synthesis_results": list(neutral_theories(previous_synthesized)),
                }
            )
            flat_calls += 1
            proposed = tuple(proposal.candidates)
            synthesized = self.synthesizer.synthesize(
                paradigm="B",
                observations=tuple(base["observations"]),
                candidate_theories=proposed,
                frozen_a_theory=frozen_a,
                limit=32,
            )
            previous_synthesized = synthesized
            selection_models = _selection_models(synthesized, proposed)
            targets = _target_ids(selection_models)

            batch = self.agent.propose_experiments(
                {
                    **base,
                    "frozen_a_model": neutral_theory(frozen_a),
                    "candidate_models": list(neutral_theories(selection_models)),
                    "allowed_entity_ids": list(calibration_entities),
                    "legal_action_values": list(range(DOMAIN_SIZE)),
                    "allowed_target_ids": sorted(targets),
                    "required_batch_size": batch_size,
                }
            )
            flat_calls += 1
            experiments = _validate_batch(
                batch,
                expected_count=batch_size,
                paradigm="B",
                allowed_entities=calibration_entities,
                allowed_targets=targets,
            )
            for experiment in experiments:
                self.broker.run_visible_experiment(experiment)

        b_decision = self.agent.decide_b(
            {
                **_common_payload(self.broker, phase="B_COMMIT", round_index=11),
                "frozen_a_model": neutral_theory(frozen_a),
                "synthesis_results": list(neutral_theories(previous_synthesized)),
                "instruction": "Return one executable model preserving every broker-frozen field.",
            }
        )
        flat_calls += 1
        self.broker.submit_b_theory(b_decision.theory)
        result = self.broker.execute_transfer_evaluation()
        return OrchestrationResult(
            result=result,
            audit=OrchestrationAudit(
                arm="flat",
                conjecturer_calls=0,
                critic_calls=0,
                flat_calls=flat_calls,
                epistemic_cycles=self.broker.epistemic_cycles,
                a_minimality=a_minimality,
            ),
        )
