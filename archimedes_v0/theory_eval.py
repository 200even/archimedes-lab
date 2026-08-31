from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .ast_schema import (
    AbsDiffExpr,
    AddModExpr,
    BitAndExpr,
    BitOrExpr,
    ConstExpr,
    EqMaskExpr,
    Expr,
    MaxU3Expr,
    MinU3Expr,
    MulModExpr,
    PermutationExpr,
    ProgramSpec,
    RotlExpr,
    TheoryAST,
    VarExpr,
    XorExpr,
)
from .constants import BIT_WIDTH, DOMAIN_SIZE


class TheoryEvaluationError(ValueError):
    pass


def _rotl(value: int, shift: int) -> int:
    mask = (1 << BIT_WIDTH) - 1
    value &= mask
    return ((value << shift) | (value >> (BIT_WIDTH - shift))) & mask


def evaluate_expr(expr: Expr, env: dict[str, int]) -> int:
    if isinstance(expr, VarExpr):
        if expr.name not in env:
            raise TheoryEvaluationError(f"unknown variable {expr.name!r}")
        value = env[expr.name]
    elif isinstance(expr, ConstExpr):
        value = expr.value
    elif isinstance(expr, AddModExpr):
        value = (evaluate_expr(expr.left, env) + evaluate_expr(expr.right, env)) % expr.modulus
    elif isinstance(expr, MulModExpr):
        value = (evaluate_expr(expr.left, env) * evaluate_expr(expr.right, env)) % expr.modulus
    elif isinstance(expr, XorExpr):
        value = evaluate_expr(expr.left, env) ^ evaluate_expr(expr.right, env)
    elif isinstance(expr, RotlExpr):
        value = _rotl(evaluate_expr(expr.value, env), expr.shift)
    elif isinstance(expr, PermutationExpr):
        child = evaluate_expr(expr.value, env)
        if not 0 <= child < DOMAIN_SIZE:
            raise TheoryEvaluationError("permutation input outside V0 domain")
        value = expr.mapping[child]
    elif isinstance(expr, BitAndExpr):
        value = evaluate_expr(expr.left, env) & evaluate_expr(expr.right, env)
    elif isinstance(expr, BitOrExpr):
        value = evaluate_expr(expr.left, env) | evaluate_expr(expr.right, env)
    elif isinstance(expr, MinU3Expr):
        value = min(evaluate_expr(expr.left, env), evaluate_expr(expr.right, env))
    elif isinstance(expr, MaxU3Expr):
        value = max(evaluate_expr(expr.left, env), evaluate_expr(expr.right, env))
    elif isinstance(expr, AbsDiffExpr):
        value = abs(evaluate_expr(expr.left, env) - evaluate_expr(expr.right, env))
    elif isinstance(expr, EqMaskExpr):
        value = (DOMAIN_SIZE - 1) if evaluate_expr(expr.left, env) == evaluate_expr(expr.right, env) else 0
    else:  # pragma: no cover - protected by the discriminated schema
        raise TheoryEvaluationError(f"unsupported expression type {type(expr)!r}")

    if not 0 <= value < DOMAIN_SIZE:
        raise TheoryEvaluationError("expression output outside V0 domain")
    return value


def variables_used(expr: Expr) -> frozenset[str]:
    if isinstance(expr, VarExpr):
        return frozenset([expr.name])
    if isinstance(expr, ConstExpr):
        return frozenset()
    if isinstance(expr, (AddModExpr, MulModExpr, XorExpr, BitAndExpr, BitOrExpr, MinU3Expr, MaxU3Expr, AbsDiffExpr, EqMaskExpr)):
        return variables_used(expr.left) | variables_used(expr.right)
    if isinstance(expr, (RotlExpr, PermutationExpr)):
        return variables_used(expr.value)
    raise TheoryEvaluationError(f"unsupported expression type {type(expr)!r}")


