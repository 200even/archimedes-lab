"""Exact partial-bijection encoding for PERMUTE inside the V0.2 CEGIS working set.

A CEGIS working set W observes only a finite subset of a candidate child's output
values. Requiring all eight entries of every symbolic permutation table to form a
complete bijection at every intermediate SAT check introduces constraints on values
that W has not yet identified. Those constraints are unnecessary: a partial map
from the child values actually realized on W extends to a full 8-element bijection
iff it is injective on those realized values.

This module replaces full-table Distinct constraints inside the reduced working-set
problem with the exact partial-bijection condition

    child(p_i) != child(p_j)  =>  permute(child(p_i)) != permute(child(p_j))

for every pair of points currently in W. The model decoder then constructs the
lexicographically smallest full bijection extending the solver's assignments on
child values realized by W. When W covers all eight child values this condition is
exactly a full bijection.

The transformation changes neither the Theory AST grammar nor the semantic
hypothesis class. It only removes constraints on unobserved permutation entries
from intermediate CEGIS checks.
"""

from __future__ import annotations

import z3

from . import synthesis_v02_cegis as _cegis
from . import synthesis_v02_cegis_hardened as _hard
from .ast_schema import (
    AbsDiffExpr,
    AddModExpr,
    BitAndExpr,
    BitOrExpr,
    ConstExpr,
    EqMaskExpr,
    MaxU3Expr,
    MinU3Expr,
    MulModExpr,
    PermutationExpr,
    RotlExpr,
    VarExpr,
    XorExpr,
)
from .constants import DOMAIN_SIZE
from .synthesis import (
    BINARY_OPS,
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
    UNARY_OPS,
    _node_level,
    _or_selector,
)
from .synthesis_v02_cegis_lexscore import SMTProgramSearchV02CEGIS
from .theory_eval import evaluate_expr


class _PartialPermutationWorkingSetProblem(_hard._IsolatedWorkingSetProblem):
    """Invocation-local reduced-W problem with exact partial permutation semantics."""

    def _build_structure_constraints_isolated(self) -> None:
        self.constraints.append(self.selector[0] != OP_INACTIVE)
        self.constraints.extend((self.effective_depth >= 1, self.effective_depth <= self.max_depth))

        for index, selector in enumerate(self.selector):
            level = _node_level(index)
            self.constraints.append(z3.And(selector >= OP_Q, selector <= OP_INACTIVE))
            if level == self.max_depth:
                self.constraints.append(
                    z3.Or(selector == OP_INACTIVE, z3.And(selector >= OP_Q, selector <= OP_CONST_7))
                )

            active = selector != OP_INACTIVE
            self.constraints.append(self.effective_depth >= z3.If(active, level, 0))

            # No full-table Distinct constraint here. Exact extendability to a
            # bijection over values observed by W is enforced after semantic
            # values have been constructed below.
            if level < self.max_depth:
                left_index = 2 * index + 1
                right_index = left_index + 1
                left_active = z3.Or(_or_selector(selector, UNARY_OPS), _or_selector(selector, BINARY_OPS))
                right_active = _or_selector(selector, BINARY_OPS)
                self.constraints.append((self.selector[left_index] != OP_INACTIVE) == left_active)
                self.constraints.append((self.selector[right_index] != OP_INACTIVE) == right_active)

    def _build_semantic_constraints_isolated(self) -> None:
        super()._build_semantic_constraints_isolated()

        # A partial function on equal finite source/target domains extends to a
        # bijection iff distinct observed sources have distinct observed images.
        for index, selector in enumerate(self.selector):
            level = _node_level(index)
            if level >= self.max_depth:
                continue
            child_index = 2 * index + 1
            for first in range(len(self.points)):
                for second in range(first + 1, len(self.points)):
                    self.constraints.append(
                        z3.Implies(
                            z3.And(
                                selector == OP_PERMUTE,
                                self.values[child_index][first] != self.values[child_index][second],
                            ),
                            self.values[index][first] != self.values[index][second],
                        )
                    )

    def decode_expression(self, model):
        """Decode a SAT model, canonically completing partial permutation tables."""

        constructors = {
            OP_ADD_MOD: AddModExpr,
            OP_MUL_MOD: MulModExpr,
            OP_XOR: XorExpr,
            OP_BIT_AND: BitAndExpr,
            OP_BIT_OR: BitOrExpr,
            OP_MIN_U3: MinU3Expr,
            OP_MAX_U3: MaxU3Expr,
            OP_ABS_DIFF: AbsDiffExpr,
            OP_EQ_MASK: EqMaskExpr,
        }

        def decode(index: int):
            selector = model.eval(self.selector[index], model_completion=True).as_long()
            if selector == OP_Q:
                return VarExpr(name=self.latent_name)
            if selector == OP_ACTION:
                return VarExpr(name=self.action_name)
            if OP_CONST_0 <= selector <= OP_CONST_7:
                return ConstExpr(value=selector - OP_CONST_0)

            left_index = 2 * index + 1
            if selector == OP_ROTL_1:
                return RotlExpr(value=decode(left_index), shift=1)
            if selector == OP_ROTL_2:
                return RotlExpr(value=decode(left_index), shift=2)
            if selector == OP_PERMUTE:
                child = decode(left_index)
                required: dict[int, int] = {}
                for observation in self.observations:
                    env = {self.latent_name: observation.q, self.action_name: observation.action}
                    source = evaluate_expr(child, env)
                    target = model.eval(
                        self.values[index][self.point_index[(observation.q, observation.action)]],
                        model_completion=True,
                    ).as_long()
                    previous = required.get(source)
                    if previous is not None and previous != target:
                        raise AssertionError("partial permutation model is inconsistent on W")
                    required[source] = target

                if len(set(required.values())) != len(required):
                    raise AssertionError("partial permutation model is not injective on W")
                mapping = [-1] * DOMAIN_SIZE
                for source, target in required.items():
                    mapping[source] = target
                reserved = set(required.values())
                available = [value for value in range(DOMAIN_SIZE) if value not in reserved]
                cursor = 0
                for source in range(DOMAIN_SIZE):
                    if mapping[source] >= 0:
                        continue
                    mapping[source] = available[cursor]
                    cursor += 1
                return PermutationExpr(value=child, mapping=mapping)

            if selector not in constructors:
                raise AssertionError(f"cannot decode selector {selector}")
            right_index = left_index + 1
            return constructors[selector](left=decode(left_index), right=decode(right_index))

        return decode(0)


# Both the hardened ordinary feasibility oracle and the exact lex-score oracle
# resolve this class through the hardened module at runtime.
_hard._IsolatedWorkingSetProblem = _PartialPermutationWorkingSetProblem
_cegis._WorkingSetProblem = _PartialPermutationWorkingSetProblem

SMTProgramSearch = SMTProgramSearchV02CEGIS
