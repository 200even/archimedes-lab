"""Final V0.2 CEGIS binding to the frozen, previously validated semantic skeleton.

The first CEGIS implementation duplicated `_SkeletonProblem.__init__` in order to
materialize only the current working-set points. Independent synthetic CI exposed
that duplicate encoding as inconsistent before qualification exposure. CEGIS does
not require a reduced semantic graph: it requires only that the *observation-error
constraint* be delivered through the monotonic working set W.

This module therefore binds the authorized CEGIS control loop to the unchanged
`_SkeletonProblem` implementation that was already validated before V0.2. The
hypothesis class, grammar, operator semantics, canonical order, working-set policy,
trusted full-data verifier, and cumulative Z3 rlimit are unchanged.
"""

from . import synthesis_v02_cegis as _cegis
from .synthesis import _SkeletonProblem

# `_cegis_feasible` resolves this module global at call time. Binding it to the
# frozen base skeleton removes the faulty duplicate semantic implementation while
# preserving the authorized CEGIS algorithm verbatim.
_cegis._WorkingSetProblem = _SkeletonProblem

SMTProgramSearchV02CEGIS = _cegis.SMTProgramSearchV02CEGIS
SMTProgramSearch = SMTProgramSearchV02CEGIS
