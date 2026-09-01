"""Prequalification hardening for the authorized V0.2 CEGIS synthesizer.

This module makes two general, benchmark-independent engineering corrections found
on independent synthetic fixtures before the one-shot qualification run:

1. every synthesis invocation receives a fresh Z3 Context, isolating solver/model
   state between replayed invocations while preserving the frozen solver version,
   parameters, grammar, objective hierarchy, and cumulative rlimit;
2. permutation tables are left unconstrained when a node is not a permutation,
   and SAT models are decoded with a canonical completion of permutation entries
   that were unobserved by the current CEGIS working set W.  The completion is the
   lexicographically smallest bijection preserving the candidate's semantics on W.

Neither correction changes the semantic hypothesis class.  They remove irrelevant
solver degrees of freedom that otherwise consume resource and can make the CEGIS
counterexample path depend on arbitrary model completion.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass

import z3

from . import synthesis_v02_cegis as _cegis
from .ast_schema import (
    AbsDiffExpr,
    AddModExpr,
    BitAndExpr,
    BitOrExpr,
    EqMaskExpr,
    MaxU3Expr,
    MinU3Expr,
    MulModExpr,
    PermutationExpr,
    RotlExpr,
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
    UNARY_OPS,
    ProgramObservation,
    Z3_RANDOM_SEED,
    _SkeletonProblem,
    _node_level,
    _or_selector,
    _rlimit_count,
)
from .theory_eval import evaluate_expr


_ACTIVE_CONTEXT: contextvars.ContextVar[z3.Context | None] = contextvars.ContextVar(
    "archimedes_v02_z3_context", default=None
)


def _ctx() -> z3.Context:
    ctx = _ACTIVE_CONTEXT.get()
    if ctx is None:
        raise RuntimeError("V0.2 CEGIS Z3 context has not been initialized")
    return ctx


def _bv(value: int, ctx: z3.Context):
    return z3.BitVecVal(value, 3, ctx=ctx)


def _permute_lookup_ctx(value, mapping, ctx: z3.Context):
    result = mapping[DOMAIN_SIZE - 1]
    for source in range(DOMAIN_SIZE - 2, -1, -1):
        result = z3.If(value == _bv(source, ctx), mapping[source], result)
    return result


def _lex_semantics_le_ctx(left_values, right_values, ctx: z3.Context):
    equal_prefix = z3.BoolVal(True, ctx=ctx)
    strictly_less_terms = []
    for left, right in zip(left_values, right_values, strict=True):
        strictly_less_terms.append(z3.And(equal_prefix, z3.ULT(left, right)))
        equal_prefix = z3.And(equal_prefix, left == right)
    return z3.Or(*strictly_less_terms, equal_prefix)


def _binary_semantics_ctx(selector, left, right, ctx: z3.Context):
    zero = _bv(0, ctx)
    seven = _bv(7, ctx)
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


class _IsolatedWorkingSetProblem(_SkeletonProblem):
    """Reduced-W syntax/semantic problem in the invocation-local Z3 Context."""

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
            raise ValueError("CEGIS working set must be non-empty")
        for observation in observations:
            if not 0 <= observation.q < q_cardinality:
                raise ValueError("observation q outside supplied cardinality")
            if not 0 <= observation.action < DOMAIN_SIZE or not 0 <= observation.y < DOMAIN_SIZE:
                raise ValueError("observation outside finite domain")

        self.ctx = _ctx()
        self.q_cardinality = q_cardinality
        self.latent_name = latent_name
        self.action_name = action_name
        self.observations = observations
        self.max_depth = max_depth
        self.node_count = (1 << max_depth) - 1

        points = []
        seen = set()
        for observation in observations:
            point = (observation.q, observation.action)
            if point not in seen:
                seen.add(point)
                points.append(point)
        self.points = tuple(points)
        self.point_index = {point: index for index, point in enumerate(self.points)}

        self.selector = [z3.Int(f"op_{index}", ctx=self.ctx) for index in range(self.node_count)]
        self.mapping = [
            [z3.BitVec(f"perm_{index}_{value}", 3, ctx=self.ctx) for value in range(DOMAIN_SIZE)]
            for index in range(self.node_count)
        ]
        self.values = [
            [
                z3.BitVec(f"value_{index}_{point_index}", 3, ctx=self.ctx)
                for point_index in range(len(self.points))
            ]
            for index in range(self.node_count)
        ]
        self.effective_depth = z3.Int("effective_depth", ctx=self.ctx)
        self.constraints: list = []

        self._build_structure_constraints_isolated()
        self._build_semantic_constraints_isolated()

        self.error = z3.Sum(
            *[
                z3.If(
                    self.values[0][self.point_index[(observation.q, observation.action)]]
                    == _bv(observation.y, self.ctx),
                    0,
                    1,
                )
                for observation in observations
            ]
        )
        self.active_nodes = z3.Sum(
            *[z3.If(selector != OP_INACTIVE, 1, 0) for selector in self.selector]
        )

    def _build_structure_constraints_isolated(self) -> None:
        self.constraints.append(self.selector[0] != OP_INACTIVE)
        self.constraints.extend((self.effective_depth >= 1, self.effective_depth <= self.max_depth))

        for index, selector in enumerate(self.selector):
            level = _node_level(index)
            self.constraints.append(z3.And(selector >= OP_Q, selector <= OP_INACTIVE))
            if level == self.max_depth:
                self.constraints.append(
                    z3.Or(selector == OP_INACTIVE, z3.And(selector >= OP_Q, selector <= OP_CONST_7))
                )

            active = selector != OP_INACTIVE
            self.constraints.append(self.effective_depth >= z3.If(active, level, 0))

            # Mapping entries are semantically dead unless the node is PERMUTE.
            # Leaving them unconstrained in all other cases removes irrelevant
            # equalities without adding or removing any executable AST semantics.
            self.constraints.append(
                z3.Implies(selector == OP_PERMUTE, z3.Distinct(*self.mapping[index]))
            )

            if level < self.max_depth:
                left_index = 2 * index + 1
                right_index = left_index + 1
                left_active = z3.Or(_or_selector(selector, UNARY_OPS), _or_selector(selector, BINARY_OPS))
                right_active = _or_selector(selector, BINARY_OPS)
                self.constraints.append((self.selector[left_index] != OP_INACTIVE) == left_active)
                self.constraints.append((self.selector[right_index] != OP_INACTIVE) == right_active)

    def _build_semantic_constraints_isolated(self) -> None:
        zero = _bv(0, self.ctx)

        for index in range(self.node_count - 1, -1, -1):
            selector = self.selector[index]
            level = _node_level(index)
            has_children = level < self.max_depth
            left_index = 2 * index + 1 if has_children else None
            right_index = left_index + 1 if has_children else None

            for point_index, (q_value, action_value) in enumerate(self.points):
                result = zero
                result = z3.If(selector == OP_Q, _bv(q_value, self.ctx), result)
                result = z3.If(selector == OP_ACTION, _bv(action_value, self.ctx), result)
                for constant in range(DOMAIN_SIZE):
                    result = z3.If(selector == OP_CONST_0 + constant, _bv(constant, self.ctx), result)

                if has_children:
                    left = self.values[left_index][point_index]
                    right = self.values[right_index][point_index]
                    result = z3.If(selector == OP_ROTL_1, (left << 1) | z3.LShR(left, 2), result)
                    result = z3.If(selector == OP_ROTL_2, (left << 2) | z3.LShR(left, 1), result)
                    result = z3.If(
                        selector == OP_PERMUTE,
                        _permute_lookup_ctx(left, self.mapping[index], self.ctx),
                        result,
                    )
                    binary = _binary_semantics_ctx(selector, left, right, self.ctx)
                    result = z3.If(_or_selector(selector, BINARY_OPS), binary, result)

                self.constraints.append(self.values[index][point_index] == result)

            if has_children:
                left_index = 2 * index + 1
                right_index = left_index + 1
                self.constraints.append(
                    z3.Implies(
                        _or_selector(selector, COMMUTATIVE_OPS),
                        _lex_semantics_le_ctx(
                            self.values[left_index], self.values[right_index], self.ctx
                        ),
                    )
                )


@dataclass
class _IsolatedCumulativeBudget:
    """Single cumulative rlimit inside one fresh invocation-local Z3 Context."""

    limit: int
    remaining: int
    ctx: z3.Context
    used: int = 0
    checks: int = 0
    exhausted: bool = False
    last_reason_unknown: str | None = None

    @classmethod
    def create(cls, limit: int) -> "_IsolatedCumulativeBudget":
        ctx = z3.Context()
        _ACTIVE_CONTEXT.set(ctx)
        return cls(limit=limit, remaining=limit, ctx=ctx)

    def check(self, base_constraints: tuple, extra_constraints: tuple = ()):
        if self.remaining <= 0:
            self.exhausted = True
            self.last_reason_unknown = "cumulative rlimit exhausted"
            return z3.unknown, None

        solver = z3.Solver(ctx=self.ctx)
        solver.set(auto_config=True)
        solver.set(random_seed=Z3_RANDOM_SEED)
        solver.set(timeout=0)
        solver.set(rlimit=self.remaining)
        solver.add(*base_constraints)
        if extra_constraints:
            solver.add(*extra_constraints)

        before = _rlimit_count(solver.statistics())
        self.checks += 1
        status = solver.check()
        after = _rlimit_count(solver.statistics())
        consumed = max(1, after - before)
        consumed = min(consumed, self.remaining)
        self.used += consumed
        self.remaining -= consumed

        if status == z3.unknown:
            self.last_reason_unknown = solver.reason_unknown()
            self.exhausted = True
            return status, None
        if status == z3.sat:
            return status, solver.model()
        return status, None


def _ast_block_ctx(problem, encoded):
    terms = [
        problem.selector[index] != selector
        for index, selector in enumerate(encoded.selectors)
    ]
    for index, selector in enumerate(encoded.selectors):
        if selector == OP_PERMUTE:
            for offset, value in enumerate(encoded.mappings[index]):
                terms.append(problem.mapping[index][offset] != _bv(value, problem.ctx))
    return z3.Or(*terms)


def _extra_constraints_ctx(
    problem,
    *,
    error_bound: int,
    node_bound: int | None,
    depth_bound: int | None,
    fixed_selectors: dict[int, int],
    fixed_mappings: dict[tuple[int, int], int],
    selector_upper: tuple[int, int] | None,
    mapping_upper: tuple[int, int, int] | None,
    blocks: tuple,
) -> tuple:
    constraints = [problem.error <= error_bound]
    if node_bound is not None:
        constraints.append(problem.active_nodes <= node_bound)
    if depth_bound is not None:
        constraints.append(problem.effective_depth <= depth_bound)
    for index, value in sorted(fixed_selectors.items()):
        constraints.append(problem.selector[index] == value)
    for (index, offset), value in sorted(fixed_mappings.items()):
        constraints.append(problem.mapping[index][offset] == _bv(value, problem.ctx))
    if selector_upper is not None:
        index, value = selector_upper
        constraints.append(problem.selector[index] <= value)
    if mapping_upper is not None:
        index, offset, value = mapping_upper
        constraints.append(z3.ULE(problem.mapping[index][offset], _bv(value, problem.ctx)))
    constraints.extend(_ast_block_ctx(problem, block) for block in blocks)
    return tuple(constraints)


_BINARY_CONSTRUCTORS = {
    "add_mod": AddModExpr,
    "mul_mod": MulModExpr,
    "xor": XorExpr,
    "bit_and": BitAndExpr,
    "bit_or": BitOrExpr,
    "min_u3": MinU3Expr,
    "max_u3": MaxU3Expr,
    "abs_diff": AbsDiffExpr,
    "eq_mask": EqMaskExpr,
}


def _canonical_permutation_completion(
    expression,
    *,
    working: tuple[ProgramObservation, ...],
    latent_name: str,
    action_name: str,
):
    """Choose the least bijection completion consistent with current W semantics."""

    kind = expression.kind
    if kind in {"var", "const"}:
        return expression
    if kind == "rotl":
        return RotlExpr(
            value=_canonical_permutation_completion(
                expression.value,
                working=working,
                latent_name=latent_name,
                action_name=action_name,
            ),
            shift=expression.shift,
        )
    if kind == "permute":
        child = _canonical_permutation_completion(
            expression.value,
            working=working,
            latent_name=latent_name,
            action_name=action_name,
        )
        required: dict[int, int] = {}
        for observation in working:
            env = {latent_name: observation.q, action_name: observation.action}
            source = evaluate_expr(child, env)
            target = evaluate_expr(expression, env)
            previous = required.get(source)
            if previous is not None and previous != target:
                raise AssertionError("permutation model is inconsistent on identical child value")
            required[source] = target

        mapping = [-1] * DOMAIN_SIZE
        used = set(required.values())
        if len(used) != len(required):
            raise AssertionError("SAT permutation model violated bijection on W")
        for source, target in required.items():
            mapping[source] = target

        available = [value for value in range(DOMAIN_SIZE) if value not in used]
        cursor = 0
        for source in range(DOMAIN_SIZE):
            if mapping[source] >= 0:
                continue
            mapping[source] = available[cursor]
            cursor += 1
        return PermutationExpr(value=child, mapping=mapping)

    constructor = _BINARY_CONSTRUCTORS[kind]
    return constructor(
        left=_canonical_permutation_completion(
            expression.left,
            working=working,
            latent_name=latent_name,
            action_name=action_name,
        ),
        right=_canonical_permutation_completion(
            expression.right,
            working=working,
            latent_name=latent_name,
            action_name=action_name,
        ),
    )


def _cegis_feasible_hardened(
    *,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations: tuple[ProgramObservation, ...],
    max_depth: int,
    budget,
    working_indices: list[int],
    error_bound: int,
    node_bound: int | None = None,
    depth_bound: int | None = None,
    fixed_selectors: dict[int, int] | None = None,
    fixed_mappings: dict[tuple[int, int], int] | None = None,
    selector_upper: tuple[int, int] | None = None,
    mapping_upper: tuple[int, int, int] | None = None,
    blocks: tuple = (),
):
    fixed_selectors = fixed_selectors or {}
    fixed_mappings = fixed_mappings or {}

    while True:
        if budget.exhausted or budget.remaining <= 0:
            return _cegis._OracleResult("unknown", None)

        working = tuple(observations[index] for index in working_indices)
        problem = _IsolatedWorkingSetProblem(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=working,
            max_depth=max_depth,
        )
        extras = _extra_constraints_ctx(
            problem,
            error_bound=error_bound,
            node_bound=node_bound,
            depth_bound=depth_bound,
            fixed_selectors=fixed_selectors,
            fixed_mappings=fixed_mappings,
            selector_upper=selector_upper,
            mapping_upper=mapping_upper,
            blocks=blocks,
        )
        status, model = budget.check(tuple(problem.constraints), extras)
        if status == z3.unsat:
            return _cegis._OracleResult("infeasible", None)
        if status != z3.sat or model is None:
            return _cegis._OracleResult("unknown", None)

        problem.assert_model_soundness(model)
        expression = problem.decode_expression(model)
        expression = _canonical_permutation_completion(
            expression,
            working=working,
            latent_name=latent_name,
            action_name=action_name,
        )
        candidate = _cegis._verified_candidate(
            expression,
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
        )
        full_error = candidate.total - candidate.correct
        if full_error <= error_bound:
            return _cegis._OracleResult("feasible", candidate)

        counterexample = _cegis._first_outside_violation(
            expression,
            observations=observations,
            working_indices=working_indices,
            latent_name=latent_name,
            action_name=action_name,
        )
        if counterexample is None:
            raise AssertionError("full-data violation exists but no outside-W counterexample was found")
        working_indices.append(counterexample)


# Runtime global lookups in the authorized control loop are intentionally rebound
# to the hardened, semantically equivalent engineering components above.
_cegis._WorkingSetProblem = _IsolatedWorkingSetProblem
_cegis._CumulativeBudget = _IsolatedCumulativeBudget
_cegis._extra_constraints = _extra_constraints_ctx
_cegis._cegis_feasible = _cegis_feasible_hardened

SMTProgramSearchV02CEGIS = _cegis.SMTProgramSearchV02CEGIS
SMTProgramSearch = SMTProgramSearchV02CEGIS
