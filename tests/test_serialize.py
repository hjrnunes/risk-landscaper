# tests/test_serialize.py
from risk_landscaper.models import RiskLandscape, RiskCard, RiskSource, RiskConsequence, RiskImpact, RiskControl, RiskIncidentRef, EvaluationRef, GovernanceProvenance, PolicySourceRef, KnowledgeBaseRef, CoverageGap
from risk_landscaper.serialize import landscape_to_jsonld, SOURCE_TYPE_TO_VAIR, PROVENANCE_AGENTS, PROVENANCE_ACTIVITIES, _vair_iri


def test_empty_landscape_has_context_and_type():
    landscape = RiskLandscape(run_slug="test-run", timestamp="2026-04-22T10:00:00Z")
    result = landscape_to_jsonld(landscape)
    assert "@context" in result
    ctx = result["@context"]
    assert ctx["airo"] == "https://w3id.org/airo#"
    assert ctx["vair"] == "https://w3id.org/vair#"
    assert ctx["nexus"] == "https://ibm.github.io/ai-atlas-nexus/ontology/"
    assert ctx["dpv"] == "https://w3id.org/dpv#"
    assert ctx["prov"] == "http://www.w3.org/ns/prov#"
    assert ctx["rl"] == "https://trustyai.io/risk-landscaper/"
    assert result["@type"] == ["rl:RiskLandscape", "prov:Entity"]
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
    incidents = card["rl:hasIncident"]
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


def test_all_source_type_parents_mapped():
    expected = {
        "attack": "vair:Attack",
        "data": "vair:DataRiskSource",
        "organisational": "vair:OrganisationalRiskSource",
        "performance": "vair:PerformanceRiskSource",
        "system": "vair:SystemRiskSource",
    }
    assert SOURCE_TYPE_TO_VAIR == expected


def test_vair_iri_specific_types():
    assert _vair_iri("AdversarialAttack") == "vair:AdversarialAttack"
    assert _vair_iri("BiasedTrainingData") == "vair:BiasedTrainingData"
    assert _vair_iri("Bias") == "vair:Bias"
    assert _vair_iri("Death") == "vair:Death"
    assert _vair_iri("Freedom") == "vair:Freedom"


def test_vair_iri_unknown_returns_none():
    assert _vair_iri("SomethingInvented") is None
    assert _vair_iri("") is None


def test_impact_unknown_harm_type_no_vair_iri():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                impacts=[
                    RiskImpact(description="Custom harm", harm_type="CustomHarmType"),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    imp = result["rl:hasRiskCard"][0]["airo:hasImpact"][0]
    assert imp["@type"] == "airo:Impact"


def test_envelope_metadata():
    landscape = RiskLandscape(
        run_slug="test-run",
        timestamp="2026-04-22T10:00:00Z",
        model="granite-3.2-8b",
        selected_domains=["banking"],
        framework_coverage={"owasp-llm": 5, "nist-ai-rmf": 3},
        policy_source=PolicySourceRef(organization="Acme Corp", domain="banking", policy_count=10),
        knowledge_base=KnowledgeBaseRef(nexus_risk_count=600),
    )
    result = landscape_to_jsonld(landscape)
    assert result["rl:timestamp"] == "2026-04-22T10:00:00Z"
    assert result["rl:model"] == "granite-3.2-8b"
    assert result["rl:selectedDomains"] == ["banking"]
    assert result["rl:frameworkCoverage"] == {"owasp-llm": 5, "nist-ai-rmf": 3}


def test_provenance_serializes():
    landscape = RiskLandscape(
        run_slug="test-run",
        timestamp="2026-04-22T10:00:00Z",
        provenance=GovernanceProvenance(
            produced_by="risk-landscaper",
            governance_function="evaluate",
            aims_activities=["aimsA6", "aimsA8"],
            review_status="draft",
        ),
    )
    result = landscape_to_jsonld(landscape)
    prov = result["prov:wasGeneratedBy"]
    assert prov["@type"] == "prov:Activity"
    assert prov["prov:wasAssociatedWith"] == {"@id": "rl:risk-landscaper"}
    assert prov["prov:endedAtTime"] == "2026-04-22T10:00:00Z"
    assert prov["rl:governanceFunction"] == "evaluate"
    assert prov["rl:aimsActivity"] == ["aimsA6", "aimsA8"]
    assert prov["rl:reviewStatus"] == "draft"


def test_turtle_output():
    import pytest
    rdflib = pytest.importorskip("rdflib")
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test Risk",
                consequences=[
                    RiskConsequence(description="Bad outcome", severity="high"),
                ],
            ),
        ],
    )
    from risk_landscaper.serialize import landscape_to_turtle
    ttl = landscape_to_turtle(landscape)
    assert isinstance(ttl, str)
    assert len(ttl) > 0
    g = rdflib.Graph()
    g.parse(data=ttl, format="turtle")
    assert len(g) > 0
    airo_ns = rdflib.Namespace("https://w3id.org/airo#")
    risk_type_triples = list(g.triples((None, rdflib.RDF.type, airo_ns.Risk)))
    assert len(risk_type_triples) == 1


def test_turtle_without_rdflib_raises():
    import pytest
    from unittest.mock import patch
    import builtins

    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "rdflib":
            raise ImportError("No module named 'rdflib'")
        return original_import(name, *args, **kwargs)

    landscape = RiskLandscape(run_slug="test-run")
    from risk_landscaper.serialize import landscape_to_turtle

    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="rdflib"):
            landscape_to_turtle(landscape)


