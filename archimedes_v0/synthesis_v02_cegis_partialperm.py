"""Exact partial-bijection encoding for PERMUTE inside the V0.2 CEGIS working set.

A CEGIS working set W observes only a finite subset of a candidate child's output
values.  Requiring all eight entries of every symbolic permutation table to form a
complete bijection at every intermediate SAT check introduces constraints on values
that W has not yet identified.  Those constraints are unnecessary: a partial map
from the child values actually realized on W extends to a full 8-element bijection
iff it is injective on those realized values.

This module therefore replaces full-table Distinct constraints inside the reduced
working-set problem with the exact partial-bijection condition:

    child(p_i) != child(p_j)  =>  permute(child(p_i)) != permute(child(p_j))

for every pair of points currently in W.  The trusted Python decoder then uses the
already-frozen lexicographically smallest completion for unseen inputs.  When W
covers all eight child values this condition is exactly a full bijection.

The transformation changes neither the Theory AST grammar nor the semantic
hypothesis class.  It only removes constraints on unobserved permutation entries
from intermediate CEGIS checks.
"""

from __future__ import annotations

import z3

from . import synthesis_v02_cegis as _cegis
from . import synthesis_v02_cegis_hardened as _hard
from .synthesis import (
    BINARY_OPS,
    OP_CONST_7,
    OP_INACTIVE,
    OP_PERMUTE,
    OP_Q,
    UNARY_OPS,
    _node_level,
    _or_selector,
)
from .synthesis_v02_cegis_lexscore import SMTProgramSearchV02CEGIS


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

            # Deliberately no full-table Distinct constraint here.  Exact
            # extendability to a bijection over the values observed by W is added
            # after semantic values have been constructed below.

            if level < self.max_depth:
                left_index = 2 * index + 1
                right_index = left_index + 1
                left_active = z3.Or(_or_selector(selector, UNARY_OPS), _or_selector(selector, BINARY_OPS))
                right_active = _or_selector(selector, BINARY_OPS)
                self.constraints.append((self.selector[left_index] != OP_INACTIVE) == left_active)
                self.constraints.append((self.selector[right_index] != OP_INACTIVE) == right_active)

    def _build_semantic_constraints_isolated(self) -> None:
        super()._build_semantic_constraints_isolated()

        # A partial function on an equal finite source/target domain can be
        # extended to a bijection exactly when distinct observed source values
        # have distinct observed images.  These pairwise implications are thus
        # necessary and sufficient, with no assumption about unseen child values.
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


# Both the hardened ordinary feasibility oracle and the exact lex-score oracle
# resolve this class through the hardened module at runtime.
_hard._IsolatedWorkingSetProblem = _PartialPermutationWorkingSetProblem
_cegis._WorkingSetProblem = _PartialPermutationWorkingSetProblem

SMTProgramSearch = SMTProgramSearchV02CEGIS
