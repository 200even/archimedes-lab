SCHEMA_VERSION = "0.1.2"

# PRE-CODE FREEZE — V0 binding constants.
DOMAIN_SIZE = 8
BIT_WIDTH = 3
NUM_ENTITIES = 16
LATENT_REPLICATION = 2  # each hidden q state occurs exactly twice

# Hidden-world generator grammar limits.
MAX_EXPRESSION_DEPTH = 6
PARADIGM_A_TEMPLATES = ("A1", "A2")
PARADIGM_B_TEMPLATES = ("B1", "B2")
ODD_MULTIPLIERS = (1, 3, 5, 7)
ROTATIONS = (1, 2)

# Measurement model.
MEASUREMENT_NOISE_RATE = 0.02

# Fixed broker budget per non-null world.
BROKER_BUDGET_TOTAL = 128
BUDGET_A_DISCOVERY = 64
BUDGET_B_CALIBRATION = 32
BUDGET_B_TRANSFER_EVAL = 32
assert BROKER_BUDGET_TOTAL == BUDGET_A_DISCOVERY + BUDGET_B_CALIBRATION + BUDGET_B_TRANSFER_EVAL

# Epistemic-cycle cap before falsification failure.
MAX_EPISTEMIC_CYCLES = 12

# D4 identity freeze. q is discrete: after A freeze, zero assignment changes are permitted.
STABLE_IDENTITY_MAX_ASSIGNMENT_CHANGES = 0

# Minimum exact fit required for the frozen A explanation and final B-calibration law.
D4_VISIBLE_FIT_ACCURACY_MIN = 0.90

# Prediction success threshold used for individual-world D4 qualification.
# Cross-world statistical comparison against Flat LLM + SR remains the primary claim.
D4_TRANSFER_ACCURACY_MIN = 0.90

# Null-world hallucination kill criterion.
NULL_WORLD_FPR_MAX = 0.05

# Critic qualification kill criterion.
CRITIC_CONSECUTIVE_FAILURES_MAX = 3

# Solvability / nontriviality filters.
MIN_UNIQUE_OUTPUTS_PER_Q = 4
MIN_UNIQUE_OUTPUTS_PER_ACTION_ACROSS_Q = 4
MAX_ACTION_ONLY_ACCURACY = 0.75
MAX_ENTITY_ONLY_ACCURACY = 0.75
MAX_CONSTANT_ACCURACY = 0.50