def operator_signature(expr: Expr) -> frozenset[str]:
    """Return nontrivial operator kinds, ignoring variables/constants/final relabeling."""
    if isinstance(expr, (VarExpr, ConstExpr)):
        return frozenset()
    if isinstance(expr, AddModExpr):
        return frozenset(["add_mod"]) | operator_signature(expr.left) | operator_signature(expr.right)
    if isinstance(expr, MulModExpr):
        return frozenset(["mul_mod"]) | operator_signature(expr.left) | operator_signature(expr.right)
    if isinstance(expr, XorExpr):
        return frozenset(["xor"]) | operator_signature(expr.left) | operator_signature(expr.right)
    if isinstance(expr, RotlExpr):
        return frozenset(["rotl"]) | operator_signature(expr.value)
    if isinstance(expr, PermutationExpr):
        return operator_signature(expr.value)
    if isinstance(expr, BitAndExpr):
        return frozenset(["bit_and"]) | operator_signature(expr.left) | operator_signature(expr.right)
    if isinstance(expr, BitOrExpr):
        return frozenset(["bit_or"]) | operator_signature(expr.left) | operator_signature(expr.right)
    if isinstance(expr, MinU3Expr):
        return frozenset(["min_u3"]) | operator_signature(expr.left) | operator_signature(expr.right)
    if isinstance(expr, MaxU3Expr):
        return frozenset(["max_u3"]) | operator_signature(expr.left) | operator_signature(expr.right)
    if isinstance(expr, AbsDiffExpr):
        return frozenset(["abs_diff"]) | operator_signature(expr.left) | operator_signature(expr.right)
    if isinstance(expr, EqMaskExpr):
        return frozenset(["eq_mask"]) | operator_signature(expr.left) | operator_signature(expr.right)
    raise TheoryEvaluationError(f"unsupported expression type {type(expr)!r}")


def expression_depth(expr: Expr) -> int:
    if isinstance(expr, (VarExpr, ConstExpr)):
        return 1
    if isinstance(expr, (AddModExpr, MulModExpr, XorExpr, BitAndExpr, BitOrExpr, MinU3Expr, MaxU3Expr, AbsDiffExpr, EqMaskExpr)):
        return 1 + max(expression_depth(expr.left), expression_depth(expr.right))
    if isinstance(expr, (RotlExpr, PermutationExpr)):
        return 1 + expression_depth(expr.value)
    raise TheoryEvaluationError(f"unsupported expression type {type(expr)!r}")


def validate_program_structure(program: ProgramSpec, latent_name: str, action_name: str) -> None:
    vars_used = variables_used(program.expression)
    allowed = {latent_name, action_name}
    unknown = vars_used - allowed
    if unknown:
        raise TheoryEvaluationError(f"program uses unknown variables: {sorted(unknown)}")
    if latent_name not in vars_used:
        raise TheoryEvaluationError("program does not use the frozen latent representation")
    if action_name not in vars_used:
        raise TheoryEvaluationError("program does not use the intervention variable")
    if not operator_signature(program.expression):
        raise TheoryEvaluationError("program has no nontrivial interaction operator")


def program_for(theory: TheoryAST, paradigm: str) -> ProgramSpec:
    matches = [p for p in theory.programs if p.paradigm == paradigm]
    if len(matches) != 1:
        raise TheoryEvaluationError(f"theory must contain exactly one {paradigm} program")
    return matches[0]


def predict(theory: TheoryAST, paradigm: str, entity_id: str, action_value: int) -> int:
    if len(theory.latent_variables) != 1:
        raise TheoryEvaluationError("V0 evaluator requires exactly one latent variable")
    latent = theory.latent_variables[0]
    if entity_id not in latent.assignments:
        raise TheoryEvaluationError(f"missing latent assignment for {entity_id}")
    action_name = "x" if paradigm == "A" else "u"
    program = program_for(theory, paradigm)
    validate_program_structure(program, latent.name, action_name)
    return evaluate_expr(program.expression, {latent.name: latent.assignments[entity_id], action_name: action_value})


@dataclass(frozen=True)
class FitScore:
    correct: int
    total: int
    exact_accuracy: float


def score_observations(theory: TheoryAST, paradigm: str, observations: Iterable[dict]) -> FitScore:
    obs = [o for o in observations if o["paradigm"] == paradigm]
    if not obs:
        raise TheoryEvaluationError(f"no {paradigm} observations to score")
    correct = sum(
        predict(theory, paradigm, o["entity_id"], o["action_value"]) == o["y"]
        for o in obs
    )
    return FitScore(correct=correct, total=len(obs), exact_accuracy=correct / len(obs))
