from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .constants import (
    SCHEMA_VERSION,
    DOMAIN_SIZE,
    BIT_WIDTH,
    MIN_LATENT_CARDINALITY,
    MAX_LATENT_CARDINALITY,
    MIN_ENTITIES_PER_LATENT_STATE,
    LATENT_DOMAIN_KIND,
    LATENT_GEOMETRY,
)

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class VarExpr(StrictModel):
    kind: Literal["var"] = "var"
    name: str = Field(min_length=1, max_length=64)

class ConstExpr(StrictModel):
    kind: Literal["const"] = "const"
    value: int = Field(ge=0, lt=DOMAIN_SIZE)

class AddModExpr(StrictModel):
    kind: Literal["add_mod"] = "add_mod"
    left: "Expr"
    right: "Expr"
    modulus: Literal[DOMAIN_SIZE] = DOMAIN_SIZE

class MulModExpr(StrictModel):
    kind: Literal["mul_mod"] = "mul_mod"
    left: "Expr"
    right: "Expr"
    modulus: Literal[DOMAIN_SIZE] = DOMAIN_SIZE

class XorExpr(StrictModel):
    kind: Literal["xor"] = "xor"
    left: "Expr"
    right: "Expr"

class RotlExpr(StrictModel):
    kind: Literal["rotl"] = "rotl"
    value: "Expr"
    width: Literal[BIT_WIDTH] = BIT_WIDTH
    shift: Literal[1, 2]

class PermutationExpr(StrictModel):
    kind: Literal["permute"] = "permute"
    value: "Expr"
    mapping: list[int] = Field(min_length=DOMAIN_SIZE, max_length=DOMAIN_SIZE)

    @model_validator(mode="after")
    def valid_permutation(self):
        if sorted(self.mapping) != list(range(DOMAIN_SIZE)):
            raise ValueError("mapping must be a permutation of 0..DOMAIN_SIZE-1")
        return self

# V0.1.3 B2 distractors. All operate on the same 3-bit finite domain as the true
# operators; none requires a foreign float/string type that would make it trivial
# to reject from the schema alone.
class BitAndExpr(StrictModel):
    kind: Literal["bit_and"] = "bit_and"
    left: "Expr"
    right: "Expr"

class BitOrExpr(StrictModel):
    kind: Literal["bit_or"] = "bit_or"
    left: "Expr"
    right: "Expr"

class MinU3Expr(StrictModel):
    kind: Literal["min_u3"] = "min_u3"
    left: "Expr"
    right: "Expr"

class MaxU3Expr(StrictModel):
    kind: Literal["max_u3"] = "max_u3"
    left: "Expr"
    right: "Expr"

class AbsDiffExpr(StrictModel):
    kind: Literal["abs_diff"] = "abs_diff"
    left: "Expr"
    right: "Expr"

class EqMaskExpr(StrictModel):
    kind: Literal["eq_mask"] = "eq_mask"
    left: "Expr"
    right: "Expr"

Expr = Annotated[
    Union[
        VarExpr,
        ConstExpr,
        AddModExpr,
        MulModExpr,
        XorExpr,
        RotlExpr,
        PermutationExpr,
        BitAndExpr,
        BitOrExpr,
        MinU3Expr,
        MaxU3Expr,
        AbsDiffExpr,
        EqMaskExpr,
    ],
    Field(discriminator="kind"),
]

# Rebuild recursive models.
for cls in (
    AddModExpr,
    MulModExpr,
    XorExpr,
    RotlExpr,
    PermutationExpr,
    BitAndExpr,
    BitOrExpr,
    MinU3Expr,
    MaxU3Expr,
    AbsDiffExpr,
    EqMaskExpr,
):
    cls.model_rebuild()

class LatentVariable(StrictModel):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
    scope: Literal["entity"] = "entity"
    domain_kind: Literal[LATENT_DOMAIN_KIND] = LATENT_DOMAIN_KIND
    geometry: Literal[LATENT_GEOMETRY] = LATENT_GEOMETRY
    cardinality: int = Field(ge=MIN_LATENT_CARDINALITY, le=MAX_LATENT_CARDINALITY)
    assignments: dict[str, int]
    frozen: bool = False

    @model_validator(mode="after")
    def assignments_in_domain(self):
        if any(v < 0 or v >= self.cardinality for v in self.assignments.values()):
            raise ValueError("latent assignment outside declared cardinality")
        used = set(self.assignments.values())
        if used != set(range(self.cardinality)):
            raise ValueError("latent assignments must use every declared state exactly as labels 0..k-1")
        counts = {state: sum(v == state for v in self.assignments.values()) for state in used}
        if any(count < MIN_ENTITIES_PER_LATENT_STATE for count in counts.values()):
            raise ValueError("each latent state must cover at least two entities")
        return self

class ProgramSpec(StrictModel):
    paradigm: Literal["A", "B"]
    output_name: Literal["y"] = "y"
    expression: Expr

class TheoryAST(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    theory_id: str = Field(pattern=r"^T-[A-Za-z0-9_-]{1,48}$")
    latent_variables: list[LatentVariable] = Field(max_length=4)
    programs: list[ProgramSpec] = Field(max_length=2)
    status: Literal["candidate", "surviving", "falsified"] = "candidate"
    evidence_experiment_ids: list[str] = Field(default_factory=list, max_length=512)

class Intervention(StrictModel):
    entity_id: str = Field(pattern=r"^entity_[0-9]{2}$")
    action_value: int = Field(ge=0, lt=DOMAIN_SIZE)

class TheoryPrediction(StrictModel):
    theory_id: str = Field(pattern=r"^T-[A-Za-z0-9_-]{1,48}$")
    categorical_probabilities: list[float] = Field(min_length=DOMAIN_SIZE, max_length=DOMAIN_SIZE)

    @model_validator(mode="after")
    def valid_distribution(self):
        if any(p < 0 or p > 1 for p in self.categorical_probabilities):
            raise ValueError("probability outside [0,1]")
        if abs(sum(self.categorical_probabilities) - 1.0) > 1e-6:
            raise ValueError("probabilities must sum to 1")
        return self

class FalsificationRule(StrictModel):
    theory_id: str = Field(pattern=r"^T-[A-Za-z0-9_-]{1,48}$")
    metric: Literal["categorical_nll"] = "categorical_nll"
    threshold: float = Field(gt=0)

class ExperimentAST(StrictModel):
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    experiment_id: str = Field(pattern=r"^E-[A-Za-z0-9_-]{1,48}$")
    objective: Literal["discriminate", "falsify", "estimate"]
    paradigm: Literal["A", "B"]
    intervention: Intervention
    target_theory_ids: list[str] = Field(min_length=1, max_length=16)
    predictions: list[TheoryPrediction] = Field(default_factory=list, max_length=16)
    falsification_rules: list[FalsificationRule] = Field(default_factory=list, max_length=16)
