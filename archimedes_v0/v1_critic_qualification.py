from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .v1_agent_interfaces import V1Critic
from .v1_protocol import ACTIONS, ENTITIES, CandidatePartitionSet, PartitionHypothesis, canonicalize_partition

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "V1_CRITIC_QUALIFICATION_FIXTURES.json"


@dataclass(frozen=True)
class CriticQualificationCycleResult:
    cycle_id: str
    selected_revealing_intervention: bool
    target_entity_id: str
    target_action_value: int


@dataclass(frozen=True)
class CriticQualificationResult:
    fixture_set: str
    cycles: tuple[CriticQualificationCycleResult, ...]
    consecutive_misses: int
    passes_safeguard: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_set": self.fixture_set,
            "cycles": [asdict(cycle) for cycle in self.cycles],
            "consecutive_misses": self.consecutive_misses,
            "passes_safeguard": self.passes_safeguard,
        }


def load_fixtures() -> dict[str, Any]:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if raw.get("status") != "FROZEN_BEFORE_PROVIDER_QUALIFICATION":
        raise RuntimeError("Critic qualification fixture status is not frozen")
    if raw.get("independent_of_benchmark_generator") is not True:
        raise RuntimeError("Critic qualification fixtures must be generator-independent")
    cycles = raw.get("cycles")
    if not isinstance(cycles, list) or len(cycles) != 3:
        raise RuntimeError("Critic safeguard requires exactly three preregistered cycles")
    return raw


def _agent_payload(cycle: dict[str, Any], cycle_index: int) -> dict[str, Any]:
    # Deliberately omit every trusted_* field. The model sees only the legal
    # public geometry, injected candidate grouping, and synthetic visible records.
    partition = PartitionHypothesis.model_validate(cycle["candidate_partition"])
    canonical = canonicalize_partition(partition)
    normalized = PartitionHypothesis(
        hypothesis_id=partition.hypothesis_id,
        group_count=canonical.group_count,
        entity_group=canonical.entity_group,
    )
    candidates = CandidatePartitionSet(candidates=[normalized])
    return {
        "protocol": "Archimedes-V1-Critic-synthetic-qualification",
        "task": "select_A_interventions",
        "round_index": cycle_index,
        "public_geometry": {
            "entities": list(ENTITIES),
            "legal_action_values": list(ACTIONS),
            "outcome_domain": list(ACTIONS),
            "known_measurement_corruption_rate": 0.02,
        },
        "resource_state": {
            "A_discovery_used": len(cycle["visible_A_observations"]),
            "A_discovery_total": 60,
            "rounds_total": 3,
            "batch_size": 10,
        },
        "visible_A_observations": cycle["visible_A_observations"],
        "candidate_partitions": candidates.model_dump(mode="json"),
    }


def run_critic_qualification(critic: V1Critic) -> CriticQualificationResult:
    fixtures = load_fixtures()
    cycle_results: list[CriticQualificationCycleResult] = []
    misses = 0

    for cycle_index, cycle in enumerate(fixtures["cycles"]):
        expected = cycle["trusted_expected_revealing_intervention"]
        batch = critic.select(_agent_payload(cycle, cycle_index))
        hit = any(
            experiment.entity_id == expected["entity_id"]
            and experiment.action_value == expected["action_value"]
            for experiment in batch.experiments
        )
        misses = 0 if hit else misses + 1
        cycle_results.append(
            CriticQualificationCycleResult(
                cycle_id=cycle["cycle_id"],
                selected_revealing_intervention=hit,
                target_entity_id=expected["entity_id"],
                target_action_value=expected["action_value"],
            )
        )

    return CriticQualificationResult(
        fixture_set=fixtures["fixture_set"],
        cycles=tuple(cycle_results),
        consecutive_misses=misses,
        passes_safeguard=misses < 3,
    )
