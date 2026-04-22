from risk_landscaper.models import (
    Policy, PolicyProfile, PolicyDecomposition, BoundaryExample,
    Organization, Stakeholder, AiSystem, RiskMatch, PolicyRiskMapping,
    RiskCard, RiskDetail, RiskLandscape, CoverageGap, RunReport,
    RiskSource, RiskConsequence, RiskImpact, RiskControl,
    RiskIncidentRef, EvaluationRef, GovernanceProvenance,
    LandscapeSummary, SharedRisk, RiskRef, CausalChainStats, Comparison,
)


def test_policy_profile_round_trip():
    profile = PolicyProfile(
        organization=Organization(name="Acme Corp"),
        domain="finance",
        policies=[Policy(policy_concept="Fraud", concept_definition="Do not assist with fraud")],
    )
    data = profile.model_dump()
    restored = PolicyProfile(**data)
    assert restored.organization.name == "Acme Corp"
    assert len(restored.policies) == 1


def test_policy_profile_coerce_organization_string():
    profile = PolicyProfile(organization="Acme Corp")
    assert profile.organization.name == "Acme Corp"


def test_policy_profile_coerce_organization_from_legacy_stakeholder():
    data = {
        "organization": {"name": "Acme Corp", "roles": ["airo:AIDeveloper"]},
        "policies": [],
    }
    profile = PolicyProfile(**data)
    assert isinstance(profile.organization, Organization)
    assert profile.organization.name == "Acme Corp"


def test_policy_profile_migrate_governed_systems():
    data = {"governed_systems": [{"name": "ChatBot"}], "policies": []}
    profile = PolicyProfile(**data)
    assert len(profile.ai_systems) == 1
    assert profile.ai_systems[0].name == "ChatBot"


def test_risk_detail_is_risk_card():
    assert RiskDetail is RiskCard


def test_risk_card_identity_fields():
    card = RiskCard(
        risk_id="atlas-1", risk_name="Test Risk",
        risk_framework="IBM Risk Atlas",
        risk_type="output", descriptors=["amplified by generative AI"],
    )
    assert card.risk_type == "output"
    assert card.descriptors == ["amplified by generative AI"]


def test_risk_card_causal_chain():
    card = RiskCard(
        risk_id="atlas-bias", risk_name="Bias",
        risk_sources=[RiskSource(description="Skewed training data", source_type="data", likelihood="high")],
        consequences=[RiskConsequence(description="Discriminatory outputs", severity="high")],
        impacts=[RiskImpact(
            description="Denial of service to protected groups",
            severity="high", area="non_discrimination",
            affected_stakeholders=["loan applicants"],
            harm_type="allocative",
        )],
    )
    assert len(card.risk_sources) == 1
    assert card.risk_sources[0].source_type == "data"
    assert card.consequences[0].severity == "high"
    assert card.impacts[0].harm_type == "allocative"
    assert card.impacts[0].affected_stakeholders == ["loan applicants"]


def test_risk_card_controls():
    card = RiskCard(
        risk_id="atlas-1", risk_name="Test",
        controls=[
            RiskControl(description="Bias benchmark", control_type="evaluate", targets="risk"),
            RiskControl(description="Content filter", control_type="mitigate", targets="consequence"),
        ],
    )
    assert len(card.controls) == 2
    assert card.controls[0].control_type == "evaluate"
    assert card.controls[1].targets == "consequence"


def test_risk_card_evidence():
    card = RiskCard(
        risk_id="atlas-1", risk_name="Test",
        incidents=[RiskIncidentRef(name="Incident A", status="concluded", source_uri="https://example.com")],
        evaluations=[EvaluationRef(eval_id="eval-1", eval_type="garak", metrics={"acc": 0.87})],
    )
    assert card.incidents[0].status == "concluded"
    assert card.evaluations[0].metrics["acc"] == 0.87


def test_risk_card_governance_fields():
    card = RiskCard(
        risk_id="atlas-1", risk_name="Test",
        trustworthy_characteristics=["safety", "fairness"],
        aims_activities=["aimsA6", "aimsA8"],
        risk_level="high",
        related_policies=["fraud-prevention"],
        materialization_conditions="Model asked to generate content about protected groups",
    )
    assert "safety" in card.trustworthy_characteristics
    assert card.risk_level == "high"
    assert card.materialization_conditions is not None


def test_risk_card_backward_compat():
    card = RiskCard(
        risk_id="atlas-1", risk_name="Test",
        related_actions=["Minimize personal data"],
    )
    assert card.related_actions == ["Minimize personal data"]


def test_risk_landscape_serialization():
    landscape = RiskLandscape(
        model="test-model",
        risks=[RiskCard(risk_id="atlas-1", risk_name="Test Risk", risk_framework="IBM Risk Atlas")],
        policy_mappings=[PolicyRiskMapping(
            policy_concept="Fraud",
            matched_risks=[RiskMatch(risk_id="atlas-1", risk_name="Test Risk", relevance="primary", justification="Direct match")],
        )],
    )
    data = landscape.model_dump()
    assert data["version"] == "0.2"
    assert data["risks"][0]["risk_id"] == "atlas-1"
    restored = RiskLandscape(**data)
    assert len(restored.risks) == 1


def test_risk_landscape_provenance():
    landscape = RiskLandscape(
        model="test-model",
        provenance=GovernanceProvenance(
            produced_by="risk-landscaper",
            governance_function="evaluate",
            aims_activities=["aimsA6"],
            review_status="draft",
        ),
    )
    assert landscape.provenance.produced_by == "risk-landscaper"
    assert landscape.provenance.review_status == "draft"
    data = landscape.model_dump()
    restored = RiskLandscape(**data)
    assert restored.provenance.aims_activities == ["aimsA6"]


