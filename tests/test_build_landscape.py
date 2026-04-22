import pytest
from risk_landscaper.models import (
    RiskLandscape, RiskCard, PolicyRiskMapping, RiskMatch,
    PolicySourceRef, PolicyProfile, Organization, RiskSource,
    RiskIncidentRef,
)
from risk_landscaper.stages.build_landscape import _infer_control_type, _infer_control_targets, _infer_source_type, _incidents_to_refs


def test_build_risk_landscape_basic():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Executive Compensation",
            matched_risks=[
                RiskMatch(
                    risk_id="atlas-personal-info",
                    risk_name="Personal information",
                    relevance="primary",
                    justification="Direct PII concern",
                    match_distance=0.234,
                ),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-personal-info": {
            "id": "atlas-personal-info",
            "name": "Personal information",
            "description": "Personal information or sensitive...",
            "concern": "If personal information is included...",
        },
    }
    related_risks = {
        "atlas-personal-info": [
            {"id": "nist-data-privacy", "name": "Data Privacy",
             "taxonomy": "nist-ai-rmf", "mapping_type": "broad"},
        ],
    }
    risk_actions = {
        "atlas-personal-info": ["Minimize personal data in prompts"],
    }
    selected_domains = ["CCO", "Commons", "FIBO", "D3FEND", "CSO", "LKIF"]

    landscape = build_risk_landscape(
        mappings=mappings,
        risk_details_cache=risk_details_cache,
        related_risks=related_risks,
        risk_actions=risk_actions,
        selected_domains=selected_domains,
        model="gemma-3-12b-it",
        run_slug="swb-enriched",
        timestamp="2026-04-14T12:00:00Z",
    )

    assert isinstance(landscape, RiskLandscape)
    assert landscape.model == "gemma-3-12b-it"
    assert landscape.selected_domains == selected_domains
    assert len(landscape.risks) == 1
    assert landscape.risks[0].risk_id == "atlas-personal-info"
    assert landscape.risks[0].risk_framework == "IBM Risk Atlas"
    assert landscape.risks[0].related_actions == ["Minimize personal data in prompts"]
    assert landscape.risks[0].cross_mappings == related_risks["atlas-personal-info"]
    assert len(landscape.policy_mappings) == 1
    assert landscape.policy_mappings[0].policy_concept == "Executive Compensation"


def test_build_risk_landscape_deduplicates_risks():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    # Same risk matched from two policies
    mappings = [
        PolicyRiskMapping(
            policy_concept="Policy A",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="Risk One",
                          relevance="primary", justification="test"),
            ],
        ),
        PolicyRiskMapping(
            policy_concept="Policy B",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="Risk One",
                          relevance="supporting", justification="test2"),
            ],
        ),
    ]
    risk_details_cache = {
        "r1": {"id": "r1", "name": "Risk One", "description": "desc"},
    }

    landscape = build_risk_landscape(
        mappings=mappings,
        risk_details_cache=risk_details_cache,
        model="test-model",
        run_slug="test",
        timestamp="2026-04-14T12:00:00Z",
    )

    # Risk stored once, referenced from both policy mappings
    assert len(landscape.risks) == 1
    assert len(landscape.policy_mappings) == 2


def test_build_risk_landscape_weak_matches():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Policy A",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="Risk One",
                          relevance="primary", justification="test",
                          match_distance=0.75),
            ],
        ),
    ]
    risk_details_cache = {
        "r1": {"id": "r1", "name": "Risk One", "description": "desc"},
    }

    landscape = build_risk_landscape(
        mappings=mappings,
        risk_details_cache=risk_details_cache,
        model="test-model",
        run_slug="test",
        timestamp="2026-04-14T12:00:00Z",
    )

    assert len(landscape.weak_matches) == 1
    assert landscape.weak_matches[0].risk_id == "r1"
    assert landscape.weak_matches[0].distance == 0.75


