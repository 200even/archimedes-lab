from __future__ import annotations

import importlib.metadata
import math

import z3

from .ast_schema import ProgramSpec, TheoryAST
from .constants import MAX_EXPRESSION_DEPTH
from .synthesis import (
    OP_Q,
    ProgramObservation,
    ProgramSearchResult,
    SYNTHESIZER_VERSION,
    Z3_RLIMIT_PER_INVOCATION,
    _BudgetChecker,
    _SkeletonProblem,
    _canonicalize_model,
    _minimize_int,
    assert_frozen_z3_package,
    solver_parameter_manifest_sha256,
)
from .synthesis_v02_cegis import SMTProgramSearchV02CEGIS
from .theory_eval import operator_signature, program_for, variables_used


def _exact_observation_constraints(problem: _SkeletonProblem) -> tuple:
    """Logical strengthening of Hamming error == 0.

    A sum of mismatch indicators equal to zero is logically equivalent to all
    root-output equalities, but the direct equalities propagate more strongly
    through the original monolithic syntax skeleton. This implementation remains
    in-tree as the pre-CEGIS reference encoding only.
    """

    return tuple(
        problem.values[0][problem.point_index[(observation.q, observation.action)]]
        == z3.BitVecVal(observation.y, 3)
        for observation in problem.observations
    )


def _solve_one_exact_first(problem: _SkeletonProblem, *, blocks: tuple, rlimit: int):
    """Pre-CEGIS reference optimizer retained for reproducibility."""

    checker = _BudgetChecker(tuple(problem.constraints) + blocks, rlimit)
    fixed: list = []
    exact_constraints = _exact_observation_constraints(problem)

    status, model = checker.check((), exact_constraints)
    if status == z3.sat and model is not None:
        problem.assert_model_soundness(model)
        best_model = model
        fixed.extend(exact_constraints)
    elif status == z3.unsat:
        status, model = checker.check(())
        if status != z3.sat or model is None:
            return None, checker, None
        problem.assert_model_soundness(model)
        best_model = model
        best_model, complete = _minimize_int(
            checker,
            fixed,
            problem.error,
            lower=0,
            current_model=best_model,
        )
        problem.assert_model_soundness(best_model)
        if not complete:
            return best_model, checker, problem.candidate_from_model(best_model)
    else:
        return None, checker, None

    best_model, complete = _minimize_int(
        checker,
        fixed,
        problem.active_nodes,
        lower=1,
        current_model=best_model,
    )
    problem.assert_model_soundness(best_model)
    if not complete:
        return best_model, checker, problem.candidate_from_model(best_model)

    best_model, complete = _minimize_int(
        checker,
        fixed,
        problem.effective_depth,
        lower=1,
        current_model=best_model,
    )
    problem.assert_model_soundness(best_model)
    if not complete:
        return best_model, checker, problem.candidate_from_model(best_model)

    best_model, _ = _canonicalize_model(problem, checker, fixed, best_model)
    problem.assert_model_soundness(best_model)
    return best_model, checker, problem.candidate_from_model(best_model)


class SMTProgramSearchV02:
    """Pre-CEGIS monolithic V0.2 reference implementation.

    The public V0.2 runtime alias below points to `SMTProgramSearchV02CEGIS`.
    This class remains available only so the preregistered implementation history
    can be reproduced; it is not used by qualification or agent orchestration.
    """

    def __init__(
        self,
        *,
        max_depth: int = MAX_EXPRESSION_DEPTH,
        rlimit: int = Z3_RLIMIT_PER_INVOCATION,
    ):
        if not 1 <= max_depth <= MAX_EXPRESSION_DEPTH:
            raise ValueError("max_depth outside frozen grammar")
        if rlimit <= 0:
            raise ValueError("rlimit must be positive")
        self.max_depth = max_depth
        self.rlimit = rlimit

    def search(
        self,
        *,
        q_cardinality: int,
        latent_name: str,
        action_name: str,
        observations: tuple[ProgramObservation, ...],
        limit: int = 32,
    ) -> ProgramSearchResult:
        assert_frozen_z3_package()
        if limit < 1:
            return ProgramSearchResult(
                candidates=(),
                solver_status="not_run",
                solver_reason_unknown=None,
                sat_checks=0,
                rlimit=self.rlimit,
                rlimit_used=0,
                objective=None,
                exhausted=False,
                solver_package_version=importlib.metadata.version("z3-solver"),
                solver_internal_version=z3.get_version_string(),
                solver_parameter_manifest_sha256=solver_parameter_manifest_sha256(),
            )

        problem = _SkeletonProblem(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=self.max_depth,
        )

        remaining = self.rlimit
        total_used = 0
        total_checks = 0
        candidates = []
        blocks = []
        final_reason = None
        exhausted = False
        final_status = "sat"

        while len(candidates) < limit and remaining > 0:
            model, checker, candidate = _solve_one_exact_first(
                problem,
                blocks=tuple(blocks),
                rlimit=remaining,
            )
            total_used += checker.used
            total_checks += checker.checks
            remaining = max(0, self.rlimit - total_used)
            if checker.last_reason_unknown is not None:
                final_reason = checker.last_reason_unknown
            exhausted = exhausted or checker.exhausted

            if candidate is None or model is None:
                final_status = "unknown" if checker.last_reason_unknown is not None else "unsat"
                break

            candidates.append(candidate)
            blocks.append(problem.semantic_block(candidate.truth_table))
            if checker.exhausted:
                final_status = "resource_exhausted_with_candidate"
                break

        objective = None
        if candidates:
            first = candidates[0]
            objective = (first.total - first.correct, first.node_count, first.depth)
            if final_status == "unsat":
                final_status = "sat"
        if remaining <= 0 and len(candidates) < limit:
            exhausted = True
            final_status = "resource_exhausted_with_candidate" if candidates else "unknown"
            final_reason = final_reason or "cumulative rlimit exhausted"

        return ProgramSearchResult(
            candidates=tuple(candidates),
            solver_status=final_status,
            solver_reason_unknown=final_reason,
            sat_checks=total_checks,
            rlimit=self.rlimit,
            rlimit_used=min(total_used, self.rlimit),
            objective=objective,
            exhausted=exhausted,
            solver_package_version=importlib.metadata.version("z3-solver"),
            solver_internal_version=z3.get_version_string(),
            solver_parameter_manifest_sha256=solver_parameter_manifest_sha256(),
        )


