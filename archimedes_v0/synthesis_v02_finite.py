from __future__ import annotations

import importlib.metadata

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
    RotlExpr,
    VarExpr,
    XorExpr,
)
from .constants import DOMAIN_SIZE, MAX_EXPRESSION_DEPTH
from .synthesis import (
    BINARY_OPS,
    COMMUTATIVE_OPS,
    LEAF_OPS,
    OP_ABS_DIFF,
    OP_ACTION,
    OP_ADD_MOD,
    OP_BIT_AND,
    OP_BIT_OR,
    OP_CONST_0,
    OP_CONST_7,
    OP_EQ_MASK,
    OP_INACTIVE,
    OP_MAX_U3,
    OP_MIN_U3,
    OP_MUL_MOD,
    OP_PERMUTE,
    OP_Q,
    OP_ROTL_1,
    OP_ROTL_2,
    OP_XOR,
    ProgramCandidate,
    ProgramObservation,
    ProgramSearchResult,
    UNARY_OPS,
    Z3_RLIMIT_PER_INVOCATION,
    _BudgetChecker,
    _canonical,
    _expression_depth,
    _expression_node_count,
    _node_level,
    _or_selector,
    assert_frozen_z3_package,
    solver_parameter_manifest_sha256,
)
from .theory_eval import evaluate_expr


def _rotl(value: int, shift: int) -> int:
    return ((value << shift) | (value >> (3 - shift))) & 7


def _binary_value(op: int, left: int, right: int) -> int:
    if op == OP_ADD_MOD:
        return (left + right) % 8
    if op == OP_MUL_MOD:
        return (left * right) % 8
    if op == OP_XOR:
        return left ^ right
    if op == OP_BIT_AND:
        return left & right
    if op == OP_BIT_OR:
        return left | right
    if op == OP_MIN_U3:
        return min(left, right)
    if op == OP_MAX_U3:
        return max(left, right)
    if op == OP_ABS_DIFF:
        return abs(left - right)
    if op == OP_EQ_MASK:
        return 7 if left == right else 0
    raise ValueError(op)


def _finite_function_1(name: str, table: tuple[int, ...]):
    function = z3.Function(name, z3.IntSort(), z3.IntSort())
    constraints = tuple(function(index) == value for index, value in enumerate(table))
    return function, constraints


def _finite_function_2(name: str, table: tuple[tuple[int, ...], ...]):
    function = z3.Function(name, z3.IntSort(), z3.IntSort(), z3.IntSort())
    constraints = tuple(
        function(left, right) == table[left][right]
        for left in range(DOMAIN_SIZE)
        for right in range(DOMAIN_SIZE)
    )
    return function, constraints


