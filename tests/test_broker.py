import pytest

from archimedes_v0.ast_schema import (
    AddModExpr,
    ExperimentAST,
    Intervention,
    LatentVariable,
    ProgramSpec,
    TheoryAST,
    TheoryPrediction,
    VarExpr,
    XorExpr,
)
from archimedes_v0.broker import BrokerError, ExperimentBroker, Phase
from archimedes_v0.constants import (
    BUDGET_A_DISCOVERY,
    BUDGET_B_CALIBRATION,
    BUDGET_B_TRANSFER_EVAL,
    DOMAIN_SIZE,
    MAX_EPISTEMIC_CYCLES,
)
from archimedes_v0.generator import generate_world


def _one_hot(value: int) -> list[float]:
    return [1.0 if i == value else 0.0 for i in range(DOMAIN_SIZE)]


def _experiment(eid: str, paradigm: str, entity: str, action: int, theory_id: str = "T-main") -> ExperimentAST:
    return ExperimentAST(
        experiment_id=eid,
        objective="estimate",
        paradigm=paradigm,
        intervention=Intervention(entity_id=entity, action_value=action),
        target_theory_ids=[theory_id],
    )


def _a_theory(public, assignments=None) -> TheoryAST:
    if assignments is None:
        assignments = {e: i % DOMAIN_SIZE for i, e in enumerate(public.entities)}
    return TheoryAST(
        theory_id="T-main",
        latent_variables=[LatentVariable(name="qhat", assignments=assignments)],
        programs=[ProgramSpec(
            paradigm="A",
            expression=AddModExpr(left=VarExpr(name="qhat"), right=VarExpr(name="x")),
        )],
    )


def _b_theory_from(frozen: TheoryAST) -> TheoryAST:
    return TheoryAST(
        theory_id=frozen.theory_id,
        latent_variables=frozen.latent_variables,
        programs=[
            frozen.programs[0],
            ProgramSpec(paradigm="B", expression=XorExpr(left=VarExpr(name="qhat"), right=VarExpr(name="u"))),
        ],
    )


