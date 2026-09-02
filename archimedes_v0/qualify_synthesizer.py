from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from . import (
    synthesis,
    synthesis_v02_cegis,
    synthesis_v02_cegis_feasiblefirst,
    synthesis_v02_cegis_final,
    synthesis_v02_cegis_hardened,
    synthesis_v02_cegis_lexscore,
    synthesis_v02_cegis_partialperm,
    synthesis_v02_runtime,
)
from .qualification import (
    QUALIFICATION_CORPUS_SIZE,
    QUALIFICATION_EXPECTED_DIGEST,
    QUALIFICATION_MAX_DEPTH,
    generate_qualification_corpus,
    qualification_corpus_digest,
)
from .synthesis import (
    ProgramObservation,
    SYNTHESIZER_VERSION,
    Z3_RLIMIT_PER_INVOCATION,
    solver_parameter_manifest_sha256,
)
from .synthesis_v02_cegis_final import SMTProgramSearchV02CEGIS
from .theory_eval import evaluate_expr


def _runtime_source_sha256() -> str:
    """Freeze the complete trusted V0.2 synthesis implementation.

    The qualification must hash the final bound search implementation, including
    every semantics-preserving prequalification hardening module that contributes
    runtime bindings.  This is provenance only; it does not alter synthesis.
    """

    modules = (
        ("synthesis.py", Path(synthesis.__file__)),
        ("synthesis_v02_cegis.py", Path(synthesis_v02_cegis.__file__)),
        ("synthesis_v02_cegis_hardened.py", Path(synthesis_v02_cegis_hardened.__file__)),
        ("synthesis_v02_cegis_lexscore.py", Path(synthesis_v02_cegis_lexscore.__file__)),
        ("synthesis_v02_cegis_partialperm.py", Path(synthesis_v02_cegis_partialperm.__file__)),
        ("synthesis_v02_cegis_feasiblefirst.py", Path(synthesis_v02_cegis_feasiblefirst.__file__)),
        ("synthesis_v02_cegis_final.py", Path(synthesis_v02_cegis_final.__file__)),
        ("synthesis_v02_runtime.py", Path(synthesis_v02_runtime.__file__)),
    )
    digest = hashlib.sha256()
    for name, path in modules:
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _target_observations(expression) -> tuple[ProgramObservation, ...]:
    return tuple(
        ProgramObservation(q=q, action=action, y=evaluate_expr(expression, {"q": q, "a": action}))
        for q in range(8)
        for action in range(8)
    )


def qualify_range(*, start: int, stop: int) -> dict:
    if not 0 <= start < stop <= QUALIFICATION_CORPUS_SIZE:
        raise ValueError("qualification range outside frozen corpus")

    corpus = generate_qualification_corpus()
    digest = qualification_corpus_digest(corpus)
    if digest != QUALIFICATION_EXPECTED_DIGEST:
        raise RuntimeError("qualification corpus digest mismatch")

    began = time.monotonic()
    recovered = 0
    exhausted = 0
    unknown = 0
    exceptions = 0
    sat_checks = 0
    rlimit_used = 0
    package_version = None
    internal_version = None

    # Aggregate-only output prevents individual failed items from becoming a tuning signal.
    for index in range(start, stop):
        observations = _target_observations(corpus[index])
        try:
            result = SMTProgramSearchV02CEGIS(
                max_depth=QUALIFICATION_MAX_DEPTH,
                rlimit=Z3_RLIMIT_PER_INVOCATION,
            ).search(
                q_cardinality=8,
                latent_name="q",
                action_name="a",
                observations=observations,
                limit=1,
            )
            success = bool(result.candidates and result.candidates[0].exact_accuracy == 1.0)
            recovered += int(success)
            exhausted += int(result.exhausted)
            unknown += int(result.solver_status == "unknown")
            sat_checks += result.sat_checks
            rlimit_used += result.rlimit_used
            package_version = result.solver_package_version
            internal_version = result.solver_internal_version
        except Exception:
            # Exceptions are qualification failures; item identity and exception text stay hidden.
            exceptions += 1

    elapsed = time.monotonic() - began
    count = stop - start
    return {
        "synthesizer_version": SYNTHESIZER_VERSION,
        "synthesis_algorithm": "deterministic_cegis_v02_exact_first",
        "qualification_corpus_digest": digest,
        "start": start,
        "stop": stop,
        "count": count,
        "recovered": recovered,
        "recovery_rate": recovered / count,
        "resource_exhausted_count": exhausted,
        "unknown_count": unknown,
        "exception_count": exceptions,
        "sat_checks_total": sat_checks,
        "rlimit_per_invocation": Z3_RLIMIT_PER_INVOCATION,
        "rlimit_used_total": rlimit_used,
        "solver_package_version": package_version,
        "solver_internal_version": internal_version,
        "solver_parameter_manifest_sha256": solver_parameter_manifest_sha256(),
        "synthesizer_source_sha256": _runtime_source_sha256(),
        "elapsed_seconds": elapsed,
        "uses_hidden_world_generator": False,
        "qualification_target": "complete 8x8 observational equivalence",
        "qualification_max_depth": QUALIFICATION_MAX_DEPTH,
        "individual_failure_details_emitted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one-shot benchmark-independent V0.2 synthesizer qualification")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=QUALIFICATION_CORPUS_SIZE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = qualify_range(start=args.start, stop=args.stop)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
