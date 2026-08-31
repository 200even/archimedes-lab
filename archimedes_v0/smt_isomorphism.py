from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json

from z3 import And, Distinct, If, Int, IntVal, Solver, sat, unsat

from .ast_schema import LatentVariable, ProgramSpec
from .constants import DOMAIN_SIZE
from .theory_eval import evaluate_expr


@dataclass(frozen=True)
class IsomorphismResult:
    isomorphic: bool
    solver_status: str
    table_digest_a: str
    table_digest_b: str


def _table(program: ProgramSpec, latent: LatentVariable) -> list[list[int]]:
    action_name = "x" if program.paradigm == "A" else "u"
    return [
        [evaluate_expr(program.expression, {latent.name: q, action_name: action}) for action in range(DOMAIN_SIZE)]
        for q in range(latent.cardinality)
    ]


def _digest(table: list[list[int]]) -> str:
    payload = json.dumps(table, separators=(",", ":"), sort_keys=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _lookup_2d(table: list[list[int]], q_expr, action_expr):
    # All domains are tiny and frozen, so a total nested If expression is simpler
    # and more auditable than an uninterpreted function.
    result = IntVal(table[-1][-1])
    for q in reversed(range(len(table))):
        for action in reversed(range(DOMAIN_SIZE)):
            result = If(And(q_expr == q, action_expr == action), IntVal(table[q][action]), result)
    return result


def truth_tables_are_isomorphic(table_a: list[list[int]], table_b: list[list[int]]) -> IsomorphismResult:
    """SMT-check finite structural isomorphism under opaque relabelings.

    The two paradigms are considered structurally isomorphic if there exist
    bijections over latent states, intervention symbols, and output symbols such
    that relabeling A produces B for every latent/action pair. This is deliberately
    stronger than exact expression equality and catches algebraic disguises caused
    by renamed opaque symbols or random output permutations.
    """
    if len(table_a) != len(table_b):
        return IsomorphismResult(False, "cardinality_mismatch", _digest(table_a), _digest(table_b))
    k = len(table_a)
    if not (1 <= k <= DOMAIN_SIZE):
        raise ValueError("invalid finite latent cardinality")
    if any(len(row) != DOMAIN_SIZE for row in table_a + table_b):
        raise ValueError("truth-table action dimension mismatch")

    solver = Solver()
    q_perm = [Int(f"q_perm_{i}") for i in range(k)]
    action_perm = [Int(f"a_perm_{i}") for i in range(DOMAIN_SIZE)]
    output_perm = [Int(f"y_perm_{i}") for i in range(DOMAIN_SIZE)]

    for value in q_perm:
        solver.add(value >= 0, value < k)
    solver.add(Distinct(*q_perm))
    for values in (action_perm, output_perm):
        for value in values:
            solver.add(value >= 0, value < DOMAIN_SIZE)
        solver.add(Distinct(*values))

    for q in range(k):
        for action in range(DOMAIN_SIZE):
            b_value = _lookup_2d(table_b, q_perm[q], action_perm[action])
            solver.add(output_perm[table_a[q][action]] == b_value)

    status = solver.check()
    if status == sat:
        return IsomorphismResult(True, "sat", _digest(table_a), _digest(table_b))
    if status == unsat:
        return IsomorphismResult(False, "unsat", _digest(table_a), _digest(table_b))
    raise RuntimeError(f"unexpected Z3 status: {status}")


def programs_are_isomorphic(program_a: ProgramSpec, program_b: ProgramSpec, latent: LatentVariable) -> IsomorphismResult:
    if program_a.paradigm != "A" or program_b.paradigm != "B":
        raise ValueError("expected one A program and one B program")
    return truth_tables_are_isomorphic(_table(program_a, latent), _table(program_b, latent))
