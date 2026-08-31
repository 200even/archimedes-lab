from __future__ import annotations
from collections import Counter, defaultdict
from typing import Any
from .constants import (
    DOMAIN_SIZE,
    NUM_ENTITIES,
    HIDDEN_LATENT_CARDINALITIES,
    MIN_ENTITIES_PER_LATENT_STATE,
    MIN_UNIQUE_OUTPUTS_PER_Q,
    MIN_UNIQUE_OUTPUTS_PER_ACTION_ACROSS_Q,
    MAX_ACTION_ONLY_ACCURACY,
    MAX_ENTITY_ONLY_ACCURACY,
    MAX_CONSTANT_ACCURACY,
)
from .grammar import Program
from .smt_isomorphism import truth_tables_are_isomorphic


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

    k = hidden.latent_cardinality
    if k not in HIDDEN_LATENT_CARDINALITIES:
        return {"accepted": False, "latent_cardinality_ok": False}

    q_by_entity = hidden.latent_q_by_entity
    pa, pb = _program(hidden.program_a), _program(hidden.program_b)

    q_counts = Counter(q_by_entity.values())
    cardinality_ok = set(q_counts) == set(range(k))
    balanced_partition_ok = (
        cardinality_ok
        and sum(q_counts.values()) == NUM_ENTITIES
        and min(q_counts.values()) >= MIN_ENTITIES_PER_LATENT_STATE
        and max(q_counts.values()) - min(q_counts.values()) <= 1
    )

    sig_a = {q: tuple(pa.evaluate(q, x) for x in range(DOMAIN_SIZE)) for q in range(k)}
    sig_b = {q: tuple(pb.evaluate(q, x) for x in range(DOMAIN_SIZE)) for q in range(k)}
    identifiable_a = len(set(sig_a.values())) == k
    identifiable_b = len(set(sig_b.values())) == k

    per_q_a = min(len(set(sig_a[q])) for q in range(k))
    per_q_b = min(len(set(sig_b[q])) for q in range(k))
    per_action_a = min(len({pa.evaluate(q, x) for q in range(k)}) for x in range(DOMAIN_SIZE))
    per_action_b = min(len({pb.evaluate(q, x) for q in range(k)}) for x in range(DOMAIN_SIZE))
    action_q_target = min(MIN_UNIQUE_OUTPUTS_PER_ACTION_ACROSS_Q, k)

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
        per_q_a >= MIN_UNIQUE_OUTPUTS_PER_Q
        and per_q_b >= MIN_UNIQUE_OUTPUTS_PER_Q
        and per_action_a >= action_q_target
        and per_action_b >= action_q_target
        and all(v["constant_accuracy"] <= MAX_CONSTANT_ACCURACY for v in baseline.values())
        and all(v["action_only_accuracy"] <= MAX_ACTION_ONLY_ACCURACY for v in baseline.values())
        and all(v["entity_only_accuracy"] <= MAX_ENTITY_ONLY_ACCURACY for v in baseline.values())
    )

    family_diversity = pa.operator_families().isdisjoint(pb.operator_families() - {"permutation"}) and (
        "modular_arithmetic" in pa.operator_families() and "bitwise" in pb.operator_families()
    )

    table_a = [[pa.evaluate(q, x) for x in range(DOMAIN_SIZE)] for q in range(k)]
    table_b = [[pb.evaluate(q, x) for x in range(DOMAIN_SIZE)] for q in range(k)]
    iso = truth_tables_are_isomorphic(table_a, table_b)
    smt_nonisomorphic = not iso.isomorphic and iso.solver_status in {"unsat", "cardinality_mismatch"}

    split_ok = (
        len(hidden.b_calibration_entities) == NUM_ENTITIES // 2
        and len(hidden.b_transfer_entities) == NUM_ENTITIES // 2
        and set(hidden.b_calibration_entities).isdisjoint(hidden.b_transfer_entities)
        and set(hidden.b_calibration_entities) | set(hidden.b_transfer_entities) == set(q_by_entity)
        and {q_by_entity[e] for e in hidden.b_calibration_entities} == set(range(k))
        and {q_by_entity[e] for e in hidden.b_transfer_entities} == set(range(k))
    )

    accepted = all([
        cardinality_ok,
        balanced_partition_ok,
        identifiable_a,
        identifiable_b,
        nontrivial,
        family_diversity,
        smt_nonisomorphic,
        split_ok,
    ])
    return {
        "accepted": accepted,
        "latent_cardinality": k,
        "latent_cardinality_ok": cardinality_ok,
        "balanced_partition_ok": balanced_partition_ok,
        "latent_state_counts": dict(sorted(q_counts.items())),
        "identifiable": {"A": identifiable_a, "B": identifiable_b},
        "minimum_unique_outputs_per_q": {"A": per_q_a, "B": per_q_b},
        "minimum_unique_outputs_per_action_across_q": {"A": per_action_a, "B": per_action_b, "required": action_q_target},
        "simple_baselines": baseline,
        "operator_families": {"A": sorted(pa.operator_families()), "B": sorted(pb.operator_families())},
        "operator_family_diversity_ok": family_diversity,
        "smt_isomorphism": {
            "isomorphic": iso.isomorphic,
            "solver_status": iso.solver_status,
            "table_digest_a": iso.table_digest_a,
            "table_digest_b": iso.table_digest_b,
        },
        "smt_nonisomorphic_ok": smt_nonisomorphic,
        "b_split_ok": split_ok,
    }
