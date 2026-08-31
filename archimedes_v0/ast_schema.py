from __future__ import annotations
from typing import Annotated, Literal, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .constants import SCHEMA_VERSION, DOMAIN_SIZE, BIT_WIDTH

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class VarExpr(StrictModel):
    kind: Literal["var"] = "var"
    name: str = Field(min_length=1, max_length=64)

class ConstExpr(StrictModel):
    kind: Literal["const"] = "const"
    value: int

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

Expr = Annotated[
    Union[VarExpr, ConstExpr, AddModExpr, MulModExpr, XorExpr, RotlExpr, PermutationExpr],
    Field(discriminator="kind"),
]

# Rebuild recursive models.
for cls in (AddModExpr, MulModExpr, XorExpr, RotlExpr, PermutationExpr):
    cls.model_rebuild()

class LatentVariable(StrictModel):
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
    scope: Literal["entity"] = "entity"
    domain_kind: Literal["categorical"] = "categorical"
    cardinality: Literal[DOMAIN_SIZE] = DOMAIN_SIZE
    assignments: dict[str, int]
    frozen: bool = False

    @model_validator(mode="after")
    def assignments_in_domain(self):
        if any(v < 0 or v >= DOMAIN_SIZE for v in self.assignments.values()):
            raise ValueError("latent assignment outside domain")
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