class FiniteDomainSkeletonProblem:
    """Complete bounded Theory-AST skeleton using only finite-domain integer semantics.

    The public 3-bit operators are represented extensionally as immutable 8- or
    8x8-value tables. This is logically equivalent to the BitVec encoding but avoids
    mixing bit-vector arithmetic with integer syntax selectors. No operator is given
    a frequency, score, or generator-derived preference.
    """

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
            raise ValueError("q_cardinality must fit finite domain")
        if not 1 <= max_depth <= MAX_EXPRESSION_DEPTH:
            raise ValueError("max_depth outside frozen grammar")
        if not observations:
            raise ValueError("observations required")
        for observation in observations:
            if not 0 <= observation.q < q_cardinality:
                raise ValueError("q outside supplied cardinality")
            if not 0 <= observation.action < 8 or not 0 <= observation.y < 8:
                raise ValueError("observation outside finite domain")

        self.q_cardinality = q_cardinality
        self.latent_name = latent_name
        self.action_name = action_name
        self.observations = observations
        self.max_depth = max_depth
        self.node_count = (1 << max_depth) - 1
        self.points = tuple((q, action) for q in range(q_cardinality) for action in range(8))
        self.point_index = {point: index for index, point in enumerate(self.points)}

        self.selector = [z3.Int(f"fd_op_{index}") for index in range(self.node_count)]
        self.mapping = [
            [z3.Int(f"fd_perm_{index}_{value}") for value in range(8)]
            for index in range(self.node_count)
        ]
        self.values = [
            [z3.Int(f"fd_value_{index}_{point}") for point in range(len(self.points))]
            for index in range(self.node_count)
        ]
        self.effective_depth = z3.Int("fd_effective_depth")
        self.constraints: list = []

        self.rot1, constraints = _finite_function_1("fd_rot1", tuple(_rotl(value, 1) for value in range(8)))
        self.constraints.extend(constraints)
        self.rot2, constraints = _finite_function_1("fd_rot2", tuple(_rotl(value, 2) for value in range(8)))
        self.constraints.extend(constraints)
        self.binary = {}
        for op in BINARY_OPS:
            table = tuple(tuple(_binary_value(op, left, right) for right in range(8)) for left in range(8))
            function, constraints = _finite_function_2(f"fd_binary_{op}", table)
            self.binary[op] = function
            self.constraints.extend(constraints)

        self._build_structure()
        self._build_semantics()

        self.error = z3.Sum(
            *[
                z3.If(
                    self.values[0][self.point_index[(observation.q, observation.action)]] == observation.y,
                    0,
                    1,
                )
                for observation in observations
            ]
        )
        self.active_nodes = z3.Sum(*[z3.If(selector != OP_INACTIVE, 1, 0) for selector in self.selector])

    def _build_structure(self) -> None:
        self.constraints.extend((self.selector[0] != OP_INACTIVE, self.effective_depth >= 1, self.effective_depth <= self.max_depth))

        for index, selector in enumerate(self.selector):
            level = _node_level(index)
            self.constraints.extend((selector >= OP_Q, selector <= OP_INACTIVE))
            if level == self.max_depth:
                self.constraints.append(z3.Or(selector == OP_INACTIVE, z3.And(selector >= OP_Q, selector <= OP_CONST_7)))

            active = selector != OP_INACTIVE
            self.constraints.append(self.effective_depth >= z3.If(active, level, 0))

            is_permutation = selector == OP_PERMUTE
            for value in self.mapping[index]:
                self.constraints.extend((value >= 0, value < 8))
            self.constraints.append(z3.Implies(is_permutation, z3.Distinct(*self.mapping[index])))
            for source in range(8):
                self.constraints.append(z3.Implies(z3.Not(is_permutation), self.mapping[index][source] == source))

            for value in self.values[index]:
                self.constraints.extend((value >= 0, value < 8))

            if level < self.max_depth:
                left = 2 * index + 1
                right = left + 1
                left_active = z3.Or(_or_selector(selector, UNARY_OPS), _or_selector(selector, BINARY_OPS))
                right_active = _or_selector(selector, BINARY_OPS)
                self.constraints.append((self.selector[left] != OP_INACTIVE) == left_active)
                self.constraints.append((self.selector[right] != OP_INACTIVE) == right_active)

    @staticmethod
    def _permute_lookup(value, mapping):
        result = mapping[7]
        for source in range(6, -1, -1):
            result = z3.If(value == source, mapping[source], result)
        return result

    def _build_semantics(self) -> None:
        for index in range(self.node_count - 1, -1, -1):
            selector = self.selector[index]
            level = _node_level(index)
            has_children = level < self.max_depth
            left_index = 2 * index + 1 if has_children else None
            right_index = left_index + 1 if has_children else None

            for point, (q_value, action_value) in enumerate(self.points):
                result = z3.IntVal(0)
                result = z3.If(selector == OP_Q, q_value, result)
                result = z3.If(selector == OP_ACTION, action_value, result)
                for constant in range(8):
                    result = z3.If(selector == OP_CONST_0 + constant, constant, result)

                if has_children:
                    left = self.values[left_index][point]
                    right = self.values[right_index][point]
                    result = z3.If(selector == OP_ROTL_1, self.rot1(left), result)
                    result = z3.If(selector == OP_ROTL_2, self.rot2(left), result)
                    result = z3.If(selector == OP_PERMUTE, self._permute_lookup(left, self.mapping[index]), result)
                    for op in BINARY_OPS:
                        result = z3.If(selector == op, self.binary[op](left, right), result)

                self.constraints.append(self.values[index][point] == result)

            if has_children:
                # Sound partial canonicalization for every commutative operator.
                self.constraints.append(
                    z3.Implies(
                        _or_selector(selector, COMMUTATIVE_OPS),
                        self.selector[left_index] <= self.selector[right_index],
                    )
                )

    @property
    def root_truth_table_terms(self):
        return tuple(self.values[0])

    def exact_constraints(self):
        return tuple(
            self.values[0][self.point_index[(observation.q, observation.action)]] == observation.y
            for observation in self.observations
        )

    def semantic_block(self, truth_table: tuple[int, ...]):
        return z3.Or(*[term != value for term, value in zip(self.root_truth_table_terms, truth_table, strict=True)])

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
                mapping = [model.eval(value, model_completion=True).as_long() for value in self.mapping[index]]
                return PermutationExpr(value=decode(left_index), mapping=mapping)
            right_index = left_index + 1
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
                raise AssertionError(f"invalid active selector {selector}")
            return constructors[selector](left=decode(left_index), right=decode(right_index))
        return decode(0)

    def candidate_from_model(self, model) -> ProgramCandidate:
        expression = self.decode_expression(model)
        truth_table = tuple(
            evaluate_expr(expression, {self.latent_name: q, self.action_name: action})
            for q, action in self.points
        )
        correct = sum(
            evaluate_expr(expression, {self.latent_name: observation.q, self.action_name: observation.action}) == observation.y
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
        solver_table = tuple(model.eval(term, model_completion=True).as_long() for term in self.root_truth_table_terms)
        if candidate.truth_table != solver_table:
            raise AssertionError("decoded AST semantics disagree with finite solver model")


def _minimize_int(checker, fixed: list, expression, *, lower: int, current_model):
    upper = current_model.eval(expression, model_completion=True).as_long()
    best = current_model
    low, high = lower, upper
    while low < high:
        midpoint = (low + high) // 2
        status, model = checker.check(tuple(fixed), (expression <= midpoint,))
        if status == z3.sat:
            best = model
            high = min(midpoint, model.eval(expression, model_completion=True).as_long())
        elif status == z3.unsat:
            low = midpoint + 1
        else:
            return best, False
    fixed.append(expression == high)
    return best, True


def _canonicalize(problem, checker, fixed: list, model):
    def visit(index: int, current):
        current, complete = _minimize_int(checker, fixed, problem.selector[index], lower=OP_Q, current_model=current)
        if not complete:
            return current, False
        selector = current.eval(problem.selector[index], model_completion=True).as_long()
        if selector == OP_PERMUTE:
            for entry in problem.mapping[index]:
                current, complete = _minimize_int(checker, fixed, entry, lower=0, current_model=current)
                if not complete:
                    return current, False
        if selector in LEAF_OPS:
            return current, True
        left = 2 * index + 1
        current, complete = visit(left, current)
        if not complete:
            return current, False
        if selector in BINARY_OPS:
            current, complete = visit(left + 1, current)
        return current, complete
    return visit(0, model)


def _solve_one(problem: FiniteDomainSkeletonProblem, *, blocks: tuple, rlimit: int):
    checker = _BudgetChecker(tuple(problem.constraints) + blocks, rlimit)
    fixed: list = []

    status, model = checker.check((), problem.exact_constraints())
    if status == z3.sat and model is not None:
        problem.assert_model_soundness(model)
        best = model
        fixed.extend(problem.exact_constraints())
    elif status == z3.unsat:
        status, model = checker.check(())
        if status != z3.sat or model is None:
            return None, checker, None
        problem.assert_model_soundness(model)
        best = model
        best, complete = _minimize_int(checker, fixed, problem.error, lower=0, current_model=best)
        if not complete:
            return best, checker, problem.candidate_from_model(best)
    else:
        return None, checker, None

    best, complete = _minimize_int(checker, fixed, problem.active_nodes, lower=1, current_model=best)
    if not complete:
        return best, checker, problem.candidate_from_model(best)
    best, complete = _minimize_int(checker, fixed, problem.effective_depth, lower=1, current_model=best)
    if not complete:
        return best, checker, problem.candidate_from_model(best)
    best, _ = _canonicalize(problem, checker, fixed, best)
    problem.assert_model_soundness(best)
    return best, checker, problem.candidate_from_model(best)


class SMTProgramSearchV02Finite:
    def __init__(self, *, max_depth: int, rlimit: int = Z3_RLIMIT_PER_INVOCATION):
        self.max_depth = max_depth
        self.rlimit = rlimit

    def search(self, *, q_cardinality: int, latent_name: str, action_name: str, observations: tuple[ProgramObservation, ...], limit: int = 32) -> ProgramSearchResult:
        assert_frozen_z3_package()
        problem = FiniteDomainSkeletonProblem(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=self.max_depth,
        )
        remaining = self.rlimit
        total_used = total_checks = 0
        candidates = []
        blocks = []
        final_reason = None
        exhausted = False
        status_name = "sat"

        while len(candidates) < limit and remaining > 0:
            model, checker, candidate = _solve_one(problem, blocks=tuple(blocks), rlimit=remaining)
            total_used += checker.used
            total_checks += checker.checks
            remaining = max(0, self.rlimit - total_used)
            final_reason = checker.last_reason_unknown or final_reason
            exhausted = exhausted or checker.exhausted
            if candidate is None or model is None:
                status_name = "unknown" if checker.last_reason_unknown else "unsat"
                break
            candidates.append(candidate)
            blocks.append(problem.semantic_block(candidate.truth_table))
            if checker.exhausted:
                status_name = "resource_exhausted_with_candidate"
                break

        objective = None
        if candidates:
            first = candidates[0]
            objective = (first.total - first.correct, first.node_count, first.depth)
        return ProgramSearchResult(
            candidates=tuple(candidates),
            solver_status=status_name,
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
