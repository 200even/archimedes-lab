from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass

import z3

from .constants import DOMAIN_SIZE, MAX_EXPRESSION_DEPTH
from .synthesis import (
    BINARY_OPS,
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
    Z3_RANDOM_SEED,
    Z3_RLIMIT_PER_INVOCATION,
    _SkeletonProblem,
    _canonical,
    _expression_depth,
    _expression_node_count,
    _rlimit_count,
    assert_frozen_z3_package,
    solver_parameter_manifest_sha256,
)
from .theory_eval import evaluate_expr


@dataclass
class _CumulativeBudget:
    """Single deterministic Z3 resource ledger for one synthesis invocation."""

    limit: int
    remaining: int
    used: int = 0
    checks: int = 0
    exhausted: bool = False
    last_reason_unknown: str | None = None

    @classmethod
    def create(cls, limit: int) -> "_CumulativeBudget":
        return cls(limit=limit, remaining=limit)

    def check(self, base_constraints: tuple, extra_constraints: tuple = ()):
        if self.remaining <= 0:
            self.exhausted = True
            self.last_reason_unknown = "cumulative rlimit exhausted"
            return z3.unknown, None

        solver = z3.Solver()
        solver.set(auto_config=True)
        solver.set(random_seed=Z3_RANDOM_SEED)
        solver.set(timeout=0)
        solver.set(rlimit=self.remaining)
        solver.add(*base_constraints)
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
            # V0.2 has no scientific wall-clock timeout and no stochastic restart.
            # Any unknown therefore terminates this deterministic invocation.
            self.exhausted = True
            return status, None
        if status == z3.sat:
            return status, solver.model()
        return status, None


class _WorkingSetProblem(_SkeletonProblem):
    """Frozen syntax skeleton whose semantic graph contains only current CEGIS points."""

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

        # These are the same frozen structure and operator-semantics builders used
        # by the monolithic V0.2 encoding. Only the point set is smaller.
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


@dataclass(frozen=True)
class _EncodedAST:
    selectors: tuple[int, ...]
    mappings: tuple[tuple[int, ...], ...]


def _encode_expression(expression, *, latent_name: str, action_name: str, node_count: int) -> _EncodedAST:
    selectors = [OP_INACTIVE] * node_count
    mappings = [list(range(DOMAIN_SIZE)) for _ in range(node_count)]

    def fill(expr, index: int) -> None:
        if index >= node_count:
            raise AssertionError("expression exceeds bounded skeleton")
        if expr.kind == "var":
            if expr.name == latent_name:
                selectors[index] = OP_Q
            elif expr.name == action_name:
                selectors[index] = OP_ACTION
            else:
                raise AssertionError(f"unexpected variable {expr.name}")
            return
        if expr.kind == "const":
            selectors[index] = OP_CONST_0 + expr.value
            return

        left_index = 2 * index + 1
        if expr.kind == "rotl":
            selectors[index] = OP_ROTL_1 if expr.shift == 1 else OP_ROTL_2
            fill(expr.value, left_index)
            return
        if expr.kind == "permute":
            selectors[index] = OP_PERMUTE
            mappings[index] = list(expr.mapping)
            fill(expr.value, left_index)
            return

        selector_by_kind = {
            "add_mod": OP_ADD_MOD,
            "mul_mod": OP_MUL_MOD,
            "xor": OP_XOR,
            "bit_and": OP_BIT_AND,
            "bit_or": OP_BIT_OR,
            "min_u3": OP_MIN_U3,
            "max_u3": OP_MAX_U3,
            "abs_diff": OP_ABS_DIFF,
            "eq_mask": OP_EQ_MASK,
        }
        if expr.kind not in selector_by_kind:
            raise AssertionError(f"unexpected expression kind {expr.kind}")
        selectors[index] = selector_by_kind[expr.kind]
        fill(expr.left, left_index)
        fill(expr.right, left_index + 1)

    fill(expression, 0)
    return _EncodedAST(
        selectors=tuple(selectors),
        mappings=tuple(tuple(mapping) for mapping in mappings),
    )


