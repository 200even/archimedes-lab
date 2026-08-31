import pytest

from archimedes_v0.ast_schema import (
    AddModExpr,
    ExperimentAST,
    Intervention,
    LatentVariable,
    ProgramSpec,
    TheoryAST,
    VarExpr,
    XorExpr,
)
from archimedes_v0.broker import BrokerError, ExperimentBroker, Phase
from archimedes_v0.constants import BUDGET_A_DISCOVERY, BUDGET_B_CALIBRATION, DOMAIN_SIZE, MAX_EPISTEMIC_CYCLES
from archimedes_v0.generator import generate_world
from archimedes_v0.grammar import Program


def _experiment(eid: str, paradigm: str, entity: str, action: int) -> ExperimentAST:
    return ExperimentAST(
        experiment_id=eid,
        objective="estimate",
        paradigm=paradigm,
        intervention=Intervention(entity_id=entity, action_value=action),
        target_theory_ids=["T-main"],
    )


def _ground_truth_theory(public, hidden, *, include_b=False) -> TheoryAST:
    q = dict(hidden.latent_q_by_entity)
    latent = LatentVariable(name="qhat", assignments=q)

    def program_expr(spec, paradigm):
        p = Program(**spec)
        params = p.params
        qv = VarExpr(name="qhat")
        av = VarExpr(name="x" if paradigm == "A" else "u")
        from archimedes_v0.ast_schema import ConstExpr, MulModExpr, PermutationExpr, RotlExpr
        if p.template == "A1":
            two_q_plus_one = AddModExpr(left=MulModExpr(left=ConstExpr(value=2), right=qv), right=ConstExpr(value=1))
            ax_c1 = AddModExpr(left=MulModExpr(left=ConstExpr(value=params["a"]), right=av), right=ConstExpr(value=params["c1"]))
            inner = AddModExpr(left=AddModExpr(left=qv, right=MulModExpr(left=two_q_plus_one, right=ax_c1)), right=ConstExpr(value=params["c2"]))
        elif p.template == "A2":
            inner = AddModExpr(left=AddModExpr(left=qv, right=MulModExpr(left=ConstExpr(value=params["a"]), right=av)), right=ConstExpr(value=params["c1"]))
        elif p.template == "B1":
            inner = XorExpr(left=RotlExpr(value=qv, shift=params["r"]), right=RotlExpr(value=av, shift=params["s"]))
        elif p.template == "B2":
            inner = XorExpr(
                left=RotlExpr(value=XorExpr(left=qv, right=ConstExpr(value=params["c1"])), shift=params["r"]),
                right=XorExpr(left=av, right=ConstExpr(value=params["c2"])),
            )
        else:
            raise AssertionError(p.template)
        return PermutationExpr(value=inner, mapping=params["perm"])

    programs = [ProgramSpec(paradigm="A", expression=program_expr(hidden.program_a, "A"))]
    if include_b:
        programs.append(ProgramSpec(paradigm="B", expression=program_expr(hidden.program_b, "B")))
    return TheoryAST(theory_id="T-main", latent_variables=[latent], programs=programs)


def _fill_a(broker, public):
    for i in range(BUDGET_A_DISCOVERY):
        entity = public.entities[i % len(public.entities)]
        action = (i // len(public.entities)) % DOMAIN_SIZE
        broker.run_visible_experiment(_experiment(f"E-A-{i}", "A", entity, action))


def _fill_b(broker, calibration):
    for i in range(BUDGET_B_CALIBRATION):
        entity = calibration[i % len(calibration)]
        action = (i // len(calibration)) % DOMAIN_SIZE
        broker.run_visible_experiment(_experiment(f"E-B-{i}", "B", entity, action))


def test_broker_full_valid_path_uses_theory_derived_transfer_predictions():
    public, hidden, _ = generate_world(303)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    _fill_a(broker, public)
    frozen = broker.freeze_a_theory(_ground_truth_theory(public, hidden))
    assert frozen.latent_variables[0].frozen
    calibration = broker.open_b_calibration()
    _fill_b(broker, calibration)
    broker.submit_b_theory(_ground_truth_theory(public, hidden, include_b=True))
    challenges = broker.transfer_challenges()
    assert len(challenges) == 32
    result = broker.execute_transfer_evaluation()
    assert broker.phase == Phase.CLOSED
    assert result.a_fit_accuracy >= .90
    assert result.b_calibration_fit_accuracy >= .90
    assert result.operator_diverse
    assert result.exact_accuracy >= .90
    assert result.qualifies
    assert broker.verify_ledger()
    assert len(broker.closed_transfer_outcomes()) == 32


def test_bad_a_theory_cannot_be_frozen():
    public, hidden, _ = generate_world(101)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    _fill_a(broker, public)
    bad = TheoryAST(
        theory_id="T-main",
        latent_variables=[LatentVariable(name="qhat", assignments={e: i % 8 for i, e in enumerate(public.entities)})],
        programs=[ProgramSpec(paradigm="A", expression=AddModExpr(left=VarExpr(name="qhat"), right=VarExpr(name="x")))],
    )
    with pytest.raises(BrokerError, match="below frozen threshold"):
        broker.freeze_a_theory(bad)


def test_a_program_and_latent_cannot_change_after_freeze():
    public, hidden, _ = generate_world(202)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    _fill_a(broker, public)
    broker.freeze_a_theory(_ground_truth_theory(public, hidden))
    calibration = broker.open_b_calibration()
    _fill_b(broker, calibration)

    final = _ground_truth_theory(public, hidden, include_b=True)
    altered = dict(final.latent_variables[0].assignments)
    altered[public.entities[0]] = (altered[public.entities[0]] + 1) % 8
    final = final.model_copy(update={"latent_variables": [final.latent_variables[0].model_copy(update={"assignments": altered})]})
    with pytest.raises(BrokerError, match="frozen latent"):
        broker.submit_b_theory(final)


def test_visible_agent_view_does_not_leak_hidden_state():
    public, hidden, _ = generate_world(606)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    _fill_a(broker, public)
    text = str(broker.agent_ledger())
    assert "latent_q_by_entity" not in text
    assert "program_a" not in text
    assert "program_b" not in text
    assert hidden.measurement_noise_key not in text


def test_epistemic_cycle_cap():
    public, hidden, _ = generate_world(505)
    broker = ExperimentBroker.from_generated_world(public, hidden)
    for expected in range(1, MAX_EPISTEMIC_CYCLES + 1):
        assert broker.start_epistemic_cycle() == expected
    with pytest.raises(BrokerError):
        broker.start_epistemic_cycle()