class EnumerativeSynthesizerV02:
    """Law fitter conditional on the LLM-supplied latent representation."""

    def __init__(self, *, max_depth: int = MAX_EXPRESSION_DEPTH):
        if not 1 <= max_depth <= MAX_EXPRESSION_DEPTH:
            raise ValueError("max_depth outside frozen grammar")
        self.max_depth = max_depth
        self.solver_rlimit = Z3_RLIMIT_PER_INVOCATION

    def synthesize(
        self,
        *,
        paradigm: str,
        observations: tuple[dict, ...],
        candidate_theories: tuple[TheoryAST, ...],
        frozen_a_theory: TheoryAST | None,
        limit: int = 32,
    ) -> tuple[TheoryAST, ...]:
        if paradigm not in {"A", "B"}:
            raise ValueError("paradigm must be A or B")
        if limit < 1:
            return ()

        action_name = "x" if paradigm == "A" else "u"
        ranked_outputs = []
        source_count = max(1, len(candidate_theories))
        programs_per_source = max(1, math.ceil(limit / source_count))

        for source_index, source in enumerate(candidate_theories):
            if len(source.latent_variables) != 1:
                continue
            latent = source.latent_variables[0]

            if paradigm == "B":
                if frozen_a_theory is None or len(frozen_a_theory.latent_variables) != 1:
                    continue
                frozen_latent = frozen_a_theory.latent_variables[0]
                if latent.model_copy(update={"frozen": True}) != frozen_latent.model_copy(update={"frozen": True}):
                    continue
                latent = frozen_latent

            relevant = tuple(observation for observation in observations if observation.get("paradigm") == paradigm)
            program_observations = []
            valid = True
            for observation in relevant:
                entity_id = observation["entity_id"]
                if entity_id not in latent.assignments:
                    valid = False
                    break
                program_observations.append(
                    ProgramObservation(
                        q=latent.assignments[entity_id],
                        action=observation["action_value"],
                        y=observation["y"],
                    )
                )
            if not valid or not program_observations:
                continue

            search = SMTProgramSearchV02CEGIS(
                max_depth=self.max_depth,
                rlimit=self.solver_rlimit,
            ).search(
                q_cardinality=latent.cardinality,
                latent_name=latent.name,
                action_name=action_name,
                observations=tuple(program_observations),
                limit=max(programs_per_source * 4, programs_per_source),
            )

            accepted = 0
            for program_index, candidate in enumerate(search.candidates):
                used = variables_used(candidate.expression)
                if latent.name not in used or action_name not in used:
                    continue
                if not operator_signature(candidate.expression):
                    continue

                if paradigm == "A":
                    programs = [ProgramSpec(paradigm="A", expression=candidate.expression)]
                else:
                    assert frozen_a_theory is not None
                    programs = [
                        program_for(frozen_a_theory, "A"),
                        ProgramSpec(paradigm="B", expression=candidate.expression),
                    ]

                theory = source.model_copy(
                    update={
                        "theory_id": f"T-SYN-{paradigm}-{source_index:02d}-{program_index:02d}",
                        "latent_variables": [latent],
                        "programs": programs,
                        "status": "candidate",
                        "evidence_experiment_ids": [],
                    }
                )
                ranked_outputs.append(
                    (
                        (
                            -candidate.correct,
                            candidate.node_count,
                            candidate.depth,
                            candidate.canonical_ast,
                            source_index,
                            program_index,
                        ),
                        theory,
                    )
                )
                accepted += 1
                if accepted >= programs_per_source:
                    break

        ranked_outputs.sort(key=lambda item: item[0])
        return tuple(theory for _, theory in ranked_outputs[:limit])


SMTProgramSearch = SMTProgramSearchV02CEGIS
EnumerativeSynthesizer = EnumerativeSynthesizerV02
