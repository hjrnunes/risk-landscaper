from risk_landscaper.models import (
    RiskLandscape,
    RiskCard,
    RiskSource,
    RiskConsequence,
    RiskImpact,
    RiskControl,
    PolicyRiskMapping,
    RiskMatch,
    PolicyProfile,
    Organization,
    Policy,
    PolicySourceRef,
    CoverageGap,
)
from risk_landscaper.compare import build_comparison


def _make_landscape(
    risks: list[RiskCard],
    mappings: list[PolicyRiskMapping] | None = None,
    framework_coverage: dict[str, int] | None = None,
    coverage_gaps: list[CoverageGap] | None = None,
    selected_domains: list[str] | None = None,
    policy_source: PolicySourceRef | None = None,
) -> RiskLandscape:
    return RiskLandscape(
        run_slug="test",
        timestamp="2026-01-01T00:00:00Z",
        risks=risks,
        policy_mappings=mappings or [],
        framework_coverage=framework_coverage or {},
        coverage_gaps=coverage_gaps or [],
        selected_domains=selected_domains or [],
        policy_source=policy_source,
    )


def _make_profile(
    org_name: str = "TestOrg",
    domain: str = "test",
    policies: list[Policy] | None = None,
) -> PolicyProfile:
    return PolicyProfile(
        organization=Organization(name=org_name),
        domain=domain,
        policies=policies or [],
    )


def _make_risk(
    risk_id: str,
    risk_name: str = "Risk",
    risk_framework: str = "Test",
    risk_level: str | None = None,
    sources: int = 0,
    consequences: int = 0,
    impacts: int = 0,
    controls: int = 0,
) -> RiskCard:
    return RiskCard(
        risk_id=risk_id,
        risk_name=risk_name,
        risk_framework=risk_framework,
        risk_level=risk_level,
        risk_sources=[RiskSource(description=f"src-{i}") for i in range(sources)],
        consequences=[RiskConsequence(description=f"cons-{i}") for i in range(consequences)],
        impacts=[RiskImpact(description=f"imp-{i}") for i in range(impacts)],
        controls=[RiskControl(description=f"ctrl-{i}") for i in range(controls)],
    )


# --- Landscape summaries ---


def test_comparison_landscape_summaries():
    la = _make_landscape(
        risks=[_make_risk("r1"), _make_risk("r2")],
        selected_domains=["finance"],
        policy_source=PolicySourceRef(organization="Alpha", domain="finance", policy_count=3),
    )
    pa = _make_profile(org_name="Alpha", domain="finance", policies=[
        Policy(policy_concept="P1", concept_definition="D1"),
        Policy(policy_concept="P2", concept_definition="D2"),
        Policy(policy_concept="P3", concept_definition="D3"),
    ])
    lb = _make_landscape(
        risks=[_make_risk("r1")],
        selected_domains=["gov"],
        policy_source=PolicySourceRef(organization="Beta", domain="gov", policy_count=1),
    )
    pb = _make_profile(org_name="Beta", domain="gov", policies=[
        Policy(policy_concept="P1", concept_definition="D1"),
    ])

    result = build_comparison([("alpha", la, pa), ("beta", lb, pb)])
    assert len(result.landscapes) == 2
    assert result.landscapes[0].name == "alpha"
    assert result.landscapes[0].organization == "Alpha"
    assert result.landscapes[0].risk_count == 2
    assert result.landscapes[0].policy_count == 3
    assert result.landscapes[1].name == "beta"
    assert result.landscapes[1].risk_count == 1


# --- Shared and unique risks ---


def test_shared_and_unique_risks():
    la = _make_landscape(risks=[
        _make_risk("r1", risk_level="high"),
        _make_risk("r2", risk_level="low"),
    ])
    lb = _make_landscape(risks=[
        _make_risk("r1", risk_level="very_high"),
        _make_risk("r3"),
    ])
    pa = _make_profile()
    pb = _make_profile()

    result = build_comparison([("a", la, pa), ("b", lb, pb)])

    assert len(result.shared_risks) == 1
    assert result.shared_risks[0].risk_id == "r1"
    assert result.shared_risks[0].per_landscape == {"a": "high", "b": "very_high"}

    assert len(result.unique_risks["a"]) == 1
    assert result.unique_risks["a"][0].risk_id == "r2"
    assert len(result.unique_risks["b"]) == 1
    assert result.unique_risks["b"][0].risk_id == "r3"


