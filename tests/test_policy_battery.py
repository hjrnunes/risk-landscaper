"""Test battery exercising the pipeline against real policy examples.

Tests format detection, parsing paths (no LLM), and ingest
orchestration (mock LLM) across all policy_examples/ files.
"""
import json
from pathlib import Path

import pytest

from risk_landscaper.cli import _load_input
from risk_landscaper.models import PolicyProfile, RunReport
from risk_landscaper.nexus_adapter import detect_nexus_format, nexus_to_policy_profile
from risk_landscaper.stages.ingest import (
    ingest,
    _SlimContext,
    _SlimNamedEntity,
    _SlimPolicyList,
    _SlimPolicy,
    _SlimEnrichmentList,
    _SlimEnrichment,
    _SlimBoundaryExample,
)

POLICY_DIR = Path(__file__).parent.parent / "policy_examples"

# ---- Catalog of all policy files with expected properties ----

MARKDOWN_FILES = [
    "aramco.md",
    "atlas-telecom.md",
    "commonwealth-insurance.md",
    "dhs-gov.md",
    "generic.md",
    "healthcare.md",
    "law.md",
    "meridian-bank.md",
    "rdash-nhs.md",
    "swb.md",
]

NEXUS_FILES = [
    ("nexus-healthcare.json", 3, 2),  # (filename, risk_count, control_count)
]

ALL_FILES = MARKDOWN_FILES + [f for f, _, _ in NEXUS_FILES]


# ---- Helpers ----

def _make_report():
    return RunReport(model="test", policy_set="test", timestamp="2026-01-01")


def _stub_context(org="Test Org", domain="general"):
    return _SlimContext(
        organization=org,
        domain=domain,
        purpose=["general"],
        ai_systems=["AI System"],
        ai_users=["user"],
        ai_subjects=["subject"],
        governing_regulations=[],
        named_entities=[],
    )


# ====================================================================
# 1. Format detection — _load_input classifies each file correctly
# ====================================================================

@pytest.mark.parametrize("filename", MARKDOWN_FILES)
def test_format_detection_markdown(filename):
    path = POLICY_DIR / filename
    _, fmt, pre_parsed = _load_input(path)
    assert fmt == "markdown", f"{filename} should be markdown, got {fmt}"
    assert pre_parsed is None


@pytest.mark.parametrize("filename,_rc,_cc", NEXUS_FILES)
def test_format_detection_nexus(filename, _rc, _cc):
    path = POLICY_DIR / filename
    _, fmt, pre_parsed = _load_input(path)
    assert fmt == "policy_profile", f"{filename} should be policy_profile, got {fmt}"
    assert pre_parsed is not None
    assert isinstance(pre_parsed, PolicyProfile)


# ====================================================================
# 2. Nexus format parsing (pure, no LLM)
# ====================================================================

@pytest.mark.parametrize("filename,risk_count,control_count", NEXUS_FILES)
def test_nexus_parsing(filename, risk_count, control_count):
    raw = json.loads((POLICY_DIR / filename).read_text())
    assert detect_nexus_format(raw) is True
    profile = nexus_to_policy_profile(raw)

    assert len(profile.policies) == risk_count
    assert profile.organization is not None
    assert profile.domain is not None
    assert len(profile.ai_systems) >= 1

    if control_count > 0:
        for p in profile.policies:
            assert len(p.risk_controls) == control_count


def test_nexus_healthcare_specifics():
    raw = json.loads((POLICY_DIR / "nexus-healthcare.json").read_text())
    profile = nexus_to_policy_profile(raw)

    assert profile.organization.name == "HealthTech Solutions"
    assert profile.domain == "healthcare"
    assert profile.ai_systems[0].name == "Medical Triage Chatbot"
    assert profile.ai_systems[0].risk_level == "high"

    concepts = {p.policy_concept for p in profile.policies}
    assert "Generating Inaccurate Output" in concepts
    assert "Personal Information in Prompt" in concepts
    assert "Societal Bias" in concepts

    deployers = [s.name for s in profile.stakeholders if "airo:AIDeployer" in s.roles]
    assert "City General Hospital" in deployers
    users = [s.name for s in profile.stakeholders if "airo:AIUser" in s.roles]
    assert "Emergency nurse" in users
    subjects = [s.name for s in profile.stakeholders if "airo:AISubject" in s.roles]
    assert "Emergency patient" in subjects


def test_nexus_profile_roundtrip():
    raw = json.loads((POLICY_DIR / "nexus-healthcare.json").read_text())
    profile = nexus_to_policy_profile(raw)
    d = profile.model_dump()
    restored = PolicyProfile(**d)
    assert restored.organization.name == profile.organization.name
    assert len(restored.policies) == len(profile.policies)
    assert restored.domain == profile.domain


# ====================================================================
# 4. Ingest orchestration — JSON array (2 LLM calls: context + enrichment)
# ====================================================================



# ====================================================================
# 5. Ingest orchestration — markdown (3 LLM calls: context + policies + enrichment)
# ====================================================================

INGEST_MD_CASES = [
    ("aramco.md", "energy", "Aramco"),
    ("atlas-telecom.md", "telecom", "Atlas Communications"),
    ("commonwealth-insurance.md", "insurance", "Commonwealth Insurance Group"),
    ("dhs-gov.md", "government", "U.S. Department of Homeland Security"),
    ("generic.md", "general", "Generic AI Provider"),
    ("healthcare.md", "healthcare", "Lakeview Health System"),
    ("law.md", "corporate", "Fisher & Phillips LLP"),
    ("meridian-bank.md", "banking", "Meridian Federal Bank"),
    ("rdash-nhs.md", "healthcare", "RDaSH NHS Foundation Trust"),
    ("swb.md", "banking", "South West Bank"),
]


