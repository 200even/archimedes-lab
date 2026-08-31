import pytest
from pydantic import ValidationError

from archimedes_v0.ast_schema import LatentVariable
from archimedes_v0.constants import MAX_LATENT_CARDINALITY, NUM_ENTITIES
from archimedes_v0.smt_isomorphism import truth_tables_are_isomorphic


def test_latent_cardinality_cannot_memorize_one_state_per_entity():
    assignments = {f"entity_{i:02d}": i for i in range(NUM_ENTITIES)}
    with pytest.raises(ValidationError):
        LatentVariable(name="qhat", cardinality=NUM_ENTITIES, assignments=assignments)
    assert MAX_LATENT_CARDINALITY == 4


def test_each_declared_latent_state_must_be_reused():
    assignments = {f"entity_{i:02d}": 0 for i in range(NUM_ENTITIES)}
    assignments["entity_15"] = 1
    with pytest.raises(ValidationError, match="at least two entities"):
        LatentVariable(name="qhat", cardinality=2, assignments=assignments)


def test_smt_detects_isomorphism_under_opaque_relabeling():
    k = 4
    a = [[(q + x) % 8 for x in range(8)] for q in range(k)]
    action_perm = [3, 2, 1, 0, 7, 6, 5, 4]
    output_perm = [4, 5, 6, 7, 0, 1, 2, 3]
    b = [[output_perm[a[q][action_perm[x]]] for x in range(8)] for q in range(k)]
    result = truth_tables_are_isomorphic(a, b)
    assert result.isomorphic
    assert result.solver_status == "sat"


def test_smt_proves_nonisomorphism_when_row_structure_differs():
    k = 4
    a = [[(q + x) % 8 for x in range(8)] for q in range(k)]
    b = [[0 for _ in range(8)]] + [[(q + x) % 8 for x in range(8)] for q in range(1, k)]
    result = truth_tables_are_isomorphic(a, b)
    assert not result.isomorphic
    assert result.solver_status == "unsat"
