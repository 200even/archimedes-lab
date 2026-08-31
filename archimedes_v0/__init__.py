"""Archimedes V0: preregistered hidden-world generator, broker, and pre-exposure agent interfaces."""

from .broker import BrokerError, ExperimentBroker, Phase
from .diagnostics import FunctionalMinimalityResult, functional_minimality
from .generator import generate_world, write_world_bundle
from .orchestrator import (
    ArchimedesOrchestrator,
    FlatBaselineOrchestrator,
    OrchestrationError,
    OrchestrationResult,
)

__all__ = [
    "ArchimedesOrchestrator",
    "BrokerError",
    "ExperimentBroker",
    "FlatBaselineOrchestrator",
    "FunctionalMinimalityResult",
    "OrchestrationError",
    "OrchestrationResult",
    "Phase",
    "functional_minimality",
    "generate_world",
    "write_world_bundle",
]