def test_shared_risks_three_landscapes():
    """Shared = present in 2+ landscapes."""
    la = _make_landscape(risks=[_make_risk("r1"), _make_risk("r2")])
    lb = _make_landscape(risks=[_make_risk("r1"), _make_risk("r3")])
    lc = _make_landscape(risks=[_make_risk("r2"), _make_risk("r3"), _make_risk("r4")])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p), ("c", lc, p)])

    shared_ids = {sr.risk_id for sr in result.shared_risks}
    assert shared_ids == {"r1", "r2", "r3"}

    assert len(result.unique_risks.get("a", [])) == 0
    assert len(result.unique_risks.get("b", [])) == 0
    assert len(result.unique_risks["c"]) == 1
    assert result.unique_risks["c"][0].risk_id == "r4"


def test_shared_risk_per_landscape_none_when_absent():
    """If a risk is shared (in 2+) but not in all, absent entries are None."""
    la = _make_landscape(risks=[_make_risk("r1", risk_level="high")])
    lb = _make_landscape(risks=[_make_risk("r1", risk_level="low")])
    lc = _make_landscape(risks=[_make_risk("r2")])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p), ("c", lc, p)])

    r1_shared = next(sr for sr in result.shared_risks if sr.risk_id == "r1")
    assert r1_shared.per_landscape == {"a": "high", "b": "low", "c": None}


# --- Framework coverage ---


def test_framework_coverage():
    la = _make_landscape(risks=[], framework_coverage={"NIST": 3, "IBM": 2})
    lb = _make_landscape(risks=[], framework_coverage={"IBM": 1, "OWASP": 4})
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p)])
    assert result.framework_coverage["a"] == {"NIST": 3, "IBM": 2}
    assert result.framework_coverage["b"] == {"IBM": 1, "OWASP": 4}


# --- Risk level distribution ---


def test_risk_level_distribution():
    la = _make_landscape(risks=[
        _make_risk("r1", risk_level="high"),
        _make_risk("r2", risk_level="high"),
        _make_risk("r3", risk_level=None),
    ])
    lb = _make_landscape(risks=[
        _make_risk("r1", risk_level="very_high"),
    ])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p)])
    assert result.risk_level_distribution["a"]["high"] == 2
    assert result.risk_level_distribution["a"]["unassessed"] == 1
    assert result.risk_level_distribution["b"]["very_high"] == 1


# --- Coverage gaps ---


def test_coverage_gaps_per_landscape():
    gap = CoverageGap(
        policy_concept="Novel Policy",
        concept_definition="Something new",
        gap_type="novel",
        confidence=0.8,
        nearest_risks=[],
        reasoning="No match found",
    )
    la = _make_landscape(risks=[], coverage_gaps=[gap])
    lb = _make_landscape(risks=[], coverage_gaps=[])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p)])
    assert len(result.coverage_gaps["a"]) == 1
    assert result.coverage_gaps["a"][0].policy_concept == "Novel Policy"
    assert len(result.coverage_gaps["b"]) == 0


# --- Causal chain stats ---


def test_causal_chain_stats():
    la = _make_landscape(risks=[
        _make_risk("r1", sources=3, consequences=2, impacts=1, controls=4),
        _make_risk("r2", sources=1, consequences=0, impacts=2, controls=0),
    ])
    lb = _make_landscape(risks=[
        _make_risk("r1", sources=0, consequences=1, impacts=0, controls=2),
    ])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p)])
    assert result.causal_chain_stats["a"].sources == 4
    assert result.causal_chain_stats["a"].consequences == 2
    assert result.causal_chain_stats["a"].impacts == 3
    assert result.causal_chain_stats["a"].controls == 4
    assert result.causal_chain_stats["b"].sources == 0
    assert result.causal_chain_stats["b"].controls == 2


# --- Timestamp ---


def test_comparison_has_timestamp():
    la = _make_landscape(risks=[])
    p = _make_profile()
    result = build_comparison([("a", la, p)])
    assert result.timestamp != ""


# --- Edge case: single landscape ---


def test_single_landscape_no_shared():
    la = _make_landscape(risks=[_make_risk("r1")])
    p = _make_profile()
    result = build_comparison([("a", la, p)])
    assert result.shared_risks == []
    assert len(result.unique_risks["a"]) == 1
