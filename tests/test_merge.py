from risk_landscaper.models import (
    Organization,
    Stakeholder,
    AiSystem,
    RegulatoryReference,
)
from risk_landscaper.merge import (
    _union_lists,
    _merge_by_key,
    _merge_organizations,
    _merge_stakeholders,
    _merge_ai_systems,
    _merge_regulations,
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
