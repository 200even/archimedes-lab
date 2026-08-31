import math

SCHEMA_VERSION = "0.1.3"

# PRE-CODE FREEZE — V0 binding constants.
DOMAIN_SIZE = 8
BIT_WIDTH = 3
NUM_ENTITIES = 16

# A2 latent-cardinality safeguard. Candidate concepts are finite discrete latent
# variables whose cardinality is inferred, but cannot exceed floor(sqrt(|E|)).
MIN_LATENT_CARDINALITY = 2
MAX_LATENT_CARDINALITY = math.floor(math.sqrt(NUM_ENTITIES))  # 4 for V0
HIDDEN_LATENT_CARDINALITIES = tuple(range(MIN_LATENT_CARDINALITY, MAX_LATENT_CARDINALITY + 1))
MIN_ENTITIES_PER_LATENT_STATE = 2

# Hidden-world generator grammar limits.
MAX_EXPRESSION_DEPTH = 6
PARADIGM_A_TEMPLATES = ("A1", "A2")
PARADIGM_B_TEMPLATES = ("B1", "B2")
ODD_MULTIPLIERS = (1, 3, 5, 7)
ROTATIONS = (1, 2)

# Measurement model.
MEASUREMENT_NOISE_RATE = 0.02

# Fixed V0.1.3 resource budget. Theory-gate evaluations are deliberately charged
# against the same 128-unit budget as interventions, preventing free rejection
# sampling against visible data. Exactly one A gate and one B gate are permitted.
BROKER_BUDGET_TOTAL = 128
BUDGET_A_DISCOVERY = 60
BUDGET_A_THEORY_EVAL = 4
BUDGET_B_CALIBRATION = 28
BUDGET_B_THEORY_EVAL = 4
BUDGET_B_TRANSFER_EVAL = 32
assert BROKER_BUDGET_TOTAL == (
    BUDGET_A_DISCOVERY
    + BUDGET_A_THEORY_EVAL
    + BUDGET_B_CALIBRATION
    + BUDGET_B_THEORY_EVAL
    + BUDGET_B_TRANSFER_EVAL
)
MAX_A_THEORY_GATE_ATTEMPTS = 1
MAX_B_THEORY_GATE_ATTEMPTS = 1

# Epistemic-cycle cap before falsification failure.
MAX_EPISTEMIC_CYCLES = 12

# D4 identity freeze. After A freeze, zero changes are permitted to assignments,
# latent cardinality, domain kind, or geometry.
STABLE_IDENTITY_MAX_ASSIGNMENT_CHANGES = 0
LATENT_DOMAIN_KIND = "finite_discrete"
LATENT_GEOMETRY = "unsigned_bitvector3"

# Minimum exact fit required for the single committed A explanation and final
# single committed B-calibration law. A failed gate closes the world; no retry.
D4_VISIBLE_FIT_ACCURACY_MIN = 0.90

# Prediction success threshold used for individual-world D4 qualification.
# Cross-world comparison against Flat LLM + SR remains the primary claim.
D4_TRANSFER_ACCURACY_MIN = 0.90

# Null-world hallucination kill criterion.
NULL_WORLD_FPR_MAX = 0.05

# Critic qualification kill criterion.
CRITIC_CONSECUTIVE_FAILURES_MAX = 3

# Solvability / nontriviality filters.
MIN_UNIQUE_OUTPUTS_PER_Q = 4
MIN_UNIQUE_OUTPUTS_PER_ACTION_ACROSS_Q = 4  # validation uses min(this, true k)
MAX_ACTION_ONLY_ACCURACY = 0.75
MAX_ENTITY_ONLY_ACCURACY = 0.75
MAX_CONSTANT_ACCURACY = 0.50
