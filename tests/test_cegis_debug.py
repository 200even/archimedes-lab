import z3

from archimedes_v0 import synthesis_v02_cegis as impl
from archimedes_v0.ast_schema import VarExpr
from archimedes_v0.synthesis import ProgramObservation, _SkeletonProblem, _rlimit_count
from archimedes_v0.synthesis_v02_cegis_final import SMTProgramSearchV02CEGIS
from archimedes_v0.theory_eval import evaluate_expr


def _action_observations():
    expr = VarExpr(name="a")
    return tuple(
        ProgramObservation(q=q, action=a, y=evaluate_expr(expr, {"q": q, "a": a}))
        for q in range(8)
        for a in range(8)
    )


def _problem(observations):
    return _SkeletonProblem(
        q_cardinality=8,
        latent_name="q",
        action_name="a",
        observations=tuple(observations),
        max_depth=1,
    )


def _direct_status(observations):
    problem = _problem(observations)
    solver = z3.Solver()
    solver.add(*problem.constraints)
    solver.add(problem.error <= 0)
    return solver.check()


def test_rlimit_statistic_has_a_measurable_precheck_baseline():
    ordered = impl._canonical_observations(_action_observations())
    problem = _problem((ordered[0], ordered[1]))
    solver = z3.Solver()
    solver.set(rlimit=2_000_000)
    solver.add(*problem.constraints)
    solver.add(problem.error <= 0)
    before = _rlimit_count(solver.statistics())
    status = solver.check()
    after = _rlimit_count(solver.statistics())
    assert status == z3.sat
    assert after > before, (before, after)
    assert after - before < 2_000_000, (before, after, after - before)


def test_cegis_binding_and_first_two_action_constraints_are_satisfiable():
    assert impl._WorkingSetProblem is _SkeletonProblem
    ordered = impl._canonical_observations(_action_observations())
    assert ordered[0] == ProgramObservation(q=0, action=0, y=0)
    assert ordered[1] == ProgramObservation(q=0, action=1, y=1)
    assert _direct_status((ordered[0],)) == z3.sat
    assert _direct_status((ordered[0], ordered[1])) == z3.sat

    budget = impl._CumulativeBudget.create(2_000_000)
    working = [0]
    result = impl._cegis_feasible(
        q_cardinality=8,
        latent_name="q",
        action_name="a",
        observations=ordered,
        max_depth=1,
        budget=budget,
        working_indices=working,
        error_bound=0,
        blocks=(),
    )
    assert result.status == "feasible", (result, budget, working)
    assert result.candidate is not None and result.candidate.exact_accuracy == 1.0

    search = SMTProgramSearchV02CEGIS(max_depth=1, rlimit=2_000_000).search(
        q_cardinality=8,
        latent_name="q",
        action_name="a",
        observations=ordered,
        limit=1,
    )
    assert search.candidates, search
