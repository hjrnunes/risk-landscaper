from risk_landscaper.models import (
    Organization,
    Stakeholder,
    AiSystem,
    RegulatoryReference,
    Policy,
    BoundaryExample,
    PolicyDecomposition,
    PolicyProfile,
)
from risk_landscaper.merge import (
    _union_lists,
    _merge_by_key,
    _merge_organizations,
    _merge_stakeholders,
    _merge_ai_systems,
    _merge_regulations,
    _merge_policies,
    merge_profiles,
)


def test_union_lists_no_overlap():
    assert _union_lists(["a", "b"], ["c", "d"]) == ["a", "b", "c", "d"]


def test_union_lists_with_overlap():
    assert _union_lists(["a", "b", "c"], ["b", "c", "d"]) == ["a", "b", "c", "d"]


def test_union_lists_preserves_order():
    assert _union_lists(["c", "a"], ["b", "a"]) == ["c", "a", "b"]


def test_union_lists_empty():
    assert _union_lists([], ["a"]) == ["a"]
    assert _union_lists(["a"], []) == ["a"]
    assert _union_lists([], []) == []


def test_merge_by_key_no_duplicates():
    items = [{"name": "a", "v": 1}, {"name": "b", "v": 2}]
    result = _merge_by_key(
        items,
        key_fn=lambda x: x["name"],
        merge_fn=lambda a, b: {**a, "v": a["v"] + b["v"]},
    )
    assert result == [{"name": "a", "v": 1}, {"name": "b", "v": 2}]


def test_merge_by_key_with_duplicates():
    items = [{"name": "a", "v": 1}, {"name": "a", "v": 2}, {"name": "b", "v": 3}]
    result = _merge_by_key(
        items,
        key_fn=lambda x: x["name"],
        merge_fn=lambda a, b: {**a, "v": a["v"] + b["v"]},
    )
    assert len(result) == 2
    assert result[0] == {"name": "a", "v": 3}
    assert result[1] == {"name": "b", "v": 3}


def test_merge_by_key_preserves_first_occurrence_order():
    items = [{"name": "c"}, {"name": "a"}, {"name": "c"}]
    result = _merge_by_key(
        items,
        key_fn=lambda x: x["name"],
        merge_fn=lambda a, b: a,
    )
    assert [r["name"] for r in result] == ["c", "a"]


def test_merge_organizations_union_lists():
    a = Organization(name="Acme", governance_roles=["CTO"], certifications=["SOC2"])
    b = Organization(name="Acme", governance_roles=["CTO", "Board"], certifications=["ISO27001"])
    result = _merge_organizations(a, b)
    assert result.name == "Acme"
    assert result.governance_roles == ["CTO", "Board"]
    assert result.certifications == ["SOC2", "ISO27001"]


def test_merge_organizations_prefer_first_scalars():
    a = Organization(name="Acme", management_system="ISO 42001")
    b = Organization(name="Acme", management_system="Internal", description="Corp")
    result = _merge_organizations(a, b)
    assert result.management_system == "ISO 42001"
    assert result.description == "Corp"


def test_merge_stakeholders_union_roles_and_interests():
    a = Stakeholder(name="staff", roles=["airo:AIUser"], interests=["efficiency"])
    b = Stakeholder(name="Staff", roles=["operator"], interests=["safety", "efficiency"])
    result = _merge_stakeholders(a, b)
    assert result.name == "staff"
    assert result.roles == ["airo:AIUser", "operator"]
    assert result.interests == ["efficiency", "safety"]


def test_merge_stakeholders_prefer_first_airo_fields():
    a = Stakeholder(name="patient", involvement="intended", activity=None)
    b = Stakeholder(name="patient", involvement="unintended", activity="passive")
    result = _merge_stakeholders(a, b)
    assert result.involvement == "intended"
    assert result.activity == "passive"


def test_merge_ai_systems_union_lists():
    a = AiSystem(name="Bot", purpose=["support"], techniques=["RAG"])
    b = AiSystem(name="Bot", purpose=["triage"], techniques=["RAG", "transformer"])
    result = _merge_ai_systems(a, b)
    assert result.purpose == ["support", "triage"]
    assert result.techniques == ["RAG", "transformer"]


def test_merge_ai_systems_prefer_first_scalars():
    a = AiSystem(name="Bot", modality="text-to-text")
    b = AiSystem(name="Bot", modality="multimodal", automation_level="full")
    result = _merge_ai_systems(a, b)
    assert result.modality == "text-to-text"
    assert result.automation_level == "full"


def test_merge_regulations_prefer_non_none():
    a = RegulatoryReference(name="GDPR", jurisdiction=None)
    b = RegulatoryReference(name="GDPR", jurisdiction="EU", reference="Art 22")
    result = _merge_regulations(a, b)
    assert result.jurisdiction == "EU"
    assert result.reference == "Art 22"


# --- _merge_policies tests ---


def test_merge_policies_union_boundary_examples():
    a = Policy(
        policy_concept="Fraud", concept_definition="Short def",
        boundary_examples=[BoundaryExample(prohibited="help fraud", acceptable="detect fraud")],
        acceptable_uses=["education"],
        source_documents=["doc1.md"],
    )
    b = Policy(
        policy_concept="Fraud", concept_definition="A longer and richer definition of fraud policy",
        boundary_examples=[
            BoundaryExample(prohibited="help fraud", acceptable="detect fraud"),
            BoundaryExample(prohibited="launder money", acceptable="flag suspicious"),
        ],
        acceptable_uses=["training"],
        source_documents=["doc2.md"],
    )
    result = _merge_policies(a, b)
    assert result.policy_concept == "Fraud"
    assert result.concept_definition == b.concept_definition  # longer wins
    assert len(result.boundary_examples) == 2  # deduplicated
    assert result.acceptable_uses == ["education", "training"]
    assert result.source_documents == ["doc1.md", "doc2.md"]


