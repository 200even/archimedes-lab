"""Final authorized V0.2 CEGIS binding used by tests, qualification, and runtime.

The bound engine preserves the referee-authorized CEGIS policy, grammar, objective
hierarchy, and frozen solver resource envelope while incorporating only
prequalification engineering hardening discovered on independent synthetic
fixtures:

- reduced canonical working set W with trusted full-O verification;
- one cumulative 50M Z3 rlimit per search invocation;
- invocation-local Z3 Context isolation;
- removal of semantically dead non-permutation mapping constraints;
- canonical completion of permutation entries not identified by W;
- exact partial-bijection constraints for PERMUTE on the child values realized by
  the current CEGIS working set, with deterministic full-bijection completion; and
- the final preregistered feasible-incumbent-first anytime optimization schedule
  frozen in SYNTH_V02_FEASIBLE_FIRST_SCHEDULE_FREEZE.md.

No qualification corpus or Archimedes benchmark world was consulted in making
these corrections.
"""

from .synthesis_v02_cegis_feasiblefirst import SMTProgramSearchV02CEGIS

SMTProgramSearch = SMTProgramSearchV02CEGIS
