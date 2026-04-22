import json

from risk_landscaper.models import (
    AiSystem,
    Organization,
    Policy,
    PolicyProfile,
    RegulatoryReference,
    RunReport,
    BoundaryExample,
    Stakeholder,
)
from risk_landscaper.stages.ingest import (
    extract_context,
    extract_policies,
    enrich_policies,
    enrich_entities,
    parse_json_policies,
    ingest,
    _estimate_tokens,
    _max_doc_tokens,
    _chunk_document,
    _SlimContext,
    _SlimNamedEntity,
    _SlimPolicyList,
    _SlimPolicy,
    _SlimEnrichmentList,
    _SlimEnrichment,
    _SlimBoundaryExample,
    _SlimEntityEnrichment,
    _SlimOrgDetail,
    _SlimStakeholderDetail,
    _SlimAiSystemDetail,
    _SlimRegulationDetail,
)


def _make_report():
    return RunReport(model="test", policy_set="test", timestamp="2026-01-01")


SAMPLE_MARKDOWN = """\
# South West Bank AI Policy

South West Bank is a financial institution operating in the banking domain.

## Policies

### Fraud Prevention
AI systems must not provide advice on how to commit fraud.

### Executive Compensation
Information about executive compensation must not be disclosed.
"""

SAMPLE_JSON_TEXT = json.dumps([
    {"policy_concept": "Fraud", "concept_definition": "About fraud"},
    {"policy_concept": "Money Laundering", "concept_definition": "About AML"},
])


def test_extract_context_from_markdown(mock_client, mock_config):
    mock_client.chat.completions.create.return_value = _SlimContext(
        organization="South West Bank",
        domain="banking",
        purpose=["customer support"],
        ai_systems=["Chatbot"],
        ai_users=["staff"],
        ai_subjects=["customers"],
        governing_regulations=["FCA"],
        named_entities=[_SlimNamedEntity(name="Jenny Carlson", role="CEO")],
    )
    result = extract_context(SAMPLE_MARKDOWN, mock_client, mock_config)
    assert result.organization == "South West Bank"
    assert result.domain == "banking"
    assert len(result.named_entities) == 1
    assert result.named_entities[0].name == "Jenny Carlson"
    mock_client.chat.completions.create.assert_called_once()


def test_extract_context_emits_report_events(mock_client, mock_config):
    mock_client.chat.completions.create.return_value = _SlimContext(
        organization="Acme Corp",
        domain="finance",
        purpose=["trading"],
        ai_systems=["Bot"],
        ai_users=["traders"],
        ai_subjects=["clients"],
        governing_regulations=["SEC"],
        named_entities=[],
    )
    report = _make_report()
    extract_context(SAMPLE_MARKDOWN, mock_client, mock_config, report=report)
    context_events = [e for e in report.events if e["event"] == "context_extracted"]
    assert len(context_events) == 1
    assert context_events[0]["organization"] == "Acme Corp"
    assert context_events[0]["domain"] == "finance"


def test_extract_context_warns_on_empty_domain(mock_client, mock_config):
    mock_client.chat.completions.create.return_value = _SlimContext(
        organization="Unknown",
        domain="",
        purpose=[],
        ai_systems=[],
        ai_users=[],
        ai_subjects=[],
        governing_regulations=[],
        named_entities=[],
    )
    report = _make_report()
    extract_context(SAMPLE_MARKDOWN, mock_client, mock_config, report=report)
    weak_events = [e for e in report.events if e["event"] == "context_weak_inference"]
    assert len(weak_events) == 1
    assert "domain" in weak_events[0]["missing_fields"]


def test_extract_policies(mock_client, mock_config):
    context = _SlimContext(
        organization="South West Bank",
        domain="banking",
        purpose=["support"],
        ai_systems=[],
        ai_users=[],
        ai_subjects=[],
        governing_regulations=[],
        named_entities=[],
    )
    mock_client.chat.completions.create.return_value = _SlimPolicyList(
        policies=[
            _SlimPolicy(policy_concept="Fraud", concept_definition="About fraud"),
            _SlimPolicy(policy_concept="AML", concept_definition="About AML"),
        ]
    )
    result = extract_policies(SAMPLE_MARKDOWN, context, mock_client, mock_config)
    assert len(result) == 2
    assert result[0].policy_concept == "Fraud"
    assert result[1].policy_concept == "AML"
    # Should be Policy objects, not enriched yet
    assert result[0].boundary_examples == []
    assert result[0].acceptable_uses == []