def test_build_risk_landscape_framework_coverage():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Policy A",
            matched_risks=[
                RiskMatch(risk_id="atlas-fraud", risk_name="Fraud",
                          relevance="primary", justification="test"),
                RiskMatch(risk_id="nist-data-privacy", risk_name="Data Privacy",
                          relevance="supporting", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-fraud": {"id": "atlas-fraud", "name": "Fraud", "description": ""},
        "nist-data-privacy": {"id": "nist-data-privacy", "name": "Data Privacy", "description": ""},
    }

    landscape = build_risk_landscape(
        mappings=mappings,
        risk_details_cache=risk_details_cache,
        model="test-model",
        run_slug="test",
        timestamp="2026-04-14T12:00:00Z",
    )

    assert "IBM Risk Atlas" in landscape.framework_coverage
    assert "NIST AI RMF" in landscape.framework_coverage


def test_build_risk_landscape_with_policy_source():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    policy_profile = PolicyProfile(
        organization=Organization(name="South West Bank"),
        domain="banking",
        policies=[],
    )
    landscape = build_risk_landscape(
        mappings=[],
        risk_details_cache={},
        model="test-model",
        run_slug="test",
        timestamp="2026-04-14T12:00:00Z",
        policy_profile=policy_profile,
    )

    assert landscape.policy_source is not None
    assert landscape.policy_source.organization == "South West Bank"
    assert landscape.policy_source.domain == "banking"


def test_build_risk_landscape_empty_inputs():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    landscape = build_risk_landscape(
        mappings=[],
        risk_details_cache={},
        model="test-model",
        run_slug="test",
        timestamp="2026-04-14T12:00:00Z",
    )

    assert landscape.risks == []
    assert landscape.policy_mappings == []
    assert landscape.framework_coverage == {}


def test_build_risk_landscape_with_coverage_gaps():
    from risk_landscaper.stages.build_landscape import build_risk_landscape
    from risk_landscaper.models import CoverageGap

    gaps = [
        CoverageGap(
            policy_concept="Multi-agent collusion",
            concept_definition="AI agents coordinating to bypass controls",
            gap_type="novel",
            confidence=0.82,
            nearest_risks=[{"id": "atlas-dangerous-use", "name": "Dangerous use", "distance": 0.75}],
            reasoning="No existing risk covers multi-agent coordination failures",
        ),
    ]

    landscape = build_risk_landscape(
        mappings=[],
        risk_details_cache={},
        coverage_gaps=gaps,
        model="test-model",
        run_slug="test",
        timestamp="2026-04-16T12:00:00Z",
    )

    assert len(landscape.coverage_gaps) == 1
    assert landscape.coverage_gaps[0].gap_type == "novel"
    assert landscape.coverage_gaps[0].policy_concept == "Multi-agent collusion"


def test_build_risk_landscape_empty_coverage_gaps():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    landscape = build_risk_landscape(
        mappings=[],
        risk_details_cache={},
        model="test-model",
        run_slug="test",
        timestamp="2026-04-16T12:00:00Z",
    )

    assert landscape.coverage_gaps == []


def test_build_risk_landscape_populates_risk_type_and_descriptors():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Bias Policy",
            matched_risks=[
                RiskMatch(risk_id="atlas-bias", risk_name="Bias",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-bias": {
            "id": "atlas-bias", "name": "Bias",
            "description": "Model bias", "concern": "Discriminatory outputs",
            "risk_type": "output",
            "descriptor": ["amplified by generative AI"],
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    assert landscape.risks[0].risk_type == "output"
    assert landscape.risks[0].descriptors == ["amplified by generative AI"]


def test_build_risk_landscape_actions_become_controls():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Data Policy",
            matched_risks=[
                RiskMatch(risk_id="atlas-pii", risk_name="PII",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-pii": {"id": "atlas-pii", "name": "PII", "description": ""},
    }
    risk_actions = {
        "atlas-pii": ["Minimize personal data", "Apply output filtering"],
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        risk_actions=risk_actions, model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert len(card.controls) == 2
    assert card.controls[0].description == "Minimize personal data"
    assert card.controls[1].description == "Apply output filtering"
    assert card.related_actions == ["Minimize personal data", "Apply output filtering"]


def test_build_risk_landscape_related_policies():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Fraud Prevention",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="Risk", relevance="primary", justification="x"),
            ],
        ),
        PolicyRiskMapping(
            policy_concept="AML",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="Risk", relevance="supporting", justification="y"),
            ],
        ),
    ]
    risk_details_cache = {"r1": {"id": "r1", "name": "Risk", "description": ""}}
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    assert sorted(landscape.risks[0].related_policies) == ["AML", "Fraud Prevention"]


