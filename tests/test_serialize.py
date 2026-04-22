# tests/test_serialize.py
from risk_landscaper.models import RiskLandscape, RiskCard, RiskSource, RiskConsequence, RiskImpact, RiskControl, RiskIncidentRef, EvaluationRef
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


def test_risk_sources_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                risk_sources=[
                    RiskSource(description="Biased training data", source_type="data", likelihood="likely"),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    sources = card["airo:isRiskSourceFor"]
    assert len(sources) == 1
    src = sources[0]
    assert src["@type"] == ["airo:RiskSource", "vair:DataRiskSource"]
    assert src["rdfs:comment"] == "Biased training data"
    assert src["airo:hasLikelihood"] == "likely"


def test_consequences_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                consequences=[
                    RiskConsequence(description="Discriminatory outputs", likelihood="possible", severity="high"),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    cons = card["airo:hasConsequence"]
    assert len(cons) == 1
    assert cons[0]["@type"] == "airo:Consequence"
    assert cons[0]["rdfs:comment"] == "Discriminatory outputs"
    assert cons[0]["airo:hasLikelihood"] == "possible"
    assert cons[0]["airo:hasSeverity"] == "high"


def test_impacts_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                impacts=[
                    RiskImpact(
                        description="Users denied services",
                        severity="high",
                        area="Right",
                        affected_stakeholders=["end users", "applicants"],
                        harm_type="DiscriminatoryTreatment",
                    ),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    impacts = card["airo:hasImpact"]
    assert len(impacts) == 1
    imp = impacts[0]
    assert imp["@type"] == ["airo:Impact", "vair:DiscriminatoryTreatment"]
    assert imp["airo:hasSeverity"] == "high"
    assert imp["airo:hasImpactOnArea"] == "vair:Right"
    assert imp["airo:hasImpactOnStakeholder"] == ["end users", "applicants"]


def test_control_type_mapping():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                controls=[
                    RiskControl(description="Monitor for bias", control_type="detect"),
                    RiskControl(description="Run benchmarks", control_type="evaluate"),
                    RiskControl(description="Apply guardrails", control_type="mitigate"),
                    RiskControl(description="Remove feature", control_type="eliminate"),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    controls = card["airo:modifiesRiskConcept"]
    assert len(controls) == 4
    assert controls[0]["rl:controlFunction"] == "airo:detectsRiskConcept"
    assert controls[1]["rl:controlFunction"] == "rl:evaluatesRiskConcept"
    assert controls[2]["rl:controlFunction"] == "airo:mitigatesRiskConcept"
    assert controls[3]["rl:controlFunction"] == "airo:eliminatesRiskConcept"
    assert all(c["@type"] == "airo:RiskControl" for c in controls)


def test_incidents_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                incidents=[
                    RiskIncidentRef(
                        name="COMPAS Recidivism",
                        description="Racial bias in sentencing",
                        source_uri="https://example.com/compas",
                        status="concluded",
                    ),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    incidents = card["dpv:Incident"]
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc["@type"] == "dpv:Incident"
    assert inc["rdfs:label"] == "COMPAS Recidivism"
    assert inc["rdfs:comment"] == "Racial bias in sentencing"
    assert inc["rdfs:seeAlso"] == "https://example.com/compas"
    assert inc["rl:incidentStatus"] == "concluded"


def test_evaluations_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                evaluations=[
                    EvaluationRef(
                        eval_id="eval-001",
                        eval_type="lm-eval",
                        summary="TruthfulQA pass rate",
                        metrics={"pass_rate": 0.95},
                        source_uri="https://example.com/eval",
                    ),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    evals = card["rl:evaluation"]
    assert len(evals) == 1
    ev = evals[0]
    assert ev["@type"] == "rl:Evaluation"
    assert ev["@id"] == "eval-001"
    assert ev["rl:evalType"] == "lm-eval"
    assert ev["rdfs:comment"] == "TruthfulQA pass rate"
    assert ev["rl:metrics"] == {"pass_rate": 0.95}
    assert ev["rdfs:seeAlso"] == "https://example.com/eval"