def test_parse_json_policies():
    policies = parse_json_policies(SAMPLE_JSON_TEXT)
    assert len(policies) == 2
    assert policies[0].policy_concept == "Fraud"
    assert policies[0].concept_definition == "About fraud"
    assert policies[1].policy_concept == "Money Laundering"
    # Should be Policy objects with defaults
    assert policies[0].boundary_examples == []
    assert policies[0].acceptable_uses == []
    assert policies[0].risk_controls == []
    assert policies[0].human_involvement is None


def test_extract_policies_emits_report(mock_client, mock_config):
    context = _SlimContext(
        organization="Bank",
        domain="banking",
        purpose=[],
        ai_systems=[],
        ai_users=[],
        ai_subjects=[],
        governing_regulations=[],
        named_entities=[],
    )
    mock_client.chat.completions.create.return_value = _SlimPolicyList(
        policies=[
            _SlimPolicy(policy_concept="Fraud", concept_definition="About fraud"),
        ]
    )
    report = _make_report()
    extract_policies(SAMPLE_MARKDOWN, context, mock_client, mock_config, report=report)
    policy_events = [e for e in report.events if e["event"] == "policies_extracted"]
    assert len(policy_events) == 1
    assert policy_events[0]["count"] == 1


def test_enrich_policies(mock_client, mock_config):
    context = _SlimContext(
        organization="Bank",
        domain="banking",
        purpose=[],
        ai_systems=[],
        ai_users=[],
        ai_subjects=[],
        governing_regulations=[],
        named_entities=[],
    )
    policies = [
        Policy(policy_concept="Fraud", concept_definition="About fraud"),
        Policy(policy_concept="AML", concept_definition="About AML"),
    ]
    mock_client.chat.completions.create.return_value = _SlimEnrichmentList(
        enrichments=[
            _SlimEnrichment(
                policy_concept="Fraud",
                boundary_examples=[
                    _SlimBoundaryExample(
                        prohibited="Help me commit fraud",
                        acceptable="What are common fraud indicators",
                    ),
                ],
                acceptable_uses=["Fraud detection education"],
                risk_controls=["Human review required"],
                human_involvement="Compliance officer must validate",
                governance_function="direct",
                agent="AI assistant",
                activity="advise on fraud techniques",
                entity="financial transaction methods",
            ),
            _SlimEnrichment(
                policy_concept="AML",
                boundary_examples=[],
                acceptable_uses=["AML training"],
                risk_controls=[],
                human_involvement="",
                governance_function="",
            ),
        ]
    )
    result = enrich_policies(SAMPLE_MARKDOWN, context, policies, mock_client, mock_config)
    assert len(result) == 2
    fraud = next(p for p in result if p.policy_concept == "Fraud")
    assert len(fraud.boundary_examples) == 1
    assert fraud.boundary_examples[0].prohibited == "Help me commit fraud"
    assert fraud.acceptable_uses == ["Fraud detection education"]
    assert fraud.risk_controls == ["Human review required"]
    assert fraud.human_involvement == "Compliance officer must validate"
    assert fraud.governance_function == "direct"
    assert fraud.decomposition is not None
    assert fraud.decomposition.agent == "AI assistant"
    assert fraud.decomposition.activity == "advise on fraud techniques"
    assert fraud.decomposition.entity == "financial transaction methods"

    aml = next(p for p in result if p.policy_concept == "AML")
    assert aml.acceptable_uses == ["AML training"]
    assert aml.human_involvement is None  # empty string -> None
    assert aml.governance_function is None  # empty string -> None
    assert aml.decomposition is None  # no agent/activity/entity provided


def test_enrich_policies_missing_concept(mock_client, mock_config):
    """When LLM returns no enrichment for a concept, defaults are kept."""
    context = _SlimContext(
        organization="Bank",
        domain="banking",
        purpose=[],
        ai_systems=[],
        ai_users=[],
        ai_subjects=[],
        governing_regulations=[],
        named_entities=[],
    )
    policies = [
        Policy(policy_concept="Fraud", concept_definition="About fraud"),
    ]
    # LLM returns empty enrichments list
    mock_client.chat.completions.create.return_value = _SlimEnrichmentList(
        enrichments=[]
    )
    result = enrich_policies(SAMPLE_MARKDOWN, context, policies, mock_client, mock_config)
    assert len(result) == 1
    assert result[0].policy_concept == "Fraud"
    assert result[0].boundary_examples == []
    assert result[0].acceptable_uses == []