def _fill_a(broker: ExperimentBroker, public):
    for i in range(BUDGET_A_DISCOVERY):
        entity = public.entities[i % len(public.entities)]
        action = (i // len(public.entities)) % DOMAIN_SIZE
        broker.run_visible_experiment(_experiment(f"E-A-{i}", "A", entity, action))


def _fill_b(broker: ExperimentBroker, calibration_entities):
    for i in range(BUDGET_B_CALIBRATION):
        entity = calibration_entities[i % len(calibration_entities)]
        action = (i // len(calibration_entities)) % DOMAIN_SIZE
        broker.run_visible_experiment(_experiment(f"E-B-{i}", "B", entity, action))


def _ready_for_transfer(seed: int = 303):
    public, hidden, _ = generate_world(seed)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    _fill_a(broker, public)
    frozen = broker.freeze_a_theory(_a_theory(public))
    calibration = broker.open_b_calibration()
    _fill_b(broker, calibration)
    broker.submit_b_theory(_b_theory_from(frozen))
    return public, hidden, broker


def test_broker_enforces_phase_budget_and_freeze():
    public, hidden, _ = generate_world(101)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    with pytest.raises(BrokerError):
        broker.freeze_a_theory(_a_theory(public))
    _fill_a(broker, public)
    with pytest.raises(BrokerError):
        broker.run_visible_experiment(_experiment("E-A-over", "A", public.entities[0], 0))
    frozen = broker.freeze_a_theory(_a_theory(public))
    assert frozen.latent_variables[0].frozen is True
    calibration = broker.open_b_calibration()
    transfer_entity = next(iter(set(public.entities) - set(calibration)))
    with pytest.raises(BrokerError):
        broker.run_visible_experiment(_experiment("E-leak", "B", transfer_entity, 0))


def test_frozen_assignments_cannot_change_in_b():
    public, hidden, _ = generate_world(202)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    _fill_a(broker, public)
    frozen = broker.freeze_a_theory(_a_theory(public))
    calibration = broker.open_b_calibration()
    _fill_b(broker, calibration)
    bad = _b_theory_from(frozen)
    altered = dict(bad.latent_variables[0].assignments)
    altered[public.entities[0]] = (altered[public.entities[0]] + 1) % DOMAIN_SIZE
    bad_latent = bad.latent_variables[0].model_copy(update={"assignments": altered})
    bad = bad.model_copy(update={"latent_variables": [bad_latent]})
    with pytest.raises(BrokerError, match="frozen latent"):
        broker.submit_b_theory(bad)


def test_transfer_is_balanced_sealed_and_exactly_32():
    _, hidden, broker = _ready_for_transfer()
    challenges = broker.transfer_challenges()
    assert len(challenges) == BUDGET_B_TRANSFER_EVAL
    per_entity = {}
    for c in challenges:
        per_entity.setdefault(c.entity_id, set()).add(c.action_value)
    assert set(per_entity) == set(hidden.b_transfer_entities)
    assert all(len(actions) == 4 for actions in per_entity.values())

    for i, c in enumerate(challenges):
        exp = ExperimentAST(
            experiment_id=f"E-T-{i}",
            objective="estimate",
            paradigm="B",
            intervention=Intervention(entity_id=c.entity_id, action_value=c.action_value),
            target_theory_ids=["T-main"],
            predictions=[TheoryPrediction(theory_id="T-main", categorical_probabilities=_one_hot(0))],
        )
        broker.submit_transfer_prediction(c.challenge_id, exp)
        if i == 0:
            sealed = [r for r in broker.agent_ledger() if r["event_type"] == "sealed_transfer_experiment"]
            assert sealed[-1]["payload"]["observation"] == "SEALED_UNTIL_RUN_CLOSE"
            with pytest.raises(BrokerError):
                broker.closed_transfer_outcomes()

    assert broker.remaining_budget["total"] == 0
    result = broker.close_run()
    assert result.total == 32
    assert broker.phase == Phase.CLOSED
    assert len(broker.closed_transfer_outcomes()) == 32
    assert broker.verify_ledger()


def test_transfer_challenge_and_unique_argmax_are_enforced():
    _, _, broker = _ready_for_transfer(404)
    c = broker.transfer_challenges()[0]
    wrong = ExperimentAST(
        experiment_id="E-wrong",
        objective="estimate",
        paradigm="B",
        intervention=Intervention(entity_id=c.entity_id, action_value=(c.action_value + 1) % DOMAIN_SIZE),
        target_theory_ids=["T-main"],
        predictions=[TheoryPrediction(theory_id="T-main", categorical_probabilities=_one_hot(0))],
    )
    with pytest.raises(BrokerError, match="does not match"):
        broker.submit_transfer_prediction(c.challenge_id, wrong)

    tied = ExperimentAST(
        experiment_id="E-tied",
        objective="estimate",
        paradigm="B",
        intervention=Intervention(entity_id=c.entity_id, action_value=c.action_value),
        target_theory_ids=["T-main"],
        predictions=[TheoryPrediction(theory_id="T-main", categorical_probabilities=[0.5, 0.5, 0, 0, 0, 0, 0, 0])],
    )
    with pytest.raises(BrokerError, match="unique categorical argmax"):
        broker.submit_transfer_prediction(c.challenge_id, tied)


def test_cycle_cap_and_agent_view_do_not_leak_ground_truth():
    public, hidden, _ = generate_world(606)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    for expected in range(1, MAX_EPISTEMIC_CYCLES + 1):
        assert broker.start_epistemic_cycle() == expected
    with pytest.raises(BrokerError):
        broker.start_epistemic_cycle()
    _fill_a(broker, public)
    serialized = str(broker.agent_ledger())
    assert "latent_q_by_entity" not in serialized
    assert "program_a" not in serialized
    assert "program_b" not in serialized
    assert hidden.measurement_noise_key not in serialized