def test_context_has_reverse_annotations():
    landscape = RiskLandscape(run_slug="test-run")
    result = landscape_to_jsonld(landscape)
    ctx = result["@context"]
    assert ctx["airo:isRiskSourceFor"] == {"@reverse": "airo:isRiskSourceFor"}
    assert ctx["airo:modifiesRiskConcept"] == {"@reverse": "airo:modifiesRiskConcept"}


def test_coverage_gaps_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        coverage_gaps=[
            CoverageGap(
                policy_concept="AI-assisted triage",
                concept_definition="Using AI to prioritize patient care",
                gap_type="novel",
                confidence=0.85,
                nearest_risks=[{"risk_id": "bias-discrimination-output", "distance": 0.3}],
                reasoning="No existing risk covers AI triage specifically",
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    gaps = result["rl:coverageGap"]
    assert len(gaps) == 1
    gap = gaps[0]
    assert gap["rl:policyConcept"] == "AI-assisted triage"
    assert gap["rl:gapType"] == "novel"
    assert gap["rl:confidence"] == 0.85
    assert gap["rl:nearestRisks"] == [{"risk_id": "bias-discrimination-output", "distance": 0.3}]


def test_incidents_use_rl_hasIncident_key():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                incidents=[RiskIncidentRef(name="Test Incident")],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    assert "rl:hasIncident" in card
    assert "dpv:Incident" not in card


# --- PROV-O attribution tests ---


def test_risk_source_provenance_nexus():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                risk_sources=[RiskSource(description="Known attack vector", provenance="nexus")],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    src = result["rl:hasRiskCard"][0]["airo:isRiskSourceFor"][0]
    assert src["prov:wasAttributedTo"] == {"@id": "rl:NexusKnowledgeGraph"}
    assert src["prov:wasGeneratedBy"] == {"@id": "rl:BuildLandscape"}


def test_consequence_provenance_vair():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                consequences=[RiskConsequence(description="Model degradation", provenance="vair")],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    cons = result["rl:hasRiskCard"][0]["airo:hasConsequence"][0]
    assert cons["prov:wasAttributedTo"] == {"@id": "rl:VAIRMatcher"}
    assert cons["prov:wasGeneratedBy"] == {"@id": "rl:BuildLandscape"}


def test_impact_provenance_llm():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                impacts=[RiskImpact(description="User harm", provenance="llm")],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    imp = result["rl:hasRiskCard"][0]["airo:hasImpact"][0]
    assert imp["prov:wasAttributedTo"] == {"@id": "rl:LLMAgent"}
    assert imp["prov:wasGeneratedBy"] == {"@id": "rl:EnrichChains"}


def test_control_provenance_nexus():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                controls=[RiskControl(description="Monitor outputs", control_type="detect", provenance="nexus")],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    ctrl = result["rl:hasRiskCard"][0]["airo:modifiesRiskConcept"][0]
    assert ctrl["prov:wasAttributedTo"] == {"@id": "rl:NexusKnowledgeGraph"}
    assert ctrl["prov:wasGeneratedBy"] == {"@id": "rl:BuildLandscape"}


def test_incident_provenance_nexus():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                incidents=[RiskIncidentRef(name="Test Incident", provenance="nexus")],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    inc = result["rl:hasRiskCard"][0]["rl:hasIncident"][0]
    assert inc["prov:wasAttributedTo"] == {"@id": "rl:NexusKnowledgeGraph"}
    assert inc["prov:wasGeneratedBy"] == {"@id": "rl:BuildLandscape"}


def test_no_provenance_omits_prov_triples():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                risk_sources=[RiskSource(description="No provenance set")],
                consequences=[RiskConsequence(description="No provenance set")],
                impacts=[RiskImpact(description="No provenance set")],
                controls=[RiskControl(description="No provenance set")],
                incidents=[RiskIncidentRef(name="No provenance set")],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    assert "prov:wasAttributedTo" not in card["airo:isRiskSourceFor"][0]
    assert "prov:wasAttributedTo" not in card["airo:hasConsequence"][0]
    assert "prov:wasAttributedTo" not in card["airo:hasImpact"][0]
    assert "prov:wasAttributedTo" not in card["airo:modifiesRiskConcept"][0]
    assert "prov:wasAttributedTo" not in card["rl:hasIncident"][0]


def test_heuristic_provenance():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                risk_sources=[RiskSource(description="Inferred source", provenance="heuristic")],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    src = result["rl:hasRiskCard"][0]["airo:isRiskSourceFor"][0]
    assert src["prov:wasAttributedTo"] == {"@id": "rl:HeuristicEngine"}
    assert src["prov:wasGeneratedBy"] == {"@id": "rl:BuildLandscape"}


def test_provenance_agents_cover_all_tags():
    expected_tags = {"nexus", "vair", "heuristic", "llm"}
    assert set(PROVENANCE_AGENTS.keys()) == expected_tags
    assert set(PROVENANCE_ACTIVITIES.keys()) == expected_tags


def test_landscape_without_provenance_omits_wasGeneratedBy():
    landscape = RiskLandscape(run_slug="test-run")
    result = landscape_to_jsonld(landscape)
    assert "prov:wasGeneratedBy" not in result