def test_enrich_policies_does_not_mutate_input(mock_client, mock_config):
    context = _SlimContext(
        organization="Bank",
        domain="banking",
        purpose=[],
        ai_systems=[],
        ai_users=[],
        ai_subjects=[],
        governing_regulations=[],
        named_entities=[],
    )
    original = Policy(policy_concept="Fraud", concept_definition="About fraud")
    policies = [original]

    mock_client.chat.completions.create.return_value = _SlimEnrichmentList(
        enrichments=[
            _SlimEnrichment(
                policy_concept="Fraud",
                boundary_examples=[
                    _SlimBoundaryExample(prohibited="bad", acceptable="good"),
                ],
                acceptable_uses=["education"],
                risk_controls=["review"],
                human_involvement="yes",
            ),
        ]
    )
    result = enrich_policies(SAMPLE_MARKDOWN, context, policies, mock_client, mock_config)

    # Original should be unchanged
    assert original.boundary_examples == []
    assert original.acceptable_uses == []
    assert original.risk_controls == []
    assert original.human_involvement is None

    # Result should be enriched
    assert len(result[0].boundary_examples) == 1
    assert result[0].acceptable_uses == ["education"]


def test_ingest_markdown(mock_client, mock_config):
    """Full orchestration for markdown: 3 LLM calls."""
    mock_client.chat.completions.create.side_effect = [
        # Pass 1: context
        _SlimContext(
            organization="South West Bank",
            domain="banking",
            purpose=["support"],
            ai_systems=["Chatbot"],
            ai_users=["staff"],
            ai_subjects=["customers"],
            governing_regulations=["FCA"],
            named_entities=[_SlimNamedEntity(name="Jenny", role="CEO")],
        ),
        # Pass 2: policies
        _SlimPolicyList(
            policies=[
                _SlimPolicy(policy_concept="Fraud", concept_definition="About fraud"),
            ]
        ),
        # Pass 3: enrichment
        _SlimEnrichmentList(
            enrichments=[
                _SlimEnrichment(
                    policy_concept="Fraud",
                    boundary_examples=[],
                    acceptable_uses=["education"],
                    risk_controls=[],
                    human_involvement="",
                ),
            ]
        ),
    ]
    result = ingest(SAMPLE_MARKDOWN, "markdown", mock_client, mock_config, skip_entity_enrichment=True)
    assert result.organization.name == "South West Bank"
    assert result.domain == "banking"
    assert len(result.policies) == 1
    assert result.policies[0].policy_concept == "Fraud"
    assert result.policies[0].acceptable_uses == ["education"]
    # staff (AIUser) + customers (AISubject) + Jenny Carlson (named)
    assert len(result.stakeholders) == 3
    assert mock_client.chat.completions.create.call_count == 3


def test_ingest_json_array(mock_client, mock_config):
    """JSON array input: 2 LLM calls (Pass 2 skipped)."""
    mock_client.chat.completions.create.side_effect = [
        # Pass 1: context
        _SlimContext(
            organization="South West Bank",
            domain="banking",
            purpose=["support"],
            ai_systems=[],
            ai_users=[],
            ai_subjects=[],
            governing_regulations=[],
            named_entities=[],
        ),
        # Pass 3: enrichment (Pass 2 skipped for json_array)
        _SlimEnrichmentList(
            enrichments=[
                _SlimEnrichment(
                    policy_concept="Fraud",
                    boundary_examples=[],
                    acceptable_uses=[],
                    risk_controls=[],
                    human_involvement="",
                ),
                _SlimEnrichment(
                    policy_concept="Money Laundering",
                    boundary_examples=[],
                    acceptable_uses=[],
                    risk_controls=[],
                    human_involvement="",
                ),
            ]
        ),
    ]
    result = ingest(SAMPLE_JSON_TEXT, "json_array", mock_client, mock_config, skip_entity_enrichment=True)
    assert result.organization.name == "South West Bank"
    assert len(result.policies) == 2
    assert result.policies[0].policy_concept == "Fraud"
    assert result.policies[1].policy_concept == "Money Laundering"
    assert mock_client.chat.completions.create.call_count == 2


