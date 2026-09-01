from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import z3

from .ast_schema import (
    AbsDiffExpr,
    AddModExpr,
    BitAndExpr,
    BitOrExpr,
    ConstExpr,
    EqMaskExpr,
    MaxU3Expr,
    MinU3Expr,
    MulModExpr,
    PermutationExpr,
    ProgramSpec,
    RotlExpr,
    TheoryAST,
    VarExpr,
    XorExpr,
)
from .constants import DOMAIN_SIZE, MAX_EXPRESSION_DEPTH
from .theory_eval import evaluate_expr, operator_signature, program_for, variables_used


SYNTHESIZER_VERSION = "EnumerativeSynthesizer-V0.2"
Z3_PACKAGE_VERSION = "5.1.0.0"
Z3_RLIMIT_PER_INVOCATION = 50_000_000
Z3_RANDOM_SEED = 0

# Selector order is frozen in SYNTH_V02_SOLVER_MANIFEST.json and is also the
# canonical AST ordering used by the final deterministic tie-break stage.
OP_Q = 0
OP_ACTION = 1
OP_CONST_0 = 2
OP_CONST_7 = 9
OP_ROTL_1 = 10
OP_ROTL_2 = 11
OP_PERMUTE = 12
OP_ADD_MOD = 13
OP_MUL_MOD = 14
OP_XOR = 15
OP_BIT_AND = 16
OP_BIT_OR = 17
OP_MIN_U3 = 18
OP_MAX_U3 = 19
OP_ABS_DIFF = 20
OP_EQ_MASK = 21
OP_INACTIVE = 22

LEAF_OPS = tuple(range(OP_Q, OP_CONST_7 + 1))
UNARY_OPS = (OP_ROTL_1, OP_ROTL_2, OP_PERMUTE)
BINARY_OPS = tuple(range(OP_ADD_MOD, OP_EQ_MASK + 1))
# Every binary operation in the frozen grammar is commutative on the 3-bit domain.
COMMUTATIVE_OPS = BINARY_OPS


@dataclass(frozen=True)
class ProgramObservation:
    q: int
    action: int
    y: int


@dataclass(frozen=True)
class ProgramCandidate:
    expression: object
    truth_table: tuple[int, ...]
    correct: int
    total: int
    exact_accuracy: float
    node_count: int
    depth: int
    canonical_ast: str


@dataclass(frozen=True)
class ProgramSearchResult:
    candidates: tuple[ProgramCandidate, ...]
    solver_status: str
    solver_reason_unknown: str | None
    sat_checks: int
    rlimit: int
    rlimit_used: int
    objective: tuple[int, int, int] | None
    exhausted: bool
    solver_package_version: str
    solver_internal_version: str
    solver_parameter_manifest_sha256: str


class CandidateSynthesizer(Protocol):
    """Visible-data-only law fitting shared identically by Full and Flat.

    Candidate latent cardinalities and entity assignments must arrive from the LLM.
    A synthesizer may fit only the executable program conditional on those supplied
    assignments; it may never search, merge, split, modify, or compare partitions.
    """

    def synthesize(
        self,
        *,
        paradigm: str,
        observations: tuple[dict, ...],
        candidate_theories: tuple[TheoryAST, ...],
        frozen_a_theory: TheoryAST | None,
        limit: int = 32,
    ) -> tuple[TheoryAST, ...]:
        ...


def _solver_manifest_payload() -> dict:
    return {
        "z3_package_version": Z3_PACKAGE_VERSION,
        "solver_class": "z3.Solver",
        "auto_config": True,
        "random_seed": Z3_RANDOM_SEED,
        "rlimit": Z3_RLIMIT_PER_INVOCATION,
        "timeout": 0,
    }