@pytest.mark.parametrize("filename,domain,org", INGEST_MD_CASES)
def test_ingest_markdown(mock_client, mock_config, filename, domain, org):
    text = (POLICY_DIR / filename).read_text()

    extracted_policies = [
        _SlimPolicy(policy_concept="Policy A", concept_definition="About A"),
        _SlimPolicy(policy_concept="Policy B", concept_definition="About B"),
    ]

    mock_client.chat.completions.create.side_effect = [
        _stub_context(org=org, domain=domain),
        _SlimPolicyList(policies=extracted_policies),
        _SlimEnrichmentList(enrichments=[
            _SlimEnrichment(
                policy_concept="Policy A",
                boundary_examples=[
                    _SlimBoundaryExample(prohibited="bad", acceptable="good"),
                ],
                acceptable_uses=["education"],
                risk_controls=["review"],
                human_involvement="oversight required",
                governance_function="direct",
            ),
            _SlimEnrichment(
                policy_concept="Policy B",
                boundary_examples=[],
                acceptable_uses=[],
                risk_controls=[],
                human_involvement="",
            ),
        ]),
    ]

    report = _make_report()
    result = ingest(text, "markdown", mock_client, mock_config, skip_entity_enrichment=True, report=report)

    assert result.organization.name == org
    assert result.domain == domain
    assert len(result.policies) == 2
    assert mock_client.chat.completions.create.call_count == 3

    enriched = next(p for p in result.policies if p.policy_concept == "Policy A")
    assert len(enriched.boundary_examples) == 1
    assert enriched.governance_function == "direct"
    assert enriched.acceptable_uses == ["education"]


@pytest.mark.parametrize("filename,domain,org", INGEST_MD_CASES)
def test_ingest_markdown_until_context(mock_client, mock_config, filename, domain, org):
    text = (POLICY_DIR / filename).read_text()
    mock_client.chat.completions.create.side_effect = [
        _stub_context(org=org, domain=domain),
    ]

    result = ingest(text, "markdown", mock_client, mock_config, until="context")
    assert result.organization.name == org
    assert result.domain == domain
    assert result.policies == []
    assert mock_client.chat.completions.create.call_count == 1


# ====================================================================
# 6. Profile structural invariants (all formats)
# ====================================================================

@pytest.mark.parametrize("filename", ALL_FILES)
def test_load_produces_valid_text(filename):
    path = POLICY_DIR / filename
    text, fmt, _ = _load_input(path)
    assert len(text) > 0
    assert fmt in ("markdown", "json_array", "policy_profile")


@pytest.mark.parametrize("filename,risk_count,control_count", NEXUS_FILES)
def test_nexus_profile_all_policies_have_controls(filename, risk_count, control_count):
    raw = json.loads((POLICY_DIR / filename).read_text())
    profile = nexus_to_policy_profile(raw)
    for p in profile.policies:
        assert len(p.risk_controls) == control_count
        for ctrl in p.risk_controls:
            assert isinstance(ctrl, str)
            assert len(ctrl) > 0


# ====================================================================
# 7. Content-level checks on specific policy files
# ====================================================================

def test_generic_md_content():
    text = (POLICY_DIR / "generic.md").read_text()
    for topic in ["Illegal Activity", "Hate Speech", "Security and Malware",
                   "Violence", "Fraud", "Sexually Explicit", "Misinformation", "Self-Harm"]:
        assert topic in text


def test_healthcare_md_content():
    text = (POLICY_DIR / "healthcare.md").read_text()
    assert "Clinical Diagnosis" in text
    assert "Protected Health Information" in text
    assert "Insurance Fraud" in text
    assert text.count("Lakeview") >= 4


def test_swb_md_content():
    text = (POLICY_DIR / "swb.md").read_text()
    assert "Executive Compensation" in text
    assert "Fraud" in text
    assert "Money Laundering" in text or "Anti-Money Laundering" in text
    assert "Investment Advice" in text
    assert text.count("South West Bank") >= 2


def test_aramco_md_content():
    text = (POLICY_DIR / "aramco.md").read_text()
    assert "Proprietary Technical Data" in text
    assert "Operational Security" in text
    assert "Compliance and Sanctions Evasion" in text


# ====================================================================
# 8. Markdown files are loadable and non-trivial
# ====================================================================

@pytest.mark.parametrize("filename", MARKDOWN_FILES)
def test_markdown_non_trivial(filename):
    text = (POLICY_DIR / filename).read_text()
    assert len(text) > 500, f"{filename} is suspiciously short"
    assert text.strip(), f"{filename} is empty"


@pytest.mark.parametrize("filename,expected_substr", [
    ("aramco.md", "Aramco"),
    ("atlas-telecom.md", "Atlas Communications"),
    ("commonwealth-insurance.md", "Commonwealth Insurance"),
    ("dhs-gov.md", "Department of Homeland Security"),
    ("generic.md", "AI Safety Policy"),
    ("healthcare.md", "Lakeview Health System"),
    ("law.md", "Generative AI"),
    ("meridian-bank.md", "Meridian Federal Bank"),
    ("rdash-nhs.md", "RDaSH"),
    ("swb.md", "South West Bank"),
])
def test_markdown_contains_expected_org(filename, expected_substr):
    text = (POLICY_DIR / filename).read_text()
    assert expected_substr in text