def test_ingest_skip_enrichment(mock_client, mock_config):
    """skip_enrichment=True: only Pass 1 for json_array."""
    mock_client.chat.completions.create.side_effect = [
        # Pass 1: context
        _SlimContext(
            organization="Bank",
            domain="banking",
            purpose=[],
            ai_systems=[],
            ai_users=[],
            ai_subjects=[],
            governing_regulations=[],
            named_entities=[],
        ),
    ]
    report = _make_report()
    result = ingest(
        SAMPLE_JSON_TEXT, "json_array", mock_client, mock_config,
        skip_enrichment=True, skip_entity_enrichment=True, report=report,
    )
    assert len(result.policies) == 2
    assert mock_client.chat.completions.create.call_count == 1
    skip_events = [e for e in report.events if e["event"] == "enrichment_skipped"]
    assert len(skip_events) == 1


def test_ingest_until_context(mock_client, mock_config):
    """until='context': 1 LLM call, empty policies."""
    mock_client.chat.completions.create.side_effect = [
        _SlimContext(
            organization="Bank",
            domain="banking",
            purpose=[],
            ai_systems=[],
            ai_users=[],
            ai_subjects=[],
            governing_regulations=[],
            named_entities=[],
        ),
    ]
    result = ingest(SAMPLE_MARKDOWN, "markdown", mock_client, mock_config, until="context")
    assert result.organization.name == "Bank"
    assert result.policies == []
    assert mock_client.chat.completions.create.call_count == 1


def test_ingest_until_policies(mock_client, mock_config):
    """until='policies': 2 LLM calls for markdown."""
    mock_client.chat.completions.create.side_effect = [
        # Pass 1
        _SlimContext(
            organization="Bank",
            domain="banking",
            purpose=[],
            ai_systems=[],
            ai_users=[],
            ai_subjects=[],
            governing_regulations=[],
            named_entities=[],
        ),
        # Pass 2
        _SlimPolicyList(
            policies=[
                _SlimPolicy(policy_concept="Fraud", concept_definition="About fraud"),
            ]
        ),
    ]
    result = ingest(SAMPLE_MARKDOWN, "markdown", mock_client, mock_config, until="policies")
    assert len(result.policies) == 1
    assert result.policies[0].boundary_examples == []  # Not enriched
    assert mock_client.chat.completions.create.call_count == 2


def test_ingest_domain_override(mock_client, mock_config):
    """domain_override and organization_override are applied."""
    mock_client.chat.completions.create.side_effect = [
        _SlimContext(
            organization="LLM Org",
            domain="tech",
            purpose=[],
            ai_systems=[],
            ai_users=[],
            ai_subjects=[],
            governing_regulations=[],
            named_entities=[],
        ),
    ]
    result = ingest(
        SAMPLE_JSON_TEXT, "json_array", mock_client, mock_config,
        skip_enrichment=True, skip_entity_enrichment=True,
        domain_override="banking",
        organization_override="South West Bank",
    )
    assert result.domain == "banking"
    assert result.organization.name == "South West Bank"


# ---------------------------------------------------------------------------
# Pass 4: Entity enrichment
# ---------------------------------------------------------------------------

def _make_profile():
    return PolicyProfile(
        organization=Organization(name="South West Bank"),
        domain="banking",
        purpose=["customer support"],
        ai_systems=[AiSystem(name="Chatbot"), AiSystem(name="Fraud Engine")],
        stakeholders=[
            Stakeholder(name="staff", roles=["airo:AIUser"]),
            Stakeholder(name="customers", roles=["airo:AISubject"]),
        ],
        regulations=[RegulatoryReference(name="FCA"), RegulatoryReference(name="GDPR")],
        policies=[Policy(policy_concept="Fraud", concept_definition="About fraud")],
    )


