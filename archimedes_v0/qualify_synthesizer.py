from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .qualification import (
    QUALIFICATION_CORPUS_SIZE,
    QUALIFICATION_EXPECTED_DIGEST,
    generate_qualification_corpus,
    qualification_corpus_digest,
)
from .synthesis import EnumerativeProgramSearch, ProgramObservation, SYNTHESIZER_VERSION
from .theory_eval import evaluate_expr


def _target_observations(expression) -> tuple[ProgramObservation, ...]:
    return tuple(
        ProgramObservation(q=q, action=action, y=evaluate_expr(expression, {"q": q, "a": action}))
        for q in range(8)
        for action in range(8)
    )


def qualify_range(*, ceiling: int, start: int, stop: int) -> dict:
    if not 0 <= start < stop <= QUALIFICATION_CORPUS_SIZE:
        raise ValueError("qualification range outside frozen corpus")

    corpus = generate_qualification_corpus()
    digest = qualification_corpus_digest(corpus)
    if digest != QUALIFICATION_EXPECTED_DIGEST:
        raise RuntimeError("qualification corpus digest mismatch")

    began = time.monotonic()
    recovered = 0
    inspected: list[int] = []
    beam_widths: set[int] = set()

    for index in range(start, stop):
        observations = _target_observations(corpus[index])
        result = EnumerativeProgramSearch(search_ceiling=ceiling).search(
            q_cardinality=8,
            latent_name="q",
            action_name="a",
            observations=observations,
            limit=1,
        )
        success = bool(result.candidates and result.candidates[0].exact_accuracy == 1.0)
        recovered += int(success)
        inspected.append(result.semantic_expressions_inspected)
        beam_widths.add(result.beam_width)

    elapsed = time.monotonic() - began
    count = stop - start
    return {
        "synthesizer_version": SYNTHESIZER_VERSION,
        "qualification_corpus_digest": digest,
        "ceiling": ceiling,
        "start": start,
        "stop": stop,
        "count": count,
        "recovered": recovered,
        "recovery_rate": recovered / count,
        "semantic_expressions_inspected_mean": sum(inspected) / len(inspected),
        "semantic_expressions_inspected_max": max(inspected),
        "beam_widths": sorted(beam_widths),
        "elapsed_seconds": elapsed,
        "uses_hidden_world_generator": False,
        "qualification_target": "complete 8x8 observational equivalence",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark-independent synthesizer qualification")
    parser.add_argument("--ceiling", type=int, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=QUALIFICATION_CORPUS_SIZE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = qualify_range(ceiling=args.ceiling, start=args.start, stop=args.stop)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