def _canonical_observations(observations: tuple[ProgramObservation, ...]) -> tuple[ProgramObservation, ...]:
    # q, action, and observed output are all opaque finite integers. The original
    # position only breaks exact duplicate ties and therefore carries no heuristic signal.
    indexed = tuple(enumerate(observations))
    ordered = sorted(indexed, key=lambda item: (item[1].q, item[1].action, item[1].y, item[0]))
    return tuple(observation for _, observation in ordered)


def _verified_candidate(
    expression,
    *,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations: tuple[ProgramObservation, ...],
) -> ProgramCandidate:
    points = tuple((q, action) for q in range(q_cardinality) for action in range(DOMAIN_SIZE))
    truth_table = tuple(
        evaluate_expr(expression, {latent_name: q, action_name: action})
        for q, action in points
    )
    correct = sum(
        evaluate_expr(expression, {latent_name: observation.q, action_name: observation.action})
        == observation.y
        for observation in observations
    )
    return ProgramCandidate(
        expression=expression,
        truth_table=truth_table,
        correct=correct,
        total=len(observations),
        exact_accuracy=correct / len(observations),
        node_count=_expression_node_count(expression),
        depth=_expression_depth(expression),
        canonical_ast=_canonical(expression),
    )


def _first_outside_violation(
    expression,
    *,
    observations: tuple[ProgramObservation, ...],
    working_indices: list[int],
    latent_name: str,
    action_name: str,
) -> int | None:
    working = set(working_indices)
    for index, observation in enumerate(observations):
        if index in working:
            continue
        predicted = evaluate_expr(expression, {latent_name: observation.q, action_name: observation.action})
        if predicted != observation.y:
            return index
    return None


def _ast_block(problem: _WorkingSetProblem, encoded: _EncodedAST):
    terms = [
        problem.selector[index] != selector
        for index, selector in enumerate(encoded.selectors)
    ]
    for index, selector in enumerate(encoded.selectors):
        if selector == OP_PERMUTE:
            for offset, value in enumerate(encoded.mappings[index]):
                terms.append(problem.mapping[index][offset] != z3.BitVecVal(value, 3))
    return z3.Or(*terms)


def _extra_constraints(
    problem: _WorkingSetProblem,
    *,
    error_bound: int,
    node_bound: int | None,
    depth_bound: int | None,
    fixed_selectors: dict[int, int],
    fixed_mappings: dict[tuple[int, int], int],
    selector_upper: tuple[int, int] | None,
    mapping_upper: tuple[int, int, int] | None,
    blocks: tuple[_EncodedAST, ...],
) -> tuple:
    constraints = [problem.error <= error_bound]
    if node_bound is not None:
        constraints.append(problem.active_nodes <= node_bound)
    if depth_bound is not None:
        constraints.append(problem.effective_depth <= depth_bound)
    for index, value in sorted(fixed_selectors.items()):
        constraints.append(problem.selector[index] == value)
    for (index, offset), value in sorted(fixed_mappings.items()):
        constraints.append(problem.mapping[index][offset] == z3.BitVecVal(value, 3))
    if selector_upper is not None:
        index, value = selector_upper
        constraints.append(problem.selector[index] <= value)
    if mapping_upper is not None:
        index, offset, value = mapping_upper
        constraints.append(z3.ULE(problem.mapping[index][offset], z3.BitVecVal(value, 3)))
    constraints.extend(_ast_block(problem, block) for block in blocks)
    return tuple(constraints)


@dataclass(frozen=True)
class _OracleResult:
    status: str  # feasible | infeasible | unknown
    candidate: ProgramCandidate | None