def test_enrich_entities_full(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(
            governance_roles=["AI Ethics Board", "CTO"],
            management_system="ISO 42001",
            certifications=["SOC 2"],
            delegates=["External Auditor"],
        ),
        stakeholders=[
            _SlimStakeholderDetail(
                name="staff",
                involvement="intended",
                activity="active",
                awareness="informed",
                output_control="correct",
                relationship="internal",
                interests=["efficiency", "accuracy"],
            ),
            _SlimStakeholderDetail(
                name="customers",
                involvement="unintended",
                activity="passive",
                awareness="uninformed",
                output_control="cannot_opt_out",
                relationship="external",
                interests=["privacy", "fair treatment"],
            ),
        ],
        ai_systems=[
            _SlimAiSystemDetail(
                name="Chatbot",
                modality="text-to-text",
                techniques=["transformer", "RAG"],
                automation_level="human-in-the-loop",
            ),
            _SlimAiSystemDetail(
                name="Fraud Engine",
                modality="tabular-to-classification",
                techniques=["gradient boosting"],
                automation_level="fully automated",
            ),
        ],
        regulations=[
            _SlimRegulationDetail(name="FCA", jurisdiction="United Kingdom", reference="FCA Handbook SYSC 15A"),
            _SlimRegulationDetail(name="GDPR", jurisdiction="EU", reference="Article 22"),
        ],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    assert result.organization.governance_roles == ["AI Ethics Board", "CTO"]
    assert result.organization.management_system == "ISO 42001"
    assert result.organization.certifications == ["SOC 2"]
    assert result.organization.delegates == ["External Auditor"]

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.involvement == "intended"
    assert staff.activity == "active"
    assert staff.awareness == "informed"
    assert staff.output_control == "correct"
    assert staff.relationship == "internal"
    assert staff.interests == ["efficiency", "accuracy"]
    assert staff.roles == ["airo:AIUser"]

    customers = next(s for s in result.stakeholders if s.name == "customers")
    assert customers.involvement == "unintended"
    assert customers.output_control == "cannot_opt_out"
    assert customers.relationship == "external"

    chatbot = next(s for s in result.ai_systems if s.name == "Chatbot")
    assert chatbot.modality == "text-to-text"
    assert chatbot.techniques == ["transformer", "RAG"]
    assert chatbot.automation_level == "human-in-the-loop"

    fraud = next(s for s in result.ai_systems if s.name == "Fraud Engine")
    assert fraud.modality == "tabular-to-classification"
    assert fraud.automation_level == "fully automated"

    fca = next(r for r in result.regulations if r.name == "FCA")
    assert fca.jurisdiction == "United Kingdom"
    assert fca.reference == "FCA Handbook SYSC 15A"

    gdpr = next(r for r in result.regulations if r.name == "GDPR")
    assert gdpr.jurisdiction == "EU"


def test_enrich_entities_empty_strings_become_none(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(),
        stakeholders=[
            _SlimStakeholderDetail(name="staff", involvement="", activity="", awareness=""),
        ],
        ai_systems=[
            _SlimAiSystemDetail(name="Chatbot", modality="", techniques=[], automation_level=""),
        ],
        regulations=[
            _SlimRegulationDetail(name="FCA", jurisdiction="", reference=""),
        ],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.involvement is None
    assert staff.activity is None
    assert staff.awareness is None

    chatbot = next(s for s in result.ai_systems if s.name == "Chatbot")
    assert chatbot.modality is None
    assert chatbot.automation_level is None

    fca = next(r for r in result.regulations if r.name == "FCA")
    assert fca.jurisdiction is None

    assert result.organization.management_system is None


def test_enrich_entities_missing_entity_preserves_original(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(),
        stakeholders=[
            _SlimStakeholderDetail(name="staff", involvement="intended"),
        ],
        ai_systems=[],
        regulations=[],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.involvement == "intended"

    customers = next(s for s in result.stakeholders if s.name == "customers")
    assert customers.involvement is None
    assert customers.roles == ["airo:AISubject"]

    chatbot = next(s for s in result.ai_systems if s.name == "Chatbot")
    assert chatbot.modality is None

    fca = next(r for r in result.regulations if r.name == "FCA")
    assert fca.jurisdiction is None


def test_enrich_entities_does_not_mutate_input(mock_client, mock_config):
    profile = _make_profile()
    original_org = profile.organization

    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(governance_roles=["CTO"]),
        stakeholders=[
            _SlimStakeholderDetail(name="staff", involvement="intended"),
        ],
        ai_systems=[],
        regulations=[],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    assert original_org.governance_roles == []
    assert result.organization.governance_roles == ["CTO"]

    original_staff = next(s for s in profile.stakeholders if s.name == "staff")
    assert original_staff.involvement is None


def test_enrich_entities_emits_report(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(governance_roles=["Board"]),
        stakeholders=[
            _SlimStakeholderDetail(name="staff", involvement="intended"),
        ],
        ai_systems=[
            _SlimAiSystemDetail(name="Chatbot", modality="text-to-text"),
        ],
        regulations=[
            _SlimRegulationDetail(name="FCA", jurisdiction="UK"),
        ],
    )

    report = _make_report()
    enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config, report=report)

    entity_events = [e for e in report.events if e["event"] == "entities_enriched"]
    assert len(entity_events) == 1
    assert entity_events[0]["stakeholders_enriched"] == 1
    assert entity_events[0]["systems_enriched"] == 1
    assert entity_events[0]["regulations_enriched"] == 1
    assert entity_events[0]["org_enriched"] is True


def test_enrich_entities_populates_trustworthy_interests(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(),
        stakeholders=[
            _SlimStakeholderDetail(
                name="staff",
                involvement="intended",
                activity="active",
                awareness="informed",
                output_control="correct",
                relationship="internal",
                interests=["efficiency", "accuracy"],
            ),
            _SlimStakeholderDetail(
                name="customers",
                involvement="unintended",
                activity="passive",
                awareness="uninformed",
                output_control="cannot_opt_out",
                relationship="external",
                interests=["privacy", "fair treatment"],
            ),
        ],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.interests == ["efficiency", "accuracy"]
    assert "accuracy" in staff.trustworthy_interests

    customers = next(s for s in result.stakeholders if s.name == "customers")
    assert customers.interests == ["privacy", "fair treatment"]
    assert "privacy" in customers.trustworthy_interests
    assert "fairness" in customers.trustworthy_interests


def test_enrich_entities_trustworthy_interests_empty_when_no_match(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(),
        stakeholders=[
            _SlimStakeholderDetail(
                name="staff",
                involvement="intended",
                activity="active",
                awareness="informed",
                output_control="correct",
                relationship="internal",
                interests=["efficiency", "cost reduction"],
            ),
        ],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.interests == ["efficiency", "cost reduction"]
    assert staff.trustworthy_interests == []


def test_enrich_entities_trustworthy_interests_empty_when_no_interests(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(),
        stakeholders=[
            _SlimStakeholderDetail(
                name="staff",
                involvement="intended",
                activity="active",
                awareness="informed",
                output_control="correct",
                relationship="internal",
                interests=[],
            ),
        ],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.interests == []
    assert staff.trustworthy_interests == []


def test_ingest_with_entity_enrichment(mock_client, mock_config):
    mock_client.chat.completions.create.side_effect = [
        # Pass 1: context
        _SlimContext(
            organization="South West Bank",
            domain="banking",
            purpose=["support"],
            ai_systems=["Chatbot"],
            ai_users=["staff"],
            ai_subjects=["customers"],
            governing_regulations=["FCA"],
            named_entities=[],
        ),
        # Pass 2: policies
        _SlimPolicyList(
            policies=[
                _SlimPolicy(policy_concept="Fraud", concept_definition="About fraud"),
            ]
        ),
        # Pass 3: enrichment
        _SlimEnrichmentList(
            enrichments=[
                _SlimEnrichment(
                    policy_concept="Fraud",
                    boundary_examples=[],
                    acceptable_uses=[],
                    risk_controls=[],
                    human_involvement="",
                ),
            ]
        ),
        # Pass 4: entity enrichment
        _SlimEntityEnrichment(
            organization=_SlimOrgDetail(governance_roles=["CTO"]),
            stakeholders=[
                _SlimStakeholderDetail(name="staff", involvement="intended", activity="active"),
                _SlimStakeholderDetail(name="customers", involvement="unintended", activity="passive"),
            ],
            ai_systems=[
                _SlimAiSystemDetail(name="Chatbot", modality="text-to-text", automation_level="advisory"),
            ],
            regulations=[
                _SlimRegulationDetail(name="FCA", jurisdiction="United Kingdom"),
            ],
        ),
    ]
    result = ingest(SAMPLE_MARKDOWN, "markdown", mock_client, mock_config)
    assert mock_client.chat.completions.create.call_count == 4

    assert result.organization.governance_roles == ["CTO"]

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.involvement == "intended"
    assert staff.activity == "active"

    chatbot = next(s for s in result.ai_systems if s.name == "Chatbot")
    assert chatbot.modality == "text-to-text"

    fca = next(r for r in result.regulations if r.name == "FCA")
    assert fca.jurisdiction == "United Kingdom"


# ---------------------------------------------------------------------------
# Document chunking
# ---------------------------------------------------------------------------

def test_estimate_tokens():
    assert _estimate_tokens("a" * 400) == 100
    assert _estimate_tokens("") == 0


def test_max_doc_tokens_no_limit():
    from risk_landscaper.llm import LLMConfig
    config = LLMConfig(base_url="http://x", model="m", max_context=0)
    assert _max_doc_tokens(config) is None


def test_max_doc_tokens_with_limit():
    from risk_landscaper.llm import LLMConfig
    config = LLMConfig(base_url="http://x", model="m", max_context=16384, max_tokens=8192)
    budget = _max_doc_tokens(config)
    assert budget == 16384 - 8192 - 3000


def test_chunk_document_fits():
    text = "Short document"
    assert _chunk_document(text, 1000) == [text]


def test_chunk_document_splits_on_h2():
    text = "# Title\n\nIntro paragraph.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B."
    chunks = _chunk_document(text, 60)
    assert len(chunks) >= 2
    assert "Section A" in chunks[0] or "Section A" in chunks[1]
    assert "Section B" in chunks[-1]


def test_chunk_document_falls_back_to_paragraphs():
    text = "Para 1.\n\nPara 2.\n\nPara 3.\n\nPara 4."
    chunks = _chunk_document(text, 20)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk) <= 20


def test_ingest_chunked_path(mock_client, mock_config):
    """When max_context is set and document is large, chunking kicks in."""
    mock_config.max_context = 3300
    mock_config.max_tokens = 100

    large_doc = "# Title\n\nIntro.\n\n## Section A\n\n" + "A content. " * 50 + "\n\n## Section B\n\n" + "B content. " * 50

    mock_client.chat.completions.create.side_effect = [
        # Pass 1: context (from first chunk)
        _SlimContext(
            organization="TestOrg", domain="tech", purpose=["testing"],
            ai_systems=[], ai_users=[], ai_subjects=[],
            governing_regulations=[], named_entities=[],
        ),
        # Pass 2: policies from chunk 1
        _SlimPolicyList(policies=[
            _SlimPolicy(policy_concept="PolicyA", concept_definition="About A"),
        ]),
        # Pass 2: policies from chunk 2
        _SlimPolicyList(policies=[
            _SlimPolicy(policy_concept="PolicyB", concept_definition="About B"),
        ]),
        # Pass 3: enrichment chunk 1
        _SlimEnrichmentList(enrichments=[
            _SlimEnrichment(
                policy_concept="PolicyA", boundary_examples=[],
                acceptable_uses=["use A"], risk_controls=[], human_involvement="",
            ),
        ]),
        # Pass 3: enrichment chunk 2
        _SlimEnrichmentList(enrichments=[
            _SlimEnrichment(
                policy_concept="PolicyB", boundary_examples=[],
                acceptable_uses=["use B"], risk_controls=[], human_involvement="",
            ),
        ]),
    ]

    result = ingest(large_doc, "markdown", mock_client, mock_config, skip_entity_enrichment=True)
    assert result.organization.name == "TestOrg"
    concepts = {p.policy_concept for p in result.policies}
    assert "PolicyA" in concepts
    assert "PolicyB" in concepts


def test_ingest_chunked_deduplicates_policies(mock_client, mock_config):
    """Policies found in multiple chunks are deduplicated."""
    mock_config.max_context = 3300
    mock_config.max_tokens = 100

    large_doc = "# Title\n\nIntro.\n\n## Section A\n\n" + "x " * 300 + "\n\n## Section B\n\n" + "y " * 300

    mock_client.chat.completions.create.side_effect = [
        _SlimContext(
            organization="Org", domain="tech", purpose=[],
            ai_systems=[], ai_users=[], ai_subjects=[],
            governing_regulations=[], named_entities=[],
        ),
        # Both chunks find "SharedPolicy"
        _SlimPolicyList(policies=[
            _SlimPolicy(policy_concept="SharedPolicy", concept_definition="Def 1"),
        ]),
        _SlimPolicyList(policies=[
            _SlimPolicy(policy_concept="SharedPolicy", concept_definition="Def 2"),
            _SlimPolicy(policy_concept="UniquePolicy", concept_definition="Def 3"),
        ]),
        _SlimEnrichmentList(enrichments=[]),
        _SlimEnrichmentList(enrichments=[]),
    ]

    result = ingest(large_doc, "markdown", mock_client, mock_config,
                    skip_entity_enrichment=True)
    concepts = [p.policy_concept for p in result.policies]
    assert concepts.count("SharedPolicy") == 1
    assert "UniquePolicy" in concepts
