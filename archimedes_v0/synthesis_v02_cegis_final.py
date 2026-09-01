"""Final authorized V0.2 CEGIS binding.

Independent synthetic-fixture testing exposed two implementation defects before
qualification exposure:

1. the first CEGIS draft duplicated `_SkeletonProblem` semantics unnecessarily;
2. Z3 5.1.0.0 reports `rlimit count` cumulatively, so charging the raw statistic
   to each fresh solver exhausted the external 50M ledger after one SAT check.

This binding fixes both without changing the preregistered hypothesis class or
CEGIS policy. It uses the frozen base semantic skeleton and charges only the
measured per-check delta in Z3's deterministic rlimit statistic. Every fresh
solver is still capped at the *remaining* invocation budget, so total mechanical
compute cannot exceed the single frozen budget.
"""

from __future__ import annotations

from dataclasses import dataclass

import z3

from . import synthesis_v02_cegis as _cegis
from .synthesis import Z3_RANDOM_SEED, _SkeletonProblem, _rlimit_count


@dataclass
class _DeltaCumulativeBudget:
    """Single deterministic Z3 resource ledger using per-check statistic deltas."""

    limit: int
    remaining: int
    used: int = 0
    checks: int = 0
    exhausted: bool = False
    last_reason_unknown: str | None = None

    @classmethod
    def create(cls, limit: int) -> "_DeltaCumulativeBudget":
        return cls(limit=limit, remaining=limit)

    def check(self, base_constraints: tuple, extra_constraints: tuple = ()):
        if self.remaining <= 0:
            self.exhausted = True
            self.last_reason_unknown = "cumulative rlimit exhausted"
            return z3.unknown, None

        solver = z3.Solver()
        solver.set(auto_config=True)
        solver.set(random_seed=Z3_RANDOM_SEED)
        solver.set(timeout=0)
        solver.set(rlimit=self.remaining)
        solver.add(*base_constraints)
        if extra_constraints:
            solver.add(*extra_constraints)

        # In the frozen Z3 package the `rlimit count` statistic includes prior
        # work in the process/context. Its delta around solver.check() is the
        # deterministic resource consumed by this invocation.
        before = _rlimit_count(solver.statistics())
        self.checks += 1
        status = solver.check()
        after = _rlimit_count(solver.statistics())
        consumed = after - before
        if consumed <= 0:
            consumed = 1
        consumed = min(consumed, self.remaining)
        self.used += consumed
        self.remaining -= consumed

        if status == z3.unknown:
            self.last_reason_unknown = solver.reason_unknown()
            self.exhausted = True
            return status, None
        if status == z3.sat:
            # A SAT model may be the full-observation-valid candidate even when
            # it consumes the final resource unit. The trusted evaluator gets to
            # verify it before a subsequent check declares exhaustion.
            return status, solver.model()
        return status, None


# `_cegis_feasible` resolves these globals at call time. Both bindings preserve
# the authorized CEGIS control loop while removing prequalification implementation
# defects found solely on independent synthetic fixtures.
_cegis._WorkingSetProblem = _SkeletonProblem
_cegis._CumulativeBudget = _DeltaCumulativeBudget

SMTProgramSearchV02CEGIS = _cegis.SMTProgramSearchV02CEGIS
SMTProgramSearch = SMTProgramSearchV02CEGIS
