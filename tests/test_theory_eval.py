import pytest

from archimedes_v0.ast_schema import AddModExpr, ConstExpr, ProgramSpec, VarExpr, XorExpr
from archimedes_v0.theory_eval import evaluate_expr, operator_signature, validate_program_structure, TheoryEvaluationError


def test_expression_evaluator_and_operator_signature():
    expr = AddModExpr(left=VarExpr(name="q"), right=VarExpr(name="x"))
    assert evaluate_expr(expr, {"q": 7, "x": 2}) == 1
    assert operator_signature(expr) == frozenset(["add_mod"])


def test_program_requires_latent_and_action():
    program = ProgramSpec(paradigm="A", expression=AddModExpr(left=VarExpr(name="q"), right=ConstExpr(value=1)))
    with pytest.raises(TheoryEvaluationError, match="intervention"):
        validate_program_structure(program, "q", "x")


def test_arithmetic_and_bitwise_signatures_are_disjoint():
    a = AddModExpr(left=VarExpr(name="q"), right=VarExpr(name="x"))
    b = XorExpr(left=VarExpr(name="q"), right=VarExpr(name="u"))
    assert operator_signature(a).isdisjoint(operator_signature(b))