def solver_parameter_manifest_sha256() -> str:
    payload = json.dumps(_solver_manifest_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def assert_frozen_z3_package() -> None:
    installed = importlib.metadata.version("z3-solver")
    if installed != Z3_PACKAGE_VERSION:
        raise RuntimeError(f"frozen z3-solver version mismatch: expected {Z3_PACKAGE_VERSION}, got {installed}")


def _canonical(expression: object) -> str:
    return json.dumps(expression.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _expression_node_count(expression: object) -> int:
    if expression.kind in {"var", "const"}:
        return 1
    if expression.kind in {"rotl", "permute"}:
        return 1 + _expression_node_count(expression.value)
    return 1 + _expression_node_count(expression.left) + _expression_node_count(expression.right)


def _expression_depth(expression: object) -> int:
    if expression.kind in {"var", "const"}:
        return 1
    if expression.kind in {"rotl", "permute"}:
        return 1 + _expression_depth(expression.value)
    return 1 + max(_expression_depth(expression.left), _expression_depth(expression.right))


def _node_level(index: int) -> int:
    return (index + 1).bit_length()


def _preorder_indices(index: int, node_count: int):
    if index >= node_count:
        return
    yield index
    yield from _preorder_indices(2 * index + 1, node_count)
    yield from _preorder_indices(2 * index + 2, node_count)


def _or_selector(selector, options: tuple[int, ...]):
    return z3.Or(*(selector == option for option in options))


def _rotl_bv(value, shift: int):
    return (value << shift) | z3.LShR(value, 3 - shift)


def _permute_lookup(value, mapping):
    result = mapping[DOMAIN_SIZE - 1]
    for source in range(DOMAIN_SIZE - 2, -1, -1):
        result = z3.If(value == z3.BitVecVal(source, 3), mapping[source], result)
    return result


def _lex_semantics_le(left_values, right_values):
    """Lexicographic unsigned ordering of complete finite child semantics."""

    equal_prefix = z3.BoolVal(True)
    strictly_less_terms = []
    for left, right in zip(left_values, right_values, strict=True):
        strictly_less_terms.append(z3.And(equal_prefix, z3.ULT(left, right)))
        equal_prefix = z3.And(equal_prefix, left == right)
    return z3.Or(*strictly_less_terms, equal_prefix)


def _binary_semantics(selector, left, right):
    zero = z3.BitVecVal(0, 3)
    seven = z3.BitVecVal(7, 3)
    result = zero
    result = z3.If(selector == OP_ADD_MOD, left + right, result)
    result = z3.If(selector == OP_MUL_MOD, left * right, result)
    result = z3.If(selector == OP_XOR, left ^ right, result)
    result = z3.If(selector == OP_BIT_AND, left & right, result)
    result = z3.If(selector == OP_BIT_OR, left | right, result)
    result = z3.If(selector == OP_MIN_U3, z3.If(z3.ULE(left, right), left, right), result)
    result = z3.If(selector == OP_MAX_U3, z3.If(z3.ULE(left, right), right, left), result)
    result = z3.If(
        selector == OP_ABS_DIFF,
        z3.If(z3.ULE(left, right), right - left, left - right),
        result,
    )
    result = z3.If(selector == OP_EQ_MASK, z3.If(left == right, seven, zero), result)
    return result


class _SkeletonProblem:
    """Complete fixed-depth syntax skeleton over the frozen Theory AST grammar."""

    def __init__(
        self,
        *,
        q_cardinality: int,
        latent_name: str,
        action_name: str,
        observations: tuple[ProgramObservation, ...],
        max_depth: int,
    ):
        if not 1 <= q_cardinality <= DOMAIN_SIZE:
            raise ValueError("q_cardinality must fit the finite 3-bit domain")
        if not 1 <= max_depth <= MAX_EXPRESSION_DEPTH:
            raise ValueError("max_depth outside frozen grammar")
        if not observations:
            raise ValueError("at least one visible observation is required")
        for observation in observations:
            if not 0 <= observation.q < q_cardinality:
                raise ValueError("observation q outside supplied cardinality")
            if not 0 <= observation.action < DOMAIN_SIZE or not 0 <= observation.y < DOMAIN_SIZE:
                raise ValueError("observation outside finite domain")

        self.q_cardinality = q_cardinality
        self.latent_name = latent_name
        self.action_name = action_name
        self.observations = observations
        self.max_depth = max_depth
        self.node_count = (1 << max_depth) - 1
        self.points = tuple((q, action) for q in range(q_cardinality) for action in range(DOMAIN_SIZE))
        self.point_index = {point: index for index, point in enumerate(self.points)}

        self.selector = [z3.Int(f"op_{index}") for index in range(self.node_count)]
        self.mapping = [
            [z3.BitVec(f"perm_{index}_{value}", 3) for value in range(DOMAIN_SIZE)]
            for index in range(self.node_count)
        ]
        self.values = [
            [z3.BitVec(f"value_{index}_{point_index}", 3) for point_index in range(len(self.points))]
            for index in range(self.node_count)
        ]
        self.effective_depth = z3.Int("effective_depth")
        self.constraints: list = []

        self._build_structure_constraints()
        self._build_semantic_constraints()

        self.error = z3.Sum(
            *[
                z3.If(
                    self.values[0][self.point_index[(observation.q, observation.action)]]
                    == z3.BitVecVal(observation.y, 3),
                    0,
                    1,
                )
                for observation in observations
            ]
        )
        self.active_nodes = z3.Sum(
            *[z3.If(selector != OP_INACTIVE, 1, 0) for selector in self.selector]
        )

    def _build_structure_constraints(self) -> None:
        self.constraints.append(self.selector[0] != OP_INACTIVE)
        self.constraints.extend((self.effective_depth >= 1, self.effective_depth <= self.max_depth))

        identity_mapping = tuple(z3.BitVecVal(value, 3) for value in range(DOMAIN_SIZE))

        for index, selector in enumerate(self.selector):
            level = _node_level(index)
            self.constraints.append(z3.And(selector >= OP_Q, selector <= OP_INACTIVE))
            if level == self.max_depth:
                self.constraints.append(
                    z3.Or(selector == OP_INACTIVE, z3.And(selector >= OP_Q, selector <= OP_CONST_7))
                )

            active = selector != OP_INACTIVE
            self.constraints.append(self.effective_depth >= z3.If(active, level, 0))

            is_permutation = selector == OP_PERMUTE
            self.constraints.append(z3.Implies(is_permutation, z3.Distinct(*self.mapping[index])))
            for value in range(DOMAIN_SIZE):
                self.constraints.append(
                    z3.Implies(z3.Not(is_permutation), self.mapping[index][value] == identity_mapping[value])
                )

            if level < self.max_depth:
                left_index = 2 * index + 1
                right_index = left_index + 1
                left_active = z3.Or(_or_selector(selector, UNARY_OPS), _or_selector(selector, BINARY_OPS))
                right_active = _or_selector(selector, BINARY_OPS)
                self.constraints.append((self.selector[left_index] != OP_INACTIVE) == left_active)
                self.constraints.append((self.selector[right_index] != OP_INACTIVE) == right_active)

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
                left_index = 2 * index + 1
                right_index = left_index + 1
                self.constraints.append(
                    z3.Implies(
                        _or_selector(selector, COMMUTATIVE_OPS),
                        _lex_semantics_le(self.values[left_index], self.values[right_index]),
                    )
                )

    @property
    def root_truth_table_terms(self):
        return tuple(self.values[0])

    def semantic_block(self, truth_table: tuple[int, ...]):
        if len(truth_table) != len(self.points):
            raise ValueError("truth table length mismatch")
        return z3.Or(
            *[
                term != z3.BitVecVal(value, 3)
                for term, value in zip(self.root_truth_table_terms, truth_table, strict=True)
            ]
        )

    def decode_expression(self, model):
        def decode(index: int):
            selector = model.eval(self.selector[index], model_completion=True).as_long()
            if selector == OP_Q:
                return VarExpr(name=self.latent_name)
            if selector == OP_ACTION:
                return VarExpr(name=self.action_name)
            if OP_CONST_0 <= selector <= OP_CONST_7:
                return ConstExpr(value=selector - OP_CONST_0)

            left_index = 2 * index + 1
            if selector == OP_ROTL_1:
                return RotlExpr(value=decode(left_index), shift=1)
            if selector == OP_ROTL_2:
                return RotlExpr(value=decode(left_index), shift=2)
            if selector == OP_PERMUTE:
                mapping = [
                    model.eval(value, model_completion=True).as_long()
                    for value in self.mapping[index]
                ]
                return PermutationExpr(value=decode(left_index), mapping=mapping)

            right_index = left_index + 1
            left = decode(left_index)
            right = decode(right_index)
            constructors = {
                OP_ADD_MOD: AddModExpr,
                OP_MUL_MOD: MulModExpr,
                OP_XOR: XorExpr,
                OP_BIT_AND: BitAndExpr,
                OP_BIT_OR: BitOrExpr,
                OP_MIN_U3: MinU3Expr,
                OP_MAX_U3: MaxU3Expr,
                OP_ABS_DIFF: AbsDiffExpr,
                OP_EQ_MASK: EqMaskExpr,
            }
            if selector not in constructors:
                raise AssertionError(f"cannot decode selector {selector}")
            return constructors[selector](left=left, right=right)

        return decode(0)

    def candidate_from_model(self, model) -> ProgramCandidate:
        expression = self.decode_expression(model)
        truth_table = tuple(
            evaluate_expr(expression, {self.latent_name: q, self.action_name: action})
            for q, action in self.points
        )
        correct = sum(
            evaluate_expr(
                expression,
                {self.latent_name: observation.q, self.action_name: observation.action},
            )
            == observation.y
            for observation in self.observations
        )
        return ProgramCandidate(
            expression=expression,
            truth_table=truth_table,
            correct=correct,
            total=len(self.observations),
            exact_accuracy=correct / len(self.observations),
            node_count=_expression_node_count(expression),
            depth=_expression_depth(expression),
            canonical_ast=_canonical(expression),
        )

    def assert_model_soundness(self, model) -> None:
        candidate = self.candidate_from_model(model)
        solver_table = tuple(
            model.eval(term, model_completion=True).as_long() for term in self.root_truth_table_terms
        )
        if candidate.truth_table != solver_table:
            raise AssertionError("decoded AST semantics disagree with solver model")
        if candidate.depth > self.max_depth:
            raise AssertionError("decoded AST exceeds bounded skeleton")


def _rlimit_count(statistics) -> int:
    try:
        keys = statistics.keys()
    except Exception:
        return 0
    for key in keys:
        if key == "rlimit count":
            try:
                return int(statistics.get_key_value(key))
            except Exception:
                return 0
    return 0


class _BudgetChecker:
    """Fresh-solver SAT checks sharing one deterministic invocation resource budget."""

    def __init__(self, base_constraints: tuple, rlimit: int):
        self.base_constraints = base_constraints
        self.rlimit = rlimit
        self.remaining = rlimit
        self.used = 0
        self.checks = 0
        self.last_reason_unknown: str | None = None
        self.exhausted = False

    def check(self, fixed_constraints: tuple, extra_constraints: tuple = ()):  # -> (status, model)
        if self.remaining <= 0:
            self.exhausted = True
            self.last_reason_unknown = "cumulative rlimit exhausted"
            return z3.unknown, None

        solver = z3.Solver()
        solver.set(auto_config=True)
        solver.set(random_seed=Z3_RANDOM_SEED)
        solver.set(timeout=0)
        solver.set(rlimit=self.remaining)
        solver.add(*self.base_constraints)
        if fixed_constraints:
            solver.add(*fixed_constraints)
        if extra_constraints:
            solver.add(*extra_constraints)

        self.checks += 1
        status = solver.check()
        consumed = _rlimit_count(solver.statistics())
        if consumed <= 0:
            consumed = 1
        consumed = min(consumed, self.remaining)
        self.used += consumed
        self.remaining -= consumed

        if status == z3.unknown:
            self.last_reason_unknown = solver.reason_unknown()
            if self.remaining <= 0 or "resource" in self.last_reason_unknown.lower():
                self.exhausted = True
            return status, None
        if status == z3.sat:
            return status, solver.model()
        return status, None


def _model_int(model, expression) -> int:
    return model.eval(expression, model_completion=True).as_long()


def _minimize_int(
    checker: _BudgetChecker,
    fixed: list,
    expression,
    *,
    lower: int,
    current_model,
):
    upper = _model_int(current_model, expression)
    best_model = current_model
    low = lower
    high = upper
    while low < high:
        midpoint = (low + high) // 2
        status, model = checker.check(tuple(fixed), (expression <= midpoint,))
        if status == z3.sat:
            best_model = model
            high = min(midpoint, _model_int(model, expression))
        elif status == z3.unsat:
            low = midpoint + 1
        else:
            return best_model, False
    fixed.append(expression == high)
    return best_model, True


def _minimize_bv3(
    checker: _BudgetChecker,
    fixed: list,
    expression,
    *,
    current_model,
):
    upper = current_model.eval(expression, model_completion=True).as_long()
    best_model = current_model
    low = 0
    high = upper
    while low < high:
        midpoint = (low + high) // 2
        status, model = checker.check(
            tuple(fixed),
            (z3.ULE(expression, z3.BitVecVal(midpoint, 3)),),
        )
        if status == z3.sat:
            best_model = model
            high = min(midpoint, model.eval(expression, model_completion=True).as_long())
        elif status == z3.unsat:
            low = midpoint + 1
        else:
            return best_model, False
    fixed.append(expression == z3.BitVecVal(high, 3))
    return best_model, True


def _canonicalize_model(problem: _SkeletonProblem, checker: _BudgetChecker, fixed: list, model):
    """Freeze the lexicographically smallest canonical active AST while budget remains."""

    def visit(index: int, current_model):
        current_model, complete = _minimize_int(
            checker,
            fixed,
            problem.selector[index],
            lower=OP_Q,
            current_model=current_model,
        )
        if not complete:
            return current_model, False

        selector = _model_int(current_model, problem.selector[index])
        if selector == OP_PERMUTE:
            for mapping_value in problem.mapping[index]:
                current_model, complete = _minimize_bv3(
                    checker,
                    fixed,
                    mapping_value,
                    current_model=current_model,
                )
                if not complete:
                    return current_model, False

        if selector in LEAF_OPS:
            return current_model, True

        left_index = 2 * index + 1
        current_model, complete = visit(left_index, current_model)
        if not complete:
            return current_model, False
        if selector in BINARY_OPS:
            current_model, complete = visit(left_index + 1, current_model)
            if not complete:
                return current_model, False
        return current_model, True

    return visit(0, model)


def _solve_one(problem: _SkeletonProblem, *, blocks: tuple, rlimit: int):
    checker = _BudgetChecker(tuple(problem.constraints) + blocks, rlimit)
    fixed: list = []

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


class SMTProgramSearch:
    """Complete bounded syntax-guided constraint synthesis over the frozen grammar."""

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
        candidates: list[ProgramCandidate] = []
        blocks: list = []
        final_reason: str | None = None
        exhausted = False
        final_status = "sat"

        while len(candidates) < limit and remaining > 0:
            model, checker, candidate = _solve_one(problem, blocks=tuple(blocks), rlimit=remaining)
            total_used += checker.used
            total_checks += checker.checks
            remaining = max(0, self.rlimit - total_used)
            if checker.last_reason_unknown is not None:
                final_reason = checker.last_reason_unknown
            exhausted = exhausted or checker.exhausted

            if candidate is None or model is None:
                if checker.last_reason_unknown is not None:
                    final_status = "unknown"
                else:
                    final_status = "unsat" if candidates else "unsat"
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


# Compatibility name retained for repository continuity. V0.2 is not a beam enumerator.
EnumerativeProgramSearch = SMTProgramSearch


class EnumerativeSynthesizer:
    """Fit laws conditional on LLM-supplied partitions; never search partitions."""

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
        ranked_outputs: list[tuple[tuple, TheoryAST]] = []
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
                # Assignments/cardinality/domain/geometry are fixed inputs, never solver variables.
                if latent.model_copy(update={"frozen": True}) != frozen_latent.model_copy(update={"frozen": True}):
                    continue
                latent = frozen_latent

            relevant = tuple(observation for observation in observations if observation.get("paradigm") == paradigm)
            program_observations: list[ProgramObservation] = []
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

            search = SMTProgramSearch(
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

                ephemeral_id = f"T-SYN-{paradigm}-{source_index:02d}-{program_index:02d}"
                theory = source.model_copy(
                    update={
                        "theory_id": ephemeral_id,
                        "latent_variables": [latent],
                        "programs": programs,
                        "status": "candidate",
                        "evidence_experiment_ids": [],
                    }
                )
                rank_key = (
                    -candidate.correct,
                    candidate.node_count,
                    candidate.depth,
                    candidate.canonical_ast,
                    source_index,
                    program_index,
                )
                ranked_outputs.append((rank_key, theory))
                accepted += 1
                if accepted >= programs_per_source:
                    break

        ranked_outputs.sort(key=lambda item: item[0])
        return tuple(theory for _, theory in ranked_outputs[:limit])


class NoSynthesis:
    """Development-only no-op implementation. Not authorized for comparative runs."""

    def synthesize(
        self,
        *,
        paradigm: str,
        observations: tuple[dict, ...],
        candidate_theories: tuple[TheoryAST, ...],
        frozen_a_theory: TheoryAST | None,
        limit: int = 32,
    ) -> tuple[TheoryAST, ...]:
        return tuple(candidate_theories[:limit])
