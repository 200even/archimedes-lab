"""Final authorized V0.2 CEGIS binding.

Independent synthetic-fixture testing exposed one resource-accounting defect in
the first CEGIS draft before qualification exposure: Z3 5.1.0.0 reports
`rlimit count` cumulatively, so charging the raw statistic to each fresh solver
exhausted the external 50M ledger after one SAT check.

The authorized CEGIS architecture requires a reduced working-set semantic graph:
Z3 reasons only over the canonical monotonic working set W, while the trusted
Python evaluator checks every returned AST against the complete observation set O.
That reduction is the mechanism that removes the monolithic full-matrix constraint
bottleneck without changing the bounded AST hypothesis class.

This binding therefore keeps the CEGIS working-set problem and charges only the
measured per-check delta in Z3's deterministic rlimit statistic. Every fresh
solver is still capped at the remaining invocation budget, so total mechanical
compute cannot exceed the single frozen resource envelope.
"""

from __future__ import annotations

from dataclasses import dataclass

import z3

from . import synthesis_v02_cegis as _cegis
from .synthesis import Z3_RANDOM_SEED, _rlimit_count


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

        # In the frozen Z3 package the statistic contains a pre-check baseline.
        # Only the delta around this check is chargeable to this invocation.
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
            # The trusted full-O evaluator may accept a model that consumes the
            # final resource unit; only a subsequent required check is forbidden.
            return status, solver.model()
        return status, None


# `_cegis_feasible` resolves the budget class at call time. The working-set
# problem remains the native reduced-point implementation in `synthesis_v02_cegis`.
_cegis._CumulativeBudget = _DeltaCumulativeBudget

SMTProgramSearchV02CEGIS = _cegis.SMTProgramSearchV02CEGIS
SMTProgramSearch = SMTProgramSearchV02CEGIS
