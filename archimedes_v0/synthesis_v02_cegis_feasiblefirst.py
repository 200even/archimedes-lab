"""Final preregistered feasible-first / exact-first schedule for V0.2 CEGIS.

The exact deterministic sequence is frozen in
SYNTH_V02_FEASIBLE_FIRST_SCHEDULE_FREEZE.md:

    fallback -> E <= 0 -> remaining Hamming binary search
    -> node tightening -> depth tightening -> canonical tie-break

This module changes only optimization order. It preserves the frozen grammar,
CEGIS counterexample policy, trusted full-O verification, objective hierarchy,
partial-permutation semantics, invocation-local Z3 context, and one cumulative
50M rlimit.
"""

from __future__ import annotations

# Importing the partial-permutation binding installs all previously authorized
# prequalification hardening before this final search-order binding is applied.
from . import synthesis_v02_cegis as _cegis
from . import synthesis_v02_cegis_partialperm as _partial  # noqa: F401


def _candidate_key(candidate):
    return (
        candidate.total - candidate.correct,
        candidate.node_count,
        candidate.depth,
        candidate.canonical_ast,
    )


def _better(current, candidate):
    if current is None:
        return candidate
    return candidate if _candidate_key(candidate) < _candidate_key(current) else current


def _optimize_one_feasible_first(
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
    """Anytime lexicographic optimization under the frozen exact-first order."""

    # Phase 0: establish any full-O-verified legal fallback incumbent before
    # attempting an optimized Hamming bound. No structural minimization is
    # supplied; the frozen maximum syntax skeleton is intrinsic to max_depth.
    initial = _cegis._cegis_feasible(
        q_cardinality=q_cardinality,
        latent_name=latent_name,
        action_name=action_name,
        observations=observations,
        max_depth=max_depth,
        budget=budget,
        working_indices=working_indices,
        error_bound=len(observations),
        node_bound=None,
        depth_bound=None,
        blocks=blocks,
    )
    if initial.status != "feasible" or initial.candidate is None:
        return None, False
    incumbent = initial.candidate

    # Phase 1A: mandatory exact-first query at the mathematical Hamming lower
    # bound. The referee explicitly prohibited node/depth minimization here.
    exact = _cegis._cegis_feasible(
        q_cardinality=q_cardinality,
        latent_name=latent_name,
        action_name=action_name,
        observations=observations,
        max_depth=max_depth,
        budget=budget,
        working_indices=working_indices,
        error_bound=0,
        node_bound=None,
        depth_bound=None,
        blocks=blocks,
    )
    if exact.status == "unknown":
        return incumbent, False

    if exact.status == "feasible":
        assert exact.candidate is not None
        incumbent = _better(incumbent, exact.candidate)
        if (incumbent.total - incumbent.correct) != 0:
            raise AssertionError("exact-first feasibility did not produce an exact incumbent")
        error_bound = 0
    else:
        # Phase 1B: E<=0 was proven infeasible. Search only the remaining
        # interval [1, e_inc] by deterministic binary tightening, still without
        # structural minimization.
        lo = 1
        hi = incumbent.total - incumbent.correct
        while lo < hi:
            midpoint = (lo + hi) // 2
            result = _cegis._cegis_feasible(
                q_cardinality=q_cardinality,
                latent_name=latent_name,
                action_name=action_name,
                observations=observations,
                max_depth=max_depth,
                budget=budget,
                working_indices=working_indices,
                error_bound=midpoint,
                node_bound=None,
                depth_bound=None,
                blocks=blocks,
            )
            if result.status == "unknown":
                return incumbent, False
            if result.status == "infeasible":
                lo = midpoint + 1
                continue
            assert result.candidate is not None
            incumbent = _better(incumbent, result.candidate)
            hi = min(midpoint, result.candidate.total - result.candidate.correct)

        error_bound = lo
        if (incumbent.total - incumbent.correct) != error_bound:
            # Exactly one witness query at the established minimum bound.
            witness = _cegis._cegis_feasible(
                q_cardinality=q_cardinality,
                latent_name=latent_name,
                action_name=action_name,
                observations=observations,
                max_depth=max_depth,
                budget=budget,
                working_indices=working_indices,
                error_bound=error_bound,
                node_bound=None,
                depth_bound=None,
                blocks=blocks,
            )
            if witness.status != "feasible" or witness.candidate is None:
                return incumbent, False
            incumbent = _better(incumbent, witness.candidate)
        if (incumbent.total - incumbent.correct) != error_bound:
            raise AssertionError("Hamming optimum lacks a matching verified incumbent")

    # Phase 2: exact minimum active-node count only after Hamming is fixed.
    lo = 1
    hi = incumbent.node_count
    while lo < hi:
        midpoint = (lo + hi) // 2
        result = _cegis._cegis_feasible(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            error_bound=error_bound,
            node_bound=midpoint,
            depth_bound=None,
            blocks=blocks,
        )
        if result.status == "unknown":
            return incumbent, False
        if result.status == "infeasible":
            lo = midpoint + 1
            continue
        assert result.candidate is not None
        incumbent = _better(incumbent, result.candidate)
        hi = min(midpoint, result.candidate.node_count)

    node_bound = lo
    if incumbent.node_count != node_bound:
        witness = _cegis._cegis_feasible(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            error_bound=error_bound,
            node_bound=node_bound,
            depth_bound=None,
            blocks=blocks,
        )
        if witness.status != "feasible" or witness.candidate is None:
            return incumbent, False
        incumbent = _better(incumbent, witness.candidate)
    if (incumbent.total - incumbent.correct) != error_bound or incumbent.node_count != node_bound:
        raise AssertionError("node optimum lacks a matching verified incumbent")

    # Phase 3: exact minimum depth at fixed Hamming and node optima.
    lo = 1
    hi = incumbent.depth
    while lo < hi:
        midpoint = (lo + hi) // 2
        result = _cegis._cegis_feasible(
            q_cardinality=q_cardinality,
            latent_name=latent_name,
            action_name=action_name,
            observations=observations,
            max_depth=max_depth,
            budget=budget,
            working_indices=working_indices,
            error_bound=error_bound,
            node_bound=node_bound,
            depth_bound=midpoint,
            blocks=blocks,
        )
        if result.status == "unknown":
            return incumbent, False
        if result.status == "infeasible":
            lo = midpoint + 1
            continue
        assert result.candidate is not None
        incumbent = _better(incumbent, result.candidate)
        hi = min(midpoint, result.candidate.depth)

    depth_bound = lo
    if incumbent.depth != depth_bound:
        witness = _cegis._cegis_feasible(
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
            blocks=blocks,
        )
        if witness.status != "feasible" or witness.candidate is None:
            return incumbent, False
        incumbent = _better(incumbent, witness.candidate)
    if (
        (incumbent.total - incumbent.correct) != error_bound
        or incumbent.node_count != node_bound
        or incumbent.depth != depth_bound
    ):
        raise AssertionError("depth optimum lacks a matching verified incumbent")

    # Phase 4: existing frozen canonical preorder selector/mapping tie-break.
    canonical, complete = _cegis._canonicalize(
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
    incumbent = _better(incumbent, canonical)
    return incumbent, complete


# The public search class resolves this global at call time. This is the final
# referee-authorized search-order clarification; no hypothesis or grammar
# binding changes.
_cegis._optimize_one = _optimize_one_feasible_first

SMTProgramSearchV02CEGIS = _cegis.SMTProgramSearchV02CEGIS
SMTProgramSearch = SMTProgramSearchV02CEGIS
