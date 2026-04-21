from risk_landscaper.models import (
    AiSystem,
    EvaluationRef,
    GovernanceProvenance,
    Organization,
    Policy,
    PolicyProfile,
    PolicyRiskMapping,
    RiskCard,
    RiskConsequence,
    RiskControl,
    RiskImpact,
    RiskLandscape,
    RiskSource,
    RunReport,
    Stakeholder,
)
from risk_landscaper.stages.assess import (
    assess_risk_levels,
    compute_aims_coverage,
    compute_risk_level,
    _max_level,
)


def _make_report():
    return RunReport(model="test", policy_set="test", timestamp="2026-01-01")


# ---------------------------------------------------------------------------
# Risk level computation
# ---------------------------------------------------------------------------

def test_max_level_picks_highest():
    assert _max_level(["low", "high", "medium"]) == "high"


def test_max_level_ignores_none():
    assert _max_level([None, "medium", None]) == "medium"


def test_max_level_empty():
    assert _max_level([]) is None


def test_max_level_all_none():
    assert _max_level([None, None]) is None


def test_max_level_ignores_invalid():
    assert _max_level(["bogus", "low"]) == "low"


def test_compute_risk_level_matrix_high_high():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        risk_sources=[RiskSource(description="src", likelihood="high")],
        consequences=[RiskConsequence(description="con", severity="high")],
    )
    assert compute_risk_level(card) == "high"


def test_compute_risk_level_matrix_very_high_very_high():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        risk_sources=[RiskSource(description="src", likelihood="very_high")],
        consequences=[RiskConsequence(description="con", severity="very_high")],
    )
    assert compute_risk_level(card) == "very_high"


def test_compute_risk_level_matrix_low_low():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        risk_sources=[RiskSource(description="src", likelihood="low")],
        consequences=[RiskConsequence(description="con", severity="low")],
    )
    assert compute_risk_level(card) == "low"


def test_compute_risk_level_matrix_low_high():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        risk_sources=[RiskSource(description="src", likelihood="low")],
        consequences=[RiskConsequence(description="con", severity="high")],
    )
    assert compute_risk_level(card) == "medium"


def test_compute_risk_level_matrix_high_low():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        risk_sources=[RiskSource(description="src", likelihood="high")],
        consequences=[RiskConsequence(description="con", severity="low")],
    )
    assert compute_risk_level(card) == "medium"


def test_compute_risk_level_uses_max_across_chain():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        risk_sources=[
            RiskSource(description="s1", likelihood="low"),
            RiskSource(description="s2", likelihood="high"),
        ],
        consequences=[
            RiskConsequence(description="c1", severity="medium"),
            RiskConsequence(description="c2", severity="very_high"),
        ],
    )
    assert compute_risk_level(card) == "very_high"


def test_compute_risk_level_severity_only():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        consequences=[RiskConsequence(description="con", severity="high")],
    )
    assert compute_risk_level(card) == "high"


def test_compute_risk_level_impact_severity():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        risk_sources=[RiskSource(description="src", likelihood="medium")],
        impacts=[RiskImpact(description="imp", severity="very_high")],
    )
    assert compute_risk_level(card) == "high"


def test_compute_risk_level_no_data():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
    )
    assert compute_risk_level(card) is None


def test_compute_risk_level_likelihood_only_no_severity():
    card = RiskCard(
        risk_id="r1", risk_name="Test", risk_description="",
        risk_sources=[RiskSource(description="src", likelihood="high")],
    )
    assert compute_risk_level(card) is None


def test_assess_risk_levels_sets_on_landscape():
    landscape = RiskLandscape(risks=[
        RiskCard(
            risk_id="r1", risk_name="Enriched",
            risk_sources=[RiskSource(description="s", likelihood="high")],
            consequences=[RiskConsequence(description="c", severity="high")],
        ),
        RiskCard(risk_id="r2", risk_name="Bare"),
    ])
    report = _make_report()
    assess_risk_levels(landscape, report=report)

    assert landscape.risks[0].risk_level == "high"
    assert landscape.risks[1].risk_level is None

    events = [e for e in report.events if e["event"] == "risk_levels_computed"]
    assert len(events) == 1
    assert events[0]["computed"] == 1
    assert events[0]["total"] == 2


