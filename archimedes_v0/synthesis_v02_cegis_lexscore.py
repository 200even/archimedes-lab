"""Exact lexicographic objective encoding for the hardened V0.2 CEGIS engine.

The preregistered objective begins with Hamming error, then active AST nodes.  For
a skeleton with N possible active nodes, the scalar

    score = error * (N + 1) + active_nodes

is exactly order-isomorphic to that two-level lexicographic objective because
1 <= active_nodes <= N.  Searching this score therefore changes no scientific
objective or hypothesis.  It only prevents the SAT solver from exploring huge,
needlessly complex exact-fit trees before the already-preregistered node-count
objective is applied.

The minimum score is found deterministically by exponential bracketing followed by
binary search.  CEGIS still starts W={o_0}, appends exactly the first canonical
violating observation, verifies every model against full O in trusted Python, and
shares one cumulative 50M Z3 rlimit.  Depth and canonical AST remain the subsequent
frozen tie-break stages.
"""

from __future__ import annotations

import z3

from . import synthesis_v02_cegis as _cegis
from . import synthesis_v02_cegis_hardened as _hard


def _cegis_feasible_score(
    *,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations,
    max_depth: int,
    budget,
    working_indices: list[int],
    score_bound: int,
    blocks: tuple = (),
):
    max_nodes = (1 << max_depth) - 1
    weight = max_nodes + 1

    while True:
        if budget.exhausted or budget.remaining <= 0:
            return _cegis._OracleResult("unknown", None)

        working = tuple(observations[index] for index in working_indices)
        problem = _hard._IsolatedWorkingSetProblem(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=working,
            max_depth=max_depth,
        )
        extras = [problem.error * weight + problem.active_nodes <= score_bound]
        extras.extend(_hard._ast_block_ctx(problem, block) for block in blocks)
        status, model = budget.check(tuple(problem.constraints), tuple(extras))
        if status == z3.unsat:
            return _cegis._OracleResult("infeasible", None)
        if status != z3.sat or model is None:
            return _cegis._OracleResult("unknown", None)

        problem.assert_model_soundness(model)
        expression = problem.decode_expression(model)
        expression = _hard._canonical_permutation_completion(
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
        full_score = full_error * weight + candidate.node_count
        if full_score <= score_bound:
            return _cegis._OracleResult("feasible", candidate)

        counterexample = _cegis._first_outside_violation(
            expression,
            observations=observations,
            working_indices=working_indices,
            latent_name=latent_name,
            action_name=action_name,
        )
        if counterexample is None:
            # The structural node term is already enforced inside Z3, so a
            # full-score violation can only come from an observation outside W.
            raise AssertionError("score violation exists but no outside-W counterexample was found")
        working_indices.append(counterexample)


def _candidate_score(candidate, max_depth: int) -> int:
    max_nodes = (1 << max_depth) - 1
    return (candidate.total - candidate.correct) * (max_nodes + 1) + candidate.node_count


def _minimize_error_nodes(
    *,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations,
    max_depth: int,
    budget,
    working_indices: list[int],
    blocks: tuple,
):
    max_nodes = (1 << max_depth) - 1
    max_score = len(observations) * (max_nodes + 1) + max_nodes

    lower = 1
    upper = 1
    incumbent = None

    # Parameter-free deterministic exponential bracketing.
    while True:
        result = _cegis_feasible_score(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            score_bound=upper,
            blocks=blocks,
        )
        if result.status == "unknown":
            return incumbent, None, None, False
        if result.status == "feasible":
            incumbent = result.candidate
            assert incumbent is not None
            upper = min(upper, _candidate_score(incumbent, max_depth))
            break
        if upper >= max_score:
            return None, None, None, True
        lower = upper + 1
        upper = min(max_score, upper * 2)

    # Exact deterministic binary search within the established bracket.
    while lower < upper:
        midpoint = (lower + upper) // 2
        result = _cegis_feasible_score(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            score_bound=midpoint,
            blocks=blocks,
        )
        if result.status == "unknown":
            if incumbent is None:
                return None, None, None, False
            weight = max_nodes + 1
            return (
                incumbent,
                incumbent.total - incumbent.correct,
                incumbent.node_count,
                False,
            )
        if result.status == "infeasible":
            lower = midpoint + 1
            continue
        incumbent = result.candidate
        assert incumbent is not None
        upper = min(midpoint, _candidate_score(incumbent, max_depth))

    target_score = lower
    if incumbent is None or _candidate_score(incumbent, max_depth) != target_score:
        result = _cegis_feasible_score(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            score_bound=target_score,
            blocks=blocks,
        )
        if result.status != "feasible" or result.candidate is None:
            return incumbent, None, None, False
        incumbent = result.candidate

    weight = max_nodes + 1
    error_bound = target_score // weight
    node_bound = target_score % weight
    if node_bound == 0:
        # Active-node count is never zero, so a remainder-zero boundary belongs
        # to the preceding error level with N+1 nodes, which is impossible.
        raise AssertionError("invalid lexicographic score remainder")
    if (incumbent.total - incumbent.correct) != error_bound or incumbent.node_count != node_bound:
        raise AssertionError("trusted candidate does not realize minimal lexicographic score")
    return incumbent, error_bound, node_bound, True


def _optimize_one_lexscore(
    *,
    q_cardinality: int,
    latent_name: str,
    action_name: str,
    observations,
    max_depth: int,
    budget,
    working_indices: list[int],
    blocks: tuple,
):
    incumbent, error_bound, node_bound, complete = _minimize_error_nodes(
        q_cardinality=q_cardinality,
        latent_name=latent_name,
        action_name=action_name,
        observations=observations,
        max_depth=max_depth,
        budget=budget,
        working_indices=working_indices,
        blocks=blocks,
    )
    if incumbent is None or error_bound is None or node_bound is None:
        return incumbent, False
    if not complete:
        return incumbent, False

    incumbent, depth_bound, depth_complete = _cegis._minimize_integer_bound(
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

    incumbent, canonical_complete = _cegis._canonicalize(
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


# The public search class resolves `_optimize_one` at runtime, so this binding
# changes only the exact search order for the already-frozen objective.
_cegis._optimize_one = _optimize_one_lexscore

SMTProgramSearchV02CEGIS = _cegis.SMTProgramSearchV02CEGIS
SMTProgramSearch = SMTProgramSearchV02CEGIS