def test_build_risk_landscape_provenance():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    landscape = build_risk_landscape(
        mappings=[], risk_details_cache={},
        model="test", run_slug="test", timestamp="t",
    )
    assert landscape.provenance is not None
    assert landscape.provenance.produced_by == "risk-landscaper"
    assert landscape.provenance.governance_function == "evaluate"
    assert "aimsA6" in landscape.provenance.aims_activities
    assert landscape.provenance.review_status == "draft"


def test_build_risk_landscape_descriptor_string_coercion():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="P",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="R", relevance="primary", justification="x"),
            ],
        ),
    ]
    risk_details_cache = {
        "r1": {"id": "r1", "name": "R", "description": "", "descriptor": "single string"},
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    assert landscape.risks[0].descriptors == ["single string"]


def test_infer_control_type_detect():
    assert _infer_control_type("Monitor output for harmful content") == "detect"
    assert _infer_control_type("Audit model decisions regularly") == "detect"


def test_infer_control_type_evaluate():
    assert _infer_control_type("Evaluate model fairness with benchmarks") == "evaluate"
    assert _infer_control_type("Assess bias across demographic groups") == "evaluate"


def test_infer_control_type_mitigate():
    assert _infer_control_type("Filter offensive content from responses") == "mitigate"
    assert _infer_control_type("Reduce exposure to sensitive data") == "mitigate"


def test_infer_control_type_eliminate():
    assert _infer_control_type("Prevent unauthorized access to the model") == "eliminate"
    assert _infer_control_type("Block generation of harmful instructions") == "eliminate"


def test_infer_control_type_none():
    assert _infer_control_type("Apply best practices for AI safety") is None
    assert _infer_control_type("") is None


def test_infer_control_targets_source():
    assert _infer_control_targets("Validate training data quality") == "source"
    assert _infer_control_targets("Sanitize input prompts") == "source"


def test_infer_control_targets_consequence():
    assert _infer_control_targets("Filter output for bias") == "consequence"
    assert _infer_control_targets("Review results before publishing") == "consequence"


def test_infer_control_targets_default_risk():
    assert _infer_control_targets("Apply guardrails to the model") == "risk"
    assert _infer_control_targets("") == "risk"


def test_infer_source_type_data():
    assert _infer_source_type("training-data") == "data"
    assert _infer_source_type("input") == "data"


def test_infer_source_type_model():
    assert _infer_source_type("output") == "model"
    assert _infer_source_type("inference") == "model"
    assert _infer_source_type("agentic") == "model"


def test_infer_source_type_organisational():
    assert _infer_source_type("non-technical") == "organisational"


def test_infer_source_type_none():
    assert _infer_source_type(None) is None
    assert _infer_source_type("unknown-type") is None


def test_build_landscape_populates_baseline_risk_source():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Bias Policy",
            matched_risks=[
                RiskMatch(risk_id="atlas-bias", risk_name="Bias",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-bias": {
            "id": "atlas-bias", "name": "Bias",
            "description": "Model exhibits systematic bias",
            "concern": "Discriminatory outputs affecting users",
            "risk_type": "output",
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert len(card.risk_sources) == 1
    assert card.risk_sources[0].source_type == "model"
    assert card.risk_sources[0].description == "Discriminatory outputs affecting users"


def test_incidents_to_refs_basic():
    raw = [
        {
            "name": "AI-based Biological Attacks",
            "description": "LLMs could help plan biological attacks",
            "source_uri": "https://example.com/incident",
            "hasStatus": "Concluded",
        },
    ]
    refs = _incidents_to_refs(raw)
    assert len(refs) == 1
    assert refs[0].name == "AI-based Biological Attacks"
    assert refs[0].description == "LLMs could help plan biological attacks"
    assert refs[0].source_uri == "https://example.com/incident"
    assert refs[0].status == "concluded"


def test_incidents_to_refs_missing_fields():
    raw = [{"name": "Minimal Incident"}]
    refs = _incidents_to_refs(raw)
    assert len(refs) == 1
    assert refs[0].name == "Minimal Incident"
    assert refs[0].description is None
    assert refs[0].source_uri is None
    assert refs[0].status is None


def test_incidents_to_refs_empty():
    assert _incidents_to_refs([]) == []
    assert _incidents_to_refs(None) == []


def test_build_landscape_with_incidents():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Safety",
            matched_risks=[
                RiskMatch(risk_id="atlas-dangerous-use", risk_name="Dangerous use",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-dangerous-use": {
            "id": "atlas-dangerous-use", "name": "Dangerous use",
            "description": "AI used for dangerous purposes",
        },
    }
    risk_incidents = {
        "atlas-dangerous-use": [
            {
                "name": "Bioweapon planning",
                "description": "LLM assisted in planning biological attack",
                "source_uri": "https://example.com",
                "hasStatus": "Ongoing",
            },
        ],
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        risk_incidents=risk_incidents,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert len(card.incidents) == 1
    assert card.incidents[0].name == "Bioweapon planning"
    assert card.incidents[0].status == "ongoing"


def test_build_landscape_vair_enrichment():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Fairness",
            matched_risks=[
                RiskMatch(risk_id="atlas-bias", risk_name="Bias",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-bias": {
            "id": "atlas-bias", "name": "Bias",
            "description": "Model exhibits systematic bias against protected groups",
            "concern": "Discriminatory outputs and unfair treatment of users",
            "risk_type": "output",
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert len(card.consequences) > 0
    consequence_descs = [c.description for c in card.consequences]
    assert "Bias" in consequence_descs
    assert len(card.impacts) > 0
    impact_descs = [i.description for i in card.impacts]
    assert "Discriminatory Treatment" in impact_descs


def test_build_landscape_vair_no_matches():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="General Policy",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="R",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "r1": {
            "id": "r1", "name": "R",
            "description": "Generic risk entry",
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert card.consequences == []
    assert card.impacts == []


def test_build_landscape_populates_trustworthy_characteristics():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Fairness Policy",
            matched_risks=[
                RiskMatch(risk_id="atlas-bias", risk_name="Bias",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-bias": {
            "id": "atlas-bias", "name": "Bias",
            "description": "Model exhibits systematic bias against protected groups",
            "concern": "Discriminatory outputs and unfair treatment of users",
            "risk_type": "output",
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert "fairness" in card.trustworthy_characteristics


def test_build_landscape_trustworthy_empty_for_generic_risk():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="General",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="R",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "r1": {"id": "r1", "name": "R", "description": "Generic risk entry"},
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert card.trustworthy_characteristics == []


def test_build_landscape_trustworthy_multiple():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Security",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="R",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "r1": {
            "id": "r1", "name": "R",
            "description": "Cyberattack with lack of transparency and biased outcomes",
            "concern": "System vulnerability exploited leading to privacy breach",
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert "cybersecurity" in card.trustworthy_characteristics
    assert "transparency" in card.trustworthy_characteristics
    assert "fairness" in card.trustworthy_characteristics
    assert "privacy" in card.trustworthy_characteristics