def test_merge_policies_prefer_first_scalars():
    a = Policy(
        policy_concept="AML", concept_definition="About AML",
        governance_function="direct", human_involvement="officer review",
    )
    b = Policy(
        policy_concept="AML", concept_definition="About AML",
        governance_function="evaluate", human_involvement="auto",
        decomposition=PolicyDecomposition(agent="bot", activity="scan", entity="txn"),
    )
    result = _merge_policies(a, b)
    assert result.governance_function == "direct"
    assert result.human_involvement == "officer review"
    assert result.decomposition is not None
    assert result.decomposition.agent == "bot"


def test_merge_policies_union_risk_controls():
    a = Policy(policy_concept="P", concept_definition="D", risk_controls=["human review"])
    b = Policy(policy_concept="P", concept_definition="D", risk_controls=["human review", "audit log"])
    result = _merge_policies(a, b)
    assert result.risk_controls == ["human review", "audit log"]


# --- merge_profiles tests ---


def test_merge_profiles_single():
    profile = PolicyProfile(
        organization=Organization(name="Acme"),
        domain="finance",
        policies=[Policy(policy_concept="Fraud", concept_definition="About fraud")],
    )
    result = merge_profiles([profile], ["doc1.md"])
    assert result.organization.name == "Acme"
    assert len(result.policies) == 1
    assert result.source_documents == ["doc1.md"]
    assert result.policies[0].source_documents == ["doc1.md"]


def test_merge_profiles_two_documents():
    a = PolicyProfile(
        organization=Organization(name="Acme"),
        domain="finance",
        purpose=["trading"],
        stakeholders=[Stakeholder(name="trader", roles=["airo:AIUser"])],
        ai_systems=[AiSystem(name="Bot", modality="text-to-text")],
        regulations=[RegulatoryReference(name="SEC")],
        policies=[
            Policy(policy_concept="Fraud", concept_definition="About fraud",
                   source_documents=["policy.md"]),
            Policy(policy_concept="AML", concept_definition="About AML",
                   source_documents=["policy.md"]),
        ],
    )
    b = PolicyProfile(
        organization=Organization(name="Acme", governance_roles=["CTO"]),
        domain="finance",
        purpose=["compliance"],
        stakeholders=[
            Stakeholder(name="trader", roles=["operator"]),
            Stakeholder(name="auditor", roles=["reviewer"]),
        ],
        ai_systems=[AiSystem(name="Bot", techniques=["RAG"])],
        regulations=[RegulatoryReference(name="SEC", jurisdiction="US")],
        policies=[
            Policy(policy_concept="Fraud", concept_definition="Detailed fraud prevention policy",
                   acceptable_uses=["detection training"],
                   source_documents=["faq.md"]),
            Policy(policy_concept="KYC", concept_definition="Know your customer",
                   source_documents=["faq.md"]),
        ],
    )
    result = merge_profiles([a, b], ["policy.md", "faq.md"])
    assert result.source_documents == ["policy.md", "faq.md"]
    assert result.organization.name == "Acme"
    assert result.organization.governance_roles == ["CTO"]
    assert result.purpose == ["trading", "compliance"]

    # Stakeholders merged by name (case-insensitive)
    assert len(result.stakeholders) == 2
    trader = next(s for s in result.stakeholders if s.name.lower() == "trader")
    assert "airo:AIUser" in trader.roles
    assert "operator" in trader.roles

    # AI systems merged
    bot = next(s for s in result.ai_systems if s.name == "Bot")
    assert bot.modality == "text-to-text"
    assert bot.techniques == ["RAG"]

    # Regulations merged
    sec = next(r for r in result.regulations if r.name == "SEC")
    assert sec.jurisdiction == "US"

    # Policies: Fraud merged (3 total: Fraud, AML, KYC)
    assert len(result.policies) == 3
    fraud = next(p for p in result.policies if p.policy_concept == "Fraud")
    assert fraud.concept_definition == "Detailed fraud prevention policy"  # longer
    assert fraud.acceptable_uses == ["detection training"]
    assert set(fraud.source_documents) == {"policy.md", "faq.md"}


def test_merge_profiles_empty():
    result = merge_profiles([], [])
    assert result.policies == []
    assert result.source_documents == []


def test_merge_profiles_different_orgs_uses_first():
    a = PolicyProfile(organization=Organization(name="Alpha"), policies=[])
    b = PolicyProfile(organization=Organization(name="Beta"), policies=[])
    result = merge_profiles([a, b], ["a.md", "b.md"])
    assert result.organization.name == "Alpha"


def test_merge_profiles_domain_keeps_longest():
    a = PolicyProfile(domain="finance", policies=[])
    b = PolicyProfile(domain="financial services", policies=[])
    result = merge_profiles([a, b], ["a.md", "b.md"])
    assert result.domain == "financial services"


def test_merge_profiles_case_insensitive_entity_merge():
    a = PolicyProfile(
        stakeholders=[Stakeholder(name="Staff", roles=["user"])],
        policies=[],
    )
    b = PolicyProfile(
        stakeholders=[Stakeholder(name="staff", roles=["operator"])],
        policies=[],
    )
    result = merge_profiles([a, b], ["a.md", "b.md"])
    assert len(result.stakeholders) == 1
    assert result.stakeholders[0].name == "Staff"  # first wins
    assert set(result.stakeholders[0].roles) == {"user", "operator"}
