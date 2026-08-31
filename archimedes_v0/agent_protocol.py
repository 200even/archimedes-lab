from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ast_schema import ExperimentAST, TheoryAST


class StrictAgentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CandidateSet(StrictAgentModel):
    candidates: list[TheoryAST] = Field(default_factory=list, max_length=4)


class ExperimentBatch(StrictAgentModel):
    experiments: list[ExperimentAST] = Field(min_length=1, max_length=10)


class ACommitDecision(StrictAgentModel):
    decision: Literal["commit", "abstain"]
    theory: TheoryAST | None = None

    @model_validator(mode="after")
    def decision_matches_payload(self):
        if self.decision == "commit" and self.theory is None:
            raise ValueError("commit requires a theory")
        if self.decision == "abstain" and self.theory is not None:
            raise ValueError("abstain must not include a theory")
        return self


class BCommitDecision(StrictAgentModel):
    theory: TheoryAST
