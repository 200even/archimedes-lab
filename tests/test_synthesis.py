from archimedes_v0.agent_interfaces import StatelessFlatAgent
from archimedes_v0.ast_schema import AddModExpr, LatentVariable, ProgramSpec, TheoryAST, VarExpr
from archimedes_v0.synthesis import (
    EnumerativeProgramSearch,
    EnumerativeSynthesizer,
    ProgramObservation,
)


def test_enumerative_search_recovers_simple_two_variable_law():
    observations = tuple(
        ProgramObservation(q=q, action=a, y=(q + a) % 8)
        for q in range(8)
        for a in range(8)
    )
    result = EnumerativeProgramSearch(search_ceiling=6000, max_depth=3).search(
        q_cardinality=8,
        latent_name="q",
        action_name="a",
        observations=observations,
        limit=32,
    )
    assert result.semantic_expressions_inspected <= 6000
    assert any(candidate.exact_accuracy == 1.0 for candidate in result.candidates)


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
    results = EnumerativeSynthesizer(semantic_search_ceiling=6000, max_depth=3).synthesize(
        paradigm="A",
        observations=observations,
        candidate_theories=(source,),
        frozen_a_theory=None,
        limit=4,
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