# ---------------------------------------------------------------------------
# AIMS coverage
# ---------------------------------------------------------------------------

def _make_profile(**kwargs):
    defaults = dict(
        organization=Organization(name="Test Org"),
        domain="test",
        stakeholders=[],
        policies=[],
        ai_systems=[],
    )
    defaults.update(kwargs)
    return PolicyProfile(**defaults)


def _make_landscape(**kwargs):
    defaults = dict(
        risks=[],
        policy_mappings=[],
        provenance=GovernanceProvenance(
            produced_by="risk-landscaper",
            governance_function="evaluate",
            review_status="draft",
        ),
    )
    defaults.update(kwargs)
    return RiskLandscape(**defaults)


def test_aims_a6_always_when_risks_exist():
    profile = _make_profile()
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA6" in result


def test_aims_a2_stakeholder_involvement():
    profile = _make_profile(stakeholders=[
        Stakeholder(name="staff", roles=["user"], involvement="intended"),
    ])
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA2" in result


def test_aims_a2_not_without_involvement():
    profile = _make_profile(stakeholders=[
        Stakeholder(name="staff", roles=["user"]),
    ])
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA2" not in result


def test_aims_a4_policy_governance():
    profile = _make_profile(policies=[
        Policy(policy_concept="P1", concept_definition="d", governance_function="direct"),
    ])
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA4" in result


def test_aims_a4_not_without_governance_function():
    profile = _make_profile(policies=[
        Policy(policy_concept="P1", concept_definition="d"),
    ])
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA4" not in result


def test_aims_a8_controls():
    profile = _make_profile()
    landscape = _make_landscape(risks=[
        RiskCard(
            risk_id="r1", risk_name="Test",
            controls=[RiskControl(description="c1")],
        ),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA8" in result


def test_aims_a8_not_without_controls():
    profile = _make_profile()
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA8" not in result


def test_aims_a9_evaluations():
    profile = _make_profile()
    landscape = _make_landscape(risks=[
        RiskCard(
            risk_id="r1", risk_name="Test",
            evaluations=[EvaluationRef(eval_id="e1")],
        ),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA9" in result


def test_aims_a9_not_without_evaluations():
    profile = _make_profile()
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA9" not in result


def test_aims_updates_provenance():
    profile = _make_profile(
        stakeholders=[Stakeholder(name="s", involvement="intended")],
        policies=[Policy(policy_concept="P", concept_definition="d", governance_function="direct")],
    )
    landscape = _make_landscape(risks=[
        RiskCard(
            risk_id="r1", risk_name="Test",
            controls=[RiskControl(description="c")],
        ),
    ])
    compute_aims_coverage(profile, landscape)
    assert set(landscape.provenance.aims_activities) == {"aimsA2", "aimsA4", "aimsA6", "aimsA8"}


def test_aims_per_card_tagging():
    profile = _make_profile()
    landscape = _make_landscape(risks=[
        RiskCard(
            risk_id="r1", risk_name="With controls",
            controls=[RiskControl(description="c")],
        ),
        RiskCard(risk_id="r2", risk_name="Bare"),
    ])
    compute_aims_coverage(profile, landscape)
    assert landscape.risks[0].aims_activities == ["aimsA6", "aimsA8"]
    assert landscape.risks[1].aims_activities == ["aimsA6"]


def test_aims_emits_report():
    profile = _make_profile()
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    report = _make_report()
    compute_aims_coverage(profile, landscape, report=report)
    events = [e for e in report.events if e["event"] == "aims_coverage_computed"]
    assert len(events) == 1
    assert "aimsA6" in events[0]["satisfied"]
    assert "aimsA9" in events[0]["gaps"]


def test_aims_no_risks_no_a6():
    profile = _make_profile()
    landscape = _make_landscape()
    result = compute_aims_coverage(profile, landscape)
    assert "aimsA6" not in result


def test_aims_creates_provenance_if_none():
    profile = _make_profile()
    landscape = _make_landscape(risks=[
        RiskCard(risk_id="r1", risk_name="Test"),
    ])
    landscape.provenance = None
    compute_aims_coverage(profile, landscape)
    assert landscape.provenance is not None
    assert "aimsA6" in landscape.provenance.aims_activities
