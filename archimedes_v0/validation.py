from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any
from .constants import (
    DOMAIN_SIZE, NUM_ENTITIES, LATENT_REPLICATION, MIN_UNIQUE_OUTPUTS_PER_Q,
    MIN_UNIQUE_OUTPUTS_PER_ACTION_ACROSS_Q, MAX_ACTION_ONLY_ACCURACY,
    MAX_ENTITY_ONLY_ACCURACY, MAX_CONSTANT_ACCURACY,
)
from .grammar import Program


def _program(d: dict[str, Any]) -> Program:
    return Program(template=d["template"], params=d["params"])


def _mode_accuracy(rows: list[tuple], key_index: int | None) -> float:
    # rows: entity, action, y
    if key_index is None:
        counts = Counter(r[2] for r in rows)
        return max(counts.values()) / len(rows)
    groups = defaultdict(list)
    for r in rows:
        groups[r[key_index]].append(r[2])
    correct = 0
    for ys in groups.values():
        correct += max(Counter(ys).values())
    return correct / len(rows)


def validate_hidden_world(hidden) -> dict[str, Any]:
    if hidden.world_kind == "null":
        return {"accepted": True, "kind": "null"}
    q_by_entity = hidden.latent_q_by_entity
    pa, pb = _program(hidden.program_a), _program(hidden.program_b)

    q_counts = Counter(q_by_entity.values())
    replication_ok = all(q_counts[q] == LATENT_REPLICATION for q in range(DOMAIN_SIZE))

    sig_a = {q: tuple(pa.evaluate(q, x) for x in range(DOMAIN_SIZE)) for q in range(DOMAIN_SIZE)}
    sig_b = {q: tuple(pb.evaluate(q, x) for x in range(DOMAIN_SIZE)) for q in range(DOMAIN_SIZE)}
    identifiable_a = len(set(sig_a.values())) == DOMAIN_SIZE
    identifiable_b = len(set(sig_b.values())) == DOMAIN_SIZE

    per_q_a = min(len(set(sig_a[q])) for q in range(DOMAIN_SIZE))
    per_q_b = min(len(set(sig_b[q])) for q in range(DOMAIN_SIZE))
    per_action_a = min(len({pa.evaluate(q, x) for q in range(DOMAIN_SIZE)}) for x in range(DOMAIN_SIZE))
    per_action_b = min(len({pb.evaluate(q, x) for q in range(DOMAIN_SIZE)}) for x in range(DOMAIN_SIZE))

    rows_a, rows_b = [], []
    for entity, q in q_by_entity.items():
        for x in range(DOMAIN_SIZE):
            rows_a.append((entity, x, pa.evaluate(q, x)))
            rows_b.append((entity, x, pb.evaluate(q, x)))

    baseline = {
        "A": {
            "constant_accuracy": _mode_accuracy(rows_a, None),
            "action_only_accuracy": _mode_accuracy(rows_a, 1),
            "entity_only_accuracy": _mode_accuracy(rows_a, 0),
        },
        "B": {
            "constant_accuracy": _mode_accuracy(rows_b, None),
            "action_only_accuracy": _mode_accuracy(rows_b, 1),
            "entity_only_accuracy": _mode_accuracy(rows_b, 0),
        },
    }
    nontrivial = (
        per_q_a >= MIN_UNIQUE_OUTPUTS_PER_Q and per_q_b >= MIN_UNIQUE_OUTPUTS_PER_Q and
        per_action_a >= MIN_UNIQUE_OUTPUTS_PER_ACTION_ACROSS_Q and per_action_b >= MIN_UNIQUE_OUTPUTS_PER_ACTION_ACROSS_Q and
        all(v["constant_accuracy"] <= MAX_CONSTANT_ACCURACY for v in baseline.values()) and
        all(v["action_only_accuracy"] <= MAX_ACTION_ONLY_ACCURACY for v in baseline.values()) and
        all(v["entity_only_accuracy"] <= MAX_ENTITY_ONLY_ACCURACY for v in baseline.values())
    )

    operator_diversity = pa.operator_families().isdisjoint(pb.operator_families() - {"permutation"}) and (
        "modular_arithmetic" in pa.operator_families() and "bitwise" in pb.operator_families()
    )
    split_ok = (
        len(hidden.b_calibration_entities) == DOMAIN_SIZE and len(hidden.b_transfer_entities) == DOMAIN_SIZE and
        set(hidden.b_calibration_entities).isdisjoint(hidden.b_transfer_entities) and
        len({q_by_entity[e] for e in hidden.b_calibration_entities}) == DOMAIN_SIZE and
        len({q_by_entity[e] for e in hidden.b_transfer_entities}) == DOMAIN_SIZE
    )

    accepted = all([replication_ok, identifiable_a, identifiable_b, nontrivial, operator_diversity, split_ok])
    return {
        "accepted": accepted,
        "replication_ok": replication_ok,
        "identifiable": {"A": identifiable_a, "B": identifiable_b},
        "minimum_unique_outputs_per_q": {"A": per_q_a, "B": per_q_b},
        "minimum_unique_outputs_per_action_across_q": {"A": per_action_a, "B": per_action_b},
        "simple_baselines": baseline,
        "operator_families": {"A": sorted(pa.operator_families()), "B": sorted(pb.operator_families())},
        "operator_diversity_ok": operator_diversity,
        "b_split_ok": split_ok,
    }
