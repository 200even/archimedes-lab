from __future__ import annotations

from typing import Any

from .v1_agent_interfaces import V1AgentInterfaceError, V1Conjecturer, V1Critic, V1FlatAgent
from .v1_broker import V1Broker, V1BrokerError, V1Result
from .v1_protocol import (
    ACTIONS,
    ENTITIES,
    A_DISCOVERY_BUDGET,
    CandidatePartitionSet,
    PartitionHypothesis,
    canonicalize_partition,
)

A_RESEARCH_ROUNDS = 6
A_BATCH_SIZE = 10
FULL_MAX_CALLS = 13
FLAT_MAX_CALLS = 13
FULL_MAX_OUTPUT_TOKENS = 40_960
FLAT_MAX_OUTPUT_TOKENS = 40_960


def _normalize_candidates(candidates: CandidatePartitionSet) -> CandidatePartitionSet:
    normalized: list[PartitionHypothesis] = []
    for candidate in candidates.candidates:
        canonical = canonicalize_partition(candidate)
        normalized.append(
            PartitionHypothesis(
                hypothesis_id=candidate.hypothesis_id,
                group_count=canonical.group_count,
                entity_group=canonical.entity_group,
            )
        )
    return CandidatePartitionSet(candidates=normalized)


def _base_payload(broker: V1Broker, *, round_index: int, task: str) -> dict[str, Any]:
    return {
        "protocol": "Archimedes-V1-direct-entity-transfer",
        "task": task,
        "round_index": round_index,
        "public_geometry": {
            "entities": list(ENTITIES),
            "legal_action_values": list(ACTIONS),
            "outcome_domain": list(ACTIONS),
            "known_measurement_corruption_rate": 0.02,
        },
        "resource_state": {
            "A_discovery_used": len(broker.visible_a_observations),
            "A_discovery_total": A_DISCOVERY_BUDGET,
            "rounds_total": A_RESEARCH_ROUNDS,
            "batch_size": A_BATCH_SIZE,
        },
        "visible_A_observations": list(broker.visible_a_observations),
    }


class V1FullOrchestrator:
    """13-call Full schedule: 6 Conjecturer+Critic rounds and one A commit."""

    def __init__(self, broker: V1Broker, conjecturer: V1Conjecturer, critic: V1Critic):
        self._broker = broker
        self._conjecturer = conjecturer
        self._critic = critic

    def run(self, *, execution_authorized: bool = False) -> V1Result:
        if not execution_authorized:
            raise RuntimeError("V1 execution guard is locked; benchmark exposure is not authorized")
        try:
            for round_index in range(A_RESEARCH_ROUNDS):
                proposal_payload = _base_payload(self._broker, round_index=round_index, task="generate_partitions")
                candidates = _normalize_candidates(self._conjecturer.propose(proposal_payload))
                selector_payload = _base_payload(self._broker, round_index=round_index, task="select_A_interventions")
                selector_payload["candidate_partitions"] = candidates.model_dump(mode="json")
                batch = self._critic.select(selector_payload)
                self._broker.execute_a_batch(batch)

            commit_payload = _base_payload(self._broker, round_index=A_RESEARCH_ROUNDS, task="commit_partition_or_abstain")
            decision = self._conjecturer.commit(commit_payload)
            early_result = self._broker.submit_a_commit(decision)
            if early_result is not None:
                return early_result
            return self._broker.run_b()
        except (V1AgentInterfaceError, V1BrokerError):
            return self._broker.result or self._broker.close_external_failure()


class V1FlatOrchestrator:
    """13-call Flat schedule using one role/prompt for Generate, Select, Commit."""

    def __init__(self, broker: V1Broker, flat: V1FlatAgent):
        self._broker = broker
        self._flat = flat

    def run(self, *, execution_authorized: bool = False) -> V1Result:
        if not execution_authorized:
            raise RuntimeError("V1 execution guard is locked; benchmark exposure is not authorized")
        try:
            for round_index in range(A_RESEARCH_ROUNDS):
                generate_payload = _base_payload(self._broker, round_index=round_index, task="generate_partitions")
                candidates = _normalize_candidates(self._flat.generate(generate_payload))
                select_payload = _base_payload(self._broker, round_index=round_index, task="select_A_interventions")
                select_payload["candidate_partitions"] = candidates.model_dump(mode="json")
                batch = self._flat.select(select_payload)
                self._broker.execute_a_batch(batch)

            commit_payload = _base_payload(self._broker, round_index=A_RESEARCH_ROUNDS, task="commit_partition_or_abstain")
            decision = self._flat.commit(commit_payload)
            early_result = self._broker.submit_a_commit(decision)
            if early_result is not None:
                return early_result
            return self._broker.run_b()
        except (V1AgentInterfaceError, V1BrokerError):
            return self._broker.result or self._broker.close_external_failure()
