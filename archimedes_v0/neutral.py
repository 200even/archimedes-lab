from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from .ast_schema import TheoryAST


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def neutral_theory(theory: TheoryAST) -> dict[str, Any]:
    """Return the only theory representation that may cross agent-role boundaries."""
    value = theory.model_dump(mode="json")
    value["status"] = "candidate"
    value["evidence_experiment_ids"] = []
    return json.loads(canonical_json(value))


def neutral_theories(theories: Iterable[TheoryAST]) -> tuple[dict[str, Any], ...]:
    return tuple(
        neutral_theory(theory)
        for theory in sorted(theories, key=lambda item: item.theory_id)
    )


def observation_view(agent_ledger: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Project the broker ledger to visible measurements only.

    Timestamps, hashes, model prose, sealed payloads and trusted evaluator details
    are deliberately absent from the role-facing view.
    """
    observations: list[dict[str, Any]] = []
    for record in agent_ledger:
        if record.get("event_type") != "visible_experiment":
            continue
        payload = record.get("payload", {})
        observation = payload.get("observation")
        if not isinstance(observation, dict):
            continue
        observations.append(
            {
                "experiment_id": observation["experiment_id"],
                "paradigm": observation["paradigm"],
                "entity_id": observation["entity_id"],
                "action_value": observation["action_value"],
                "repetition": observation["repetition"],
                "y": observation["y"],
            }
        )
    return tuple(observations)