def _cegis_feasible(
    *,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations: tuple[ProgramObservation, ...],
    max_depth: int,
    budget: _CumulativeBudget,
    working_indices: list[int],
    error_bound: int,
    node_bound: int | None = None,
    depth_bound: int | None = None,
    fixed_selectors: dict[int, int] | None = None,
    fixed_mappings: dict[tuple[int, int], int] | None = None,
    selector_upper: tuple[int, int] | None = None,
    mapping_upper: tuple[int, int, int] | None = None,
    blocks: tuple[_EncodedAST, ...] = (),
) -> _OracleResult:
    fixed_selectors = fixed_selectors or {}
    fixed_mappings = fixed_mappings or {}

    while True:
        if budget.exhausted or budget.remaining <= 0:
            return _OracleResult("unknown", None)

        working = tuple(observations[index] for index in working_indices)
        problem = _WorkingSetProblem(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=working,
            max_depth=max_depth,
        )
        extras = _extra_constraints(
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
            return _OracleResult("infeasible", None)
        if status != z3.sat or model is None:
            return _OracleResult("unknown", None)

        problem.assert_model_soundness(model)
        expression = problem.decode_expression(model)
        candidate = _verified_candidate(
            expression,
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
        )
        full_error = candidate.total - candidate.correct
        if full_error <= error_bound:
            return _OracleResult("feasible", candidate)

        counterexample = _first_outside_violation(
            expression,
            observations=observations,
            working_indices=working_indices,
            latent_name=latent_name,
            action_name=action_name,
        )
        if counterexample is None:
            raise AssertionError("full-data violation exists but no outside-W counterexample was found")
        working_indices.append(counterexample)


def _minimize_hamming(
    *,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations: tuple[ProgramObservation, ...],
    max_depth: int,
    budget: _CumulativeBudget,
    working_indices: list[int],
    blocks: tuple[_EncodedAST, ...],
) -> tuple[ProgramCandidate | None, int | None, bool]:
    # Deterministic exact-first lower-bound check. For the frozen qualification
    # corpus this is the theoretically correct bound; noisy V0 data falls through
    # to bounded integer minimization without changing the objective.
    exact = _cegis_feasible(
        q_cardinality=q_cardinality,
        latent_name=latent_name,
        action_name=action_name,
        observations=observations,
        max_depth=max_depth,
        budget=budget,
        working_indices=working_indices,
        error_bound=0,
        blocks=blocks,
    )
    if exact.status == "feasible":
        return exact.candidate, 0, True
    if exact.status == "unknown":
        return None, None, False

    low = 1
    high = len(observations)
    incumbent: ProgramCandidate | None = None

    while low < high:
        midpoint = (low + high) // 2
        result = _cegis_feasible(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            error_bound=midpoint,
            blocks=blocks,
        )
        if result.status == "unknown":
            return incumbent, (incumbent.total - incumbent.correct) if incumbent else None, False
        if result.status == "infeasible":
            low = midpoint + 1
            continue
        assert result.candidate is not None
        incumbent = result.candidate
        high = min(midpoint, incumbent.total - incumbent.correct)

    target = low
    if incumbent is None or (incumbent.total - incumbent.correct) > target:
        result = _cegis_feasible(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            error_bound=target,
            blocks=blocks,
        )
        if result.status != "feasible" or result.candidate is None:
            return incumbent, (incumbent.total - incumbent.correct) if incumbent else None, False
        incumbent = result.candidate
    return incumbent, target, True


def _minimize_integer_bound(
    *,
    objective: str,
    incumbent: ProgramCandidate,
    error_bound: int,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations: tuple[ProgramObservation, ...],
    max_depth: int,
    budget: _CumulativeBudget,
    working_indices: list[int],
    node_bound: int | None,
    depth_bound: int | None,
    blocks: tuple[_EncodedAST, ...],
) -> tuple[ProgramCandidate, int, bool]:
    if objective == "nodes":
        low, high = 1, incumbent.node_count
    elif objective == "depth":
        low, high = 1, incumbent.depth
    else:
        raise ValueError("unknown integer objective")

    best = incumbent
    while low < high:
        midpoint = (low + high) // 2
        trial_nodes = midpoint if objective == "nodes" else node_bound
        trial_depth = midpoint if objective == "depth" else depth_bound
        result = _cegis_feasible(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            error_bound=error_bound,
            node_bound=trial_nodes,
            depth_bound=trial_depth,
            blocks=blocks,
        )
        if result.status == "unknown":
            return best, (best.node_count if objective == "nodes" else best.depth), False
        if result.status == "infeasible":
            low = midpoint + 1
            continue
        assert result.candidate is not None
        best = result.candidate
        observed = best.node_count if objective == "nodes" else best.depth
        high = min(midpoint, observed)

    return best, high, True


def _canonicalize(
    *,
    incumbent: ProgramCandidate,
    error_bound: int,
    node_bound: int,
    depth_bound: int,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations: tuple[ProgramObservation, ...],
    max_depth: int,
    budget: _CumulativeBudget,
    working_indices: list[int],
    blocks: tuple[_EncodedAST, ...],
) -> tuple[ProgramCandidate, bool]:
    fixed_selectors: dict[int, int] = {}
    fixed_mappings: dict[tuple[int, int], int] = {}
    best = incumbent
    node_count = (1 << max_depth) - 1

    def visit(index: int) -> bool:
        nonlocal best
        encoded = _encode_expression(
            best.expression,
            latent_name=latent_name,
            action_name=action_name,
            node_count=node_count,
        )
        low = OP_Q
        high = encoded.selectors[index]
        while low < high:
            midpoint = (low + high) // 2
            result = _cegis_feasible(
                q_cardinality=q_cardinality,
                latent_name=latent_name,
                action_name=action_name,
                observations=observations,
                max_depth=max_depth,
                budget=budget,
                working_indices=working_indices,
                error_bound=error_bound,
                node_bound=node_bound,
                depth_bound=depth_bound,
                fixed_selectors=fixed_selectors,
                fixed_mappings=fixed_mappings,
                selector_upper=(index, midpoint),
                blocks=blocks,
            )
            if result.status == "unknown":
                return False
            if result.status == "infeasible":
                low = midpoint + 1
                continue
            assert result.candidate is not None
            best = result.candidate
            current = _encode_expression(
                best.expression,
                latent_name=latent_name,
                action_name=action_name,
                node_count=node_count,
            ).selectors[index]
            high = min(midpoint, current)

        fixed_selectors[index] = high
        selector = high

        if selector == OP_PERMUTE:
            for offset in range(DOMAIN_SIZE):
                encoded = _encode_expression(
                    best.expression,
                    latent_name=latent_name,
                    action_name=action_name,
                    node_count=node_count,
                )
                low_map = 0
                high_map = encoded.mappings[index][offset]
                while low_map < high_map:
                    midpoint = (low_map + high_map) // 2
                    result = _cegis_feasible(
                        q_cardinality=q_cardinality,
                        latent_name=latent_name,
                        action_name=action_name,
                        observations=observations,
                        max_depth=max_depth,
                        budget=budget,
                        working_indices=working_indices,
                        error_bound=error_bound,
                        node_bound=node_bound,
                        depth_bound=depth_bound,
                        fixed_selectors=fixed_selectors,
                        fixed_mappings=fixed_mappings,
                        mapping_upper=(index, offset, midpoint),
                        blocks=blocks,
                    )
                    if result.status == "unknown":
                        return False
                    if result.status == "infeasible":
                        low_map = midpoint + 1
                        continue
                    assert result.candidate is not None
                    best = result.candidate
                    current = _encode_expression(
                        best.expression,
                        latent_name=latent_name,
                        action_name=action_name,
                        node_count=node_count,
                    ).mappings[index][offset]
                    high_map = min(midpoint, current)
                fixed_mappings[(index, offset)] = high_map

        if selector in LEAF_OPS:
            return True
        left = 2 * index + 1
        if not visit(left):
            return False
        if selector in BINARY_OPS:
            if not visit(left + 1):
                return False
        return True

    complete = visit(0)
    return best, complete


def _optimize_one(
    *,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations: tuple[ProgramObservation, ...],
    max_depth: int,
    budget: _CumulativeBudget,
    working_indices: list[int],
    blocks: tuple[_EncodedAST, ...],
) -> tuple[ProgramCandidate | None, bool]:
    incumbent, error_bound, error_complete = _minimize_hamming(
        q_cardinality=q_cardinality,
        latent_name=latent_name,
        action_name=action_name,
        observations=observations,
        max_depth=max_depth,
        budget=budget,
        working_indices=working_indices,
        blocks=blocks,
    )
    if incumbent is None or error_bound is None:
        return None, False
    if not error_complete:
        return incumbent, False

    incumbent, node_bound, node_complete = _minimize_integer_bound(
        objective="nodes",
        incumbent=incumbent,
        error_bound=error_bound,
        q_cardinality=q_cardinality,
        latent_name=latent_name,
        action_name=action_name,
        observations=observations,
        max_depth=max_depth,
        budget=budget,
        working_indices=working_indices,
        node_bound=None,
        depth_bound=None,
        blocks=blocks,
    )
    if not node_complete:
        return incumbent, False

    incumbent, depth_bound, depth_complete = _minimize_integer_bound(
        objective="depth",
        incumbent=incumbent,
        error_bound=error_bound,
        q_cardinality=q_cardinality,
        latent_name=latent_name,
        action_name=action_name,
        observations=observations,
        max_depth=max_depth,
        budget=budget,
        working_indices=working_indices,
        node_bound=node_bound,
        depth_bound=None,
        blocks=blocks,
    )
    if not depth_complete:
        return incumbent, False

    incumbent, canonical_complete = _canonicalize(
        incumbent=incumbent,
        error_bound=error_bound,
        node_bound=node_bound,
        depth_bound=depth_bound,
        q_cardinality=q_cardinality,
        latent_name=latent_name,
        action_name=action_name,
        observations=observations,
        max_depth=max_depth,
        budget=budget,
        working_indices=working_indices,
        blocks=blocks,
    )
    return incumbent, canonical_complete


class SMTProgramSearchV02CEGIS:
    """Final authorized V0.2 deterministic CEGIS constraint synthesizer."""

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
        if not observations:
            raise ValueError("at least one visible observation is required")
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

        ordered = _canonical_observations(observations)
        budget = _CumulativeBudget.create(self.rlimit)
        working_indices = [0]
        candidates: list[ProgramCandidate] = []
        blocks: list[_EncodedAST] = []
        all_complete = True

        while len(candidates) < limit and not budget.exhausted:
            candidate, complete = _optimize_one(
                q_cardinality=q_cardinality,
                latent_name=latent_name,
                action_name=action_name,
                observations=ordered,
                max_depth=self.max_depth,
                budget=budget,
                working_indices=working_indices,
                blocks=tuple(blocks),
            )
            if candidate is None:
                all_complete = False
                break
            candidates.append(candidate)
            all_complete = all_complete and complete
            blocks.append(
                _encode_expression(
                    candidate.expression,
                    latent_name=latent_name,
                    action_name=action_name,
                    node_count=(1 << self.max_depth) - 1,
                )
            )
            if not complete:
                break

        if budget.exhausted:
            status = "resource_exhausted_with_candidate" if candidates else "unknown"
        elif candidates:
            status = "sat" if all_complete else "sat_incomplete_optimization"
        else:
            status = "unsat"

        objective = None
        if candidates:
            first = candidates[0]
            objective = (first.total - first.correct, first.node_count, first.depth)

        return ProgramSearchResult(
            candidates=tuple(candidates),
            solver_status=status,
            solver_reason_unknown=budget.last_reason_unknown,
            sat_checks=budget.checks,
            rlimit=self.rlimit,
            rlimit_used=min(budget.used, self.rlimit),
            objective=objective,
            exhausted=budget.exhausted,
            solver_package_version=importlib.metadata.version("z3-solver"),
            solver_internal_version=z3.get_version_string(),
            solver_parameter_manifest_sha256=solver_parameter_manifest_sha256(),
        )


# Public continuity name used by qualification and runtime integration.
SMTProgramSearch = SMTProgramSearchV02CEGIS
