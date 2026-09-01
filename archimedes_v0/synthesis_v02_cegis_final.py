"""Final authorized V0.2 CEGIS binding used by tests, qualification, and runtime.

The bound engine preserves the referee-authorized CEGIS policy and frozen solver
resource envelope while incorporating prequalification engineering hardening found
strictly on independent synthetic fixtures:

- reduced canonical working set W with trusted full-O verification;
- one cumulative 50M Z3 rlimit per search invocation;
- invocation-local Z3 Context isolation;
- removal of semantically dead non-permutation mapping constraints; and
- canonical completion of permutation entries not identified by W.

No qualification corpus or Archimedes benchmark world was consulted in making
these corrections.
"""

from .synthesis_v02_cegis_hardened import SMTProgramSearchV02CEGIS

SMTProgramSearch = SMTProgramSearchV02CEGIS
