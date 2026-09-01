from __future__ import annotations

import importlib.metadata

import z3

from .synthesis import (
    BINARY_OPS,
    COMMUTATIVE_OPS,
    DOMAIN_SIZE,
    OP_ACTION,
    OP_CONST_0,
    OP_CONST_7,
    OP_PERMUTE,
    OP_Q,
    OP_ROTL_1,
    OP_ROTL_2,
    ProgramObservation,
    ProgramSearchResult,
    Z3_RLIMIT_PER_INVOCATION,
    _SkeletonProblem,
    _binary_semantics,
    _node_level,
    _or_selector,
    _permute_lookup,
    _rotl_bv,
    assert_frozen_z3_package,
    solver_parameter_manifest_sha256,
)
from .synthesis_v02_runtime import _solve_one_exact_first


class EfficientSkeletonProblem(_SkeletonProblem):
    """Same complete grammar encoding with a cheaper sound commutative symmetry break.

    For every commutative binary node, requiring the left child root selector to be
    <= the right child root selector is sound: any violating tree has an equivalent
    tree obtained by swapping the two children. Equal-root-selector cases are left
    unconstrained. This removes a large 64-point lexicographic Boolean network from
    every binary node without removing any semantic equivalence class.
    """

    def _build_semantic_constraints(self) -> None:
        zero = z3.BitVecVal(0, 3)

        for index in range(self.node_count - 1, -1, -1):
            selector = self.selector[index]
            level = _node_level(index)
            has_children = level < self.max_depth
            left_index = 2 * index + 1 if has_children else None
            right_index = left_index + 1 if has_children else None

            for point_index, (q_value, action_value) in enumerate(self.points):
                result = zero
                result = z3.If(selector == OP_Q, z3.BitVecVal(q_value, 3), result)
                result = z3.If(selector == OP_ACTION, z3.BitVecVal(action_value, 3), result)
                for constant in range(DOMAIN_SIZE):
                    result = z3.If(selector == OP_CONST_0 + constant, z3.BitVecVal(constant, 3), result)

                if has_children:
                    left = self.values[left_index][point_index]
                    right = self.values[right_index][point_index]
                    result = z3.If(selector == OP_ROTL_1, _rotl_bv(left, 1), result)
                    result = z3.If(selector == OP_ROTL_2, _rotl_bv(left, 2), result)
                    result = z3.If(selector == OP_PERMUTE, _permute_lookup(left, self.mapping[index]), result)
                    binary = _binary_semantics(selector, left, right)
                    result = z3.If(_or_selector(selector, BINARY_OPS), binary, result)

                self.constraints.append(self.values[index][point_index] == result)

            if has_children:
                self.constraints.append(
                    z3.Implies(
                        _or_selector(selector, COMMUTATIVE_OPS),
                        self.selector[left_index] <= self.selector[right_index],
                    )
                )


class SMTProgramSearchV02Fast:
    """Authorized bounded syntax-guided synthesis with equivalent lighter encoding."""

    def __init__(self, *, max_depth: int, rlimit: int = Z3_RLIMIT_PER_INVOCATION):
        if not 1 <= max_depth <= 6:
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
        problem = EfficientSkeletonProblem(
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
