from archimedes_v0.agent_interfaces import StatelessFlatAgent
from archimedes_v0.ast_schema import (
    AddModExpr,
    ConstExpr,
    LatentVariable,
    PermutationExpr,
    ProgramSpec,
    RotlExpr,
    TheoryAST,
    VarExpr,
    XorExpr,
)
from archimedes_v0.synthesis import (
    ProgramObservation,
    Z3_PACKAGE_VERSION,
    Z3_RLIMIT_PER_INVOCATION,
    assert_frozen_z3_package,
)
from archimedes_v0.synthesis_v02_cegis_final import SMTProgramSearchV02CEGIS as SMTProgramSearch
from archimedes_v0.synthesis_v02_runtime import EnumerativeSynthesizerV02 as EnumerativeSynthesizer
from archimedes_v0.theory_eval import evaluate_expr


def _observations(expression):
    return tuple(
        ProgramObservation(q=q, action=a, y=evaluate_expr(expression, {"q": q, "a": a}))
        for q in range(8)
        for a in range(8)
    )


def test_frozen_z3_package_is_exact():
    assert Z3_PACKAGE_VERSION == "5.1.0.0"
    assert Z3_RLIMIT_PER_INVOCATION == 50_000_000
    assert_frozen_z3_package()


def test_cegis_exhaustively_recovers_depth_one_grammar():
    targets = [VarExpr(name="q"), VarExpr(name="a")]
    targets.extend(ConstExpr(value=value) for value in range(8))
    for target in targets:
        result = SMTProgramSearch(max_depth=1, rlimit=2_000_000).search(
            q_cardinality=8,
            latent_name="q",
            action_name="a",
            observations=_observations(target),
            limit=1,
        )
        assert result.candidates, (target, result)
        assert result.candidates[0].exact_accuracy == 1.0, (target, result)


def test_cegis_recovers_simple_two_variable_law():
    target = AddModExpr(left=VarExpr(name="q"), right=VarExpr(name="a"))
    result = SMTProgramSearch(max_depth=2, rlimit=5_000_000).search(
        q_cardinality=8,
        latent_name="q",
        action_name="a",
        observations=_observations(target),
        limit=1,
    )
    assert result.candidates, result
    assert result.candidates[0].exact_accuracy == 1.0, result
    assert result.candidates[0].truth_table == tuple(
        evaluate_expr(target, {"q": q, "a": a}) for q in range(8) for a in range(8)
    )


def _nested_permutation_target():
    return PermutationExpr(
        value=XorExpr(
            left=RotlExpr(value=VarExpr(name="q"), shift=1),
            right=VarExpr(name="a"),
        ),
        mapping=[3, 1, 7, 0, 5, 2, 6, 4],
    )


def test_cegis_handles_nested_permutation_without_target_specific_rules():
    target = _nested_permutation_target()
    result = SMTProgramSearch(max_depth=4, rlimit=Z3_RLIMIT_PER_INVOCATION).search(
        q_cardinality=8,
        latent_name="q",
        action_name="a",
        observations=_observations(target),
        limit=1,
    )
    assert result.candidates, result
    assert result.candidates[0].exact_accuracy == 1.0, result


def test_cegis_handles_same_fixture_inside_qualification_depth_skeleton():
    target = _nested_permutation_target()
    result = SMTProgramSearch(max_depth=5, rlimit=Z3_RLIMIT_PER_INVOCATION).search(
        q_cardinality=8,
        latent_name="q",
        action_name="a",
        observations=_observations(target),
        limit=1,
    )
    assert result.candidates, result
    assert result.candidates[0].exact_accuracy == 1.0, result


def test_deterministic_replay_on_independent_fixture():
    target = XorExpr(left=VarExpr(name="q"), right=VarExpr(name="a"))
    kwargs = dict(
        q_cardinality=8,
        latent_name="q",
        action_name="a",
        observations=_observations(target),
        limit=1,
    )
    first = SMTProgramSearch(max_depth=2, rlimit=5_000_000).search(**kwargs)
    second = SMTProgramSearch(max_depth=2, rlimit=5_000_000).search(**kwargs)
    assert first.candidates and second.candidates
    assert first.candidates[0].canonical_ast == second.candidates[0].canonical_ast
    assert first.candidates[0].truth_table == second.candidates[0].truth_table
    assert first.rlimit_used == second.rlimit_used
    assert first.sat_checks == second.sat_checks


def test_synthesizer_never_changes_llm_partition():
    assignments = {f"entity_{i:02d}": i % 2 for i in range(16)}
    latent = LatentVariable(name="qhat", cardinality=2, assignments=assignments)
    source = TheoryAST(
        theory_id="T-source",
        latent_variables=[latent],
        programs=[
            ProgramSpec(
                paradigm="A",
                expression=AddModExpr(left=VarExpr(name="qhat"), right=VarExpr(name="x")),
            )
        ],
    )
    observations = tuple(
        {
            "paradigm": "A",
            "entity_id": entity_id,
            "action_value": action,
            "y": (q + action) % 8,
        }
        for entity_id, q in assignments.items()
        for action in range(8)
    )
    results = EnumerativeSynthesizer(max_depth=2).synthesize(
        paradigm="A",
        observations=observations,
        candidate_theories=(source,),
        frozen_a_theory=None,
        limit=1,
    )
    assert results
    assert all(theory.latent_variables[0].assignments == assignments for theory in results)
    assert all(theory.latent_variables[0].cardinality == 2 for theory in results)


class RecordingBackend:
    def __init__(self):
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs["response_schema"].get("title") == "CandidateSet":
            return {"candidates": []}
        if kwargs["response_schema"].get("title") == "ACommitDecision":
            return {"decision": "abstain", "theory": None}
        return {
            "experiments": [
                {
                    "experiment_id": "E-flat-test",
                    "objective": "estimate",
                    "paradigm": "A",
                    "intervention": {"entity_id": "entity_00", "action_value": 0},
                    "target_theory_ids": ["T-explore"],
                }
            ]
        }


def test_flat_slots_are_one_for_one_compute_matched():
    backend = RecordingBackend()
    flat = StatelessFlatAgent(backend, "flat prompt")
    flat.propose_candidates({})
    flat.propose_experiments({})
    flat.decide_a({})
    assert [call["max_output_tokens"] for call in backend.calls] == [4096, 2048, 4096]
    assert all(call["role"] == "flat" for call in backend.calls)
