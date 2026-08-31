from pathlib import Path
import re

from archimedes_v0.agent_interfaces import StatelessConjecturer
from archimedes_v0.analysis_plan import hallucination_kill, null_false_positive_rate, paired_sign_flip_test
from archimedes_v0.ast_schema import (
    AddModExpr,
    ConstExpr,
    LatentVariable,
    MulModExpr,
    ProgramSpec,
    TheoryAST,
    VarExpr,
)
from archimedes_v0.diagnostics import functional_minimality
from archimedes_v0.neutral import neutral_theory
from archimedes_v0.orchestrator import A_BATCH_SIZES, B_BATCH_SIZES


def _theory(*, redundant: bool = False) -> TheoryAST:
    latent = LatentVariable(
        name="qhat",
        cardinality=2,
        assignments={f"entity_{i:02d}": i % 2 for i in range(16)},
    )
    q = VarExpr(name="qhat")
    x = VarExpr(name="x")
    if redundant:
        expression = AddModExpr(
            left=MulModExpr(left=q, right=ConstExpr(value=0)),
            right=x,
        )
    else:
        expression = AddModExpr(left=q, right=x)
    return TheoryAST(
        theory_id="T-test",
        latent_variables=[latent],
        programs=[ProgramSpec(paradigm="A", expression=expression)],
    )


def test_functional_minimality_detects_redundant_labels():
    minimal = functional_minimality(_theory(redundant=False))
    redundant = functional_minimality(_theory(redundant=True))
    assert minimal.functionally_minimal
    assert minimal.effective_cardinality == 2
    assert not redundant.functionally_minimal
    assert redundant.effective_cardinality == 1
    assert redundant.redundant_groups == ((0, 1),)


def test_neutral_theory_strips_roleplay_metadata():
    theory = _theory().model_copy(
        update={"status": "surviving", "evidence_experiment_ids": ["E-secret-prose-free"]}
    )
    value = neutral_theory(theory)
    assert value["status"] == "candidate"
    assert value["evidence_experiment_ids"] == []


def test_preregistered_round_schedule_matches_visible_budget():
    assert A_BATCH_SIZES == (10, 10, 10, 10, 10, 10)
    assert B_BATCH_SIZES == (7, 7, 7, 7)
    assert sum(A_BATCH_SIZES) == 60
    assert sum(B_BATCH_SIZES) == 28
    assert len(A_BATCH_SIZES) + len(B_BATCH_SIZES) == 10


def test_prompt_files_avoid_solution_leaking_instruction_words():
    banned = ("null", "hidden", "state", "property", "invariant", "concept")
    root = Path(__file__).resolve().parents[1] / "prompts"
    for name in ("conjecturer_system.txt", "critic_system.txt", "flat_system.txt"):
        text = (root / name).read_text().lower()
        for word in banned:
            assert re.search(rf"\b{re.escape(word)}\b", text) is None, (name, word)


class FakeBackend:
    def __init__(self):
        self.calls = []

    def invoke(self, **kwargs):
        self.calls.append(kwargs)
        return {"candidates": []}


def test_conjecturer_interface_uses_fresh_schema_bound_call():
    backend = FakeBackend()
    agent = StatelessConjecturer(backend, "fixed prompt")
    result = agent.propose_candidates({"observations": []})
    assert result.candidates == []
    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert set(call) == {"role", "system_prompt", "payload", "response_schema", "max_output_tokens"}
    assert call["role"] == "conjecturer"


def test_preregistered_primary_analysis_operates_at_world_level():
    comparison = paired_sign_flip_test([1.0] * 20, [0.0] * 20, draws=2000, seed=7)
    assert comparison.mean_difference == 1.0
    assert comparison.primary_success
    assert null_false_positive_rate([False, False, True, False]) == 0.25
    assert not hallucination_kill([False] * 96 + [True] * 4)
    assert hallucination_kill([False] * 95 + [True] * 5)
