from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Iterable


CAUSAL_WORLDS_PER_ARM = 100
NULL_WORLDS_FULL = 100
PRIMARY_ALPHA = 0.05
PRIMARY_MIN_MEAN_ADVANTAGE = 0.05
PERMUTATION_DRAWS = 100_000
PERMUTATION_SEED = 20260830


@dataclass(frozen=True)
class PrimaryComparison:
    n_worlds: int
    mean_full: float
    mean_flat: float
    mean_difference: float
    p_value_one_sided: float
    passes_significance: bool
    passes_minimum_effect: bool
    primary_success: bool


def _as_scores(values: Iterable[float]) -> tuple[float, ...]:
    scores = tuple(float(value) for value in values)
    if any(value < 0.0 or value > 1.0 for value in scores):
        raise ValueError("world scores must be in [0, 1]")
    return scores


def paired_sign_flip_test(
    full_scores: Iterable[float],
    flat_scores: Iterable[float],
    *,
    draws: int = PERMUTATION_DRAWS,
    seed: int = PERMUTATION_SEED,
) -> PrimaryComparison:
    """Preregistered paired randomization test on world-level D4 accuracy.

    A world that abstains, fails a gate, or otherwise never reaches transfer is
    scored as 0 by the caller. The world, not an individual transfer intervention,
    is the experimental unit.
    """
    full = _as_scores(full_scores)
    flat = _as_scores(flat_scores)
    if len(full) != len(flat) or not full:
        raise ValueError("paired arms must contain the same nonzero number of worlds")
    if draws < 1:
        raise ValueError("draws must be positive")

    diffs = tuple(a - b for a, b in zip(full, flat, strict=True))
    observed = sum(diffs) / len(diffs)
    rng = random.Random(seed)
    extreme = 0
    for _ in range(draws):
        permuted = sum((1 if rng.getrandbits(1) else -1) * d for d in diffs) / len(diffs)
        if permuted >= observed:
            extreme += 1
    p_value = (extreme + 1) / (draws + 1)
    significant = p_value < PRIMARY_ALPHA
    effect = observed >= PRIMARY_MIN_MEAN_ADVANTAGE
    return PrimaryComparison(
        n_worlds=len(full),
        mean_full=sum(full) / len(full),
        mean_flat=sum(flat) / len(flat),
        mean_difference=observed,
        p_value_one_sided=p_value,
        passes_significance=significant,
        passes_minimum_effect=effect,
        primary_success=significant and effect,
    )


def null_false_positive_rate(concept_declarations: Iterable[bool]) -> float:
    declarations = tuple(bool(value) for value in concept_declarations)
    if not declarations:
        raise ValueError("at least one Null-world result is required")
    return sum(declarations) / len(declarations)


def evaluate_registered_primary(full_scores: Iterable[float], flat_scores: Iterable[float]) -> PrimaryComparison:
    full = tuple(full_scores)
    flat = tuple(flat_scores)
    if len(full) != CAUSAL_WORLDS_PER_ARM or len(flat) != CAUSAL_WORLDS_PER_ARM:
        raise ValueError(f"registered primary requires exactly {CAUSAL_WORLDS_PER_ARM} paired worlds")
    return paired_sign_flip_test(full, flat)


def hallucination_kill(concept_declarations: Iterable[bool]) -> bool:
    declarations = tuple(concept_declarations)
    if len(declarations) != NULL_WORLDS_FULL:
        raise ValueError(f"registered Null analysis requires exactly {NULL_WORLDS_FULL} worlds")
    return null_false_positive_rate(declarations) >= 0.05
