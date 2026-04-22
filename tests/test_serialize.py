# tests/test_serialize.py
from risk_landscaper.models import RiskLandscape, RiskCard
from risk_landscaper.serialize import landscape_to_jsonld


def test_empty_landscape_has_context_and_type():
    landscape = RiskLandscape(run_slug="test-run", timestamp="2026-04-22T10:00:00Z")
    result = landscape_to_jsonld(landscape)
    assert "@context" in result
    ctx = result["@context"]
    assert ctx["airo"] == "https://w3id.org/airo#"
    assert ctx["vair"] == "https://w3id.org/vair#"
    assert ctx["nexus"] == "https://ibm.github.io/ai-atlas-nexus/ontology/"
    assert ctx["dpv"] == "https://w3id.org/dpv#"
    assert ctx["rl"] == "https://trustyai.io/risk-landscaper/"
    assert result["@type"] == "rl:RiskLandscape"
    assert result["@id"] == "rl:test-run"
    assert result["rl:version"] == "0.2"
    assert result["rl:hasRiskCard"] == []


def test_minimal_risk_card():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(risk_id="bias-discrimination-output", risk_name="Bias/Discrimination in Output"),
        ],
    )
    result = landscape_to_jsonld(landscape)
    cards = result["rl:hasRiskCard"]
    assert len(cards) == 1
    card = cards[0]
    assert card["@id"] == "nexus:bias-discrimination-output"
    assert card["@type"] == "airo:Risk"
    assert card["rdfs:label"] == "Bias/Discrimination in Output"


def test_none_fields_omitted():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(risk_id="test-risk", risk_name="Test"),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    assert "rl:materializationConditions" not in card
    assert "rl:riskConcern" not in card
    assert "airo:hasConsequence" not in card
    assert "airo:hasImpact" not in card