def test_organization_fields():
    org = Organization(
        name="HealthCo",
        governance_roles=["governing_body", "ai_team"],
        management_system="ISO/IEC 42001",
        certifications=["ISO 27001"],
        delegates=["External Auditor"],
    )
    assert org.governance_roles == ["governing_body", "ai_team"]
    assert org.management_system == "ISO/IEC 42001"


def test_stakeholder_involvement_fields():
    s = Stakeholder(
        name="Patient", roles=["airo:AISubject"],
        involvement="unintended", activity="passive",
        awareness="uninformed", output_control="cannot_opt_out",
        relationship="external", interests=["safety", "privacy"],
    )
    assert s.involvement == "unintended"
    assert s.output_control == "cannot_opt_out"
    assert s.interests == ["safety", "privacy"]


def test_policy_governance_function():
    p = Policy(
        policy_concept="Bias Testing",
        concept_definition="Run fairness benchmarks",
        governance_function="evaluate",
        affects_stakeholders=["loan applicants"],
        applies_to_systems=["credit-scorer"],
    )
    assert p.governance_function == "evaluate"
    assert p.affects_stakeholders == ["loan applicants"]


def test_ai_system_extended_fields():
    sys = AiSystem(
        name="Credit Scorer",
        modality="service",
        techniques=["deep_learning", "statistical_model"],
        automation_level="human_in_loop",
        serves_stakeholders=["bank customers"],
        assets=["transaction-data", "credit-model-v2"],
    )
    assert sys.modality == "service"
    assert sys.automation_level == "human_in_loop"
    assert sys.assets == ["transaction-data", "credit-model-v2"]


def test_coverage_gap_creation():
    gap = CoverageGap(
        policy_concept="Novel Risk", concept_definition="Something new",
        gap_type="novel", confidence=0.85,
        nearest_risks=[{"id": "atlas-1", "name": "Similar", "distance": 0.7}],
        reasoning="No existing risk covers this",
    )
    assert gap.gap_type == "novel"
    assert gap.confidence == 0.85


def test_policy_source_documents_default():
    p = Policy(policy_concept="Fraud", concept_definition="About fraud")
    assert p.source_documents == []


def test_policy_source_documents_set():
    p = Policy(
        policy_concept="Fraud", concept_definition="About fraud",
        source_documents=["policy.pdf", "faq.md"],
    )
    assert p.source_documents == ["policy.pdf", "faq.md"]


def test_policy_profile_source_documents_default():
    profile = PolicyProfile(policies=[])
    assert profile.source_documents == []


def test_policy_profile_source_documents_set():
    profile = PolicyProfile(
        policies=[],
        source_documents=["policy.pdf", "annex.docx"],
    )
    assert profile.source_documents == ["policy.pdf", "annex.docx"]


def test_policy_profile_round_trip_with_source_documents():
    profile = PolicyProfile(
        organization=Organization(name="Acme"),
        policies=[
            Policy(
                policy_concept="Fraud", concept_definition="About fraud",
                source_documents=["doc1.md"],
            ),
        ],
        source_documents=["doc1.md", "doc2.pdf"],
    )
    data = profile.model_dump()
    restored = PolicyProfile(**data)
    assert restored.source_documents == ["doc1.md", "doc2.pdf"]
    assert restored.policies[0].source_documents == ["doc1.md"]


def test_run_report_to_dict():
    report = RunReport(model="test", policy_set="test.json", timestamp="2026-01-01")
    report.stages_completed.append("ingest")
    d = report.to_dict()
    assert d["stages_completed"] == ["ingest"]


def test_landscape_summary_defaults():
    s = LandscapeSummary(name="test-run")
    assert s.organization is None
    assert s.domain == []
    assert s.risk_count == 0
    assert s.policy_count == 0
    assert s.timestamp == ""


def test_shared_risk_per_landscape():
    sr = SharedRisk(
        risk_id="r1",
        risk_name="Test Risk",
        risk_framework="NIST",
        per_landscape={"org-a": "high", "org-b": None},
    )
    assert sr.per_landscape["org-a"] == "high"
    assert sr.per_landscape["org-b"] is None


def test_risk_ref_minimal():
    r = RiskRef(risk_id="r1", risk_name="Test Risk")
    assert r.risk_framework is None
    assert r.risk_level is None


def test_causal_chain_stats_defaults():
    s = CausalChainStats()
    assert s.sources == 0
    assert s.consequences == 0
    assert s.impacts == 0
    assert s.controls == 0


def test_comparison_defaults():
    c = Comparison()
    assert c.version == "0.1"
    assert c.landscapes == []
    assert c.shared_risks == []
    assert c.unique_risks == {}
    assert c.framework_coverage == {}
    assert c.risk_level_distribution == {}
    assert c.coverage_gaps == {}
    assert c.causal_chain_stats == {}


def test_comparison_roundtrip():
    c = Comparison(
        landscapes=[LandscapeSummary(name="a", risk_count=3)],
        shared_risks=[SharedRisk(risk_id="r1", risk_name="R", per_landscape={"a": "high"})],
        unique_risks={"a": [RiskRef(risk_id="r2", risk_name="R2")]},
        causal_chain_stats={"a": CausalChainStats(sources=5, controls=2)},
    )
    d = c.model_dump()
    c2 = Comparison(**d)
    assert c2.landscapes[0].risk_count == 3
    assert c2.shared_risks[0].per_landscape == {"a": "high"}
    assert len(c2.unique_risks["a"]) == 1
    assert c2.causal_chain_stats["a"].sources == 5
