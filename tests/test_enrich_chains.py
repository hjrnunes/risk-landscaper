import pytest
from unittest.mock import MagicMock, patch
from risk_landscaper.models import (
    RiskCard, RiskLandscape, RiskSource, PolicyRiskMapping, RiskMatch, Policy,
)
from risk_landscaper.llm import LLMConfig


@pytest.fixture
def sample_landscape():
    return RiskLandscape(
        model="test-model",
        timestamp="t",
        run_slug="test",
        risks=[
            RiskCard(
                risk_id="atlas-bias",
                risk_name="Bias",
                risk_description="Model exhibits systematic bias",
                risk_concern="Discriminatory outputs affecting users",
                risk_type="output",
                risk_sources=[RiskSource(description="Discriminatory outputs", source_type="model")],
                related_policies=["Fairness Policy"],
            ),
            RiskCard(
                risk_id="atlas-hallucination",
                risk_name="Hallucination",
                risk_description="Model generates false information",
                risk_concern="Incorrect outputs",
                risk_type="output",
                risk_sources=[RiskSource(description="Incorrect outputs", source_type="model")],
                related_policies=["Accuracy Policy"],
            ),
        ],
        policy_mappings=[
            PolicyRiskMapping(
                policy_concept="Fairness Policy",
                matched_risks=[
                    RiskMatch(risk_id="atlas-bias", risk_name="Bias",
                              relevance="primary", justification="test"),
                ],
            ),
            PolicyRiskMapping(
                policy_concept="Accuracy Policy",
                matched_risks=[
                    RiskMatch(risk_id="atlas-hallucination", risk_name="Hallucination",
                              relevance="supporting", justification="test"),
                ],
            ),
        ],
    )


def test_collect_primary_risk_ids(sample_landscape):
    from risk_landscaper.stages.enrich_chains import _collect_primary_risk_ids
    primary = _collect_primary_risk_ids(sample_landscape.policy_mappings)
    assert primary == {"atlas-bias"}


def test_collect_primary_risk_ids_empty():
    from risk_landscaper.stages.enrich_chains import _collect_primary_risk_ids
    assert _collect_primary_risk_ids([]) == set()


def test_build_policy_context(sample_landscape):
    from risk_landscaper.stages.enrich_chains import _build_policy_context
    policies = [
        Policy(policy_concept="Fairness Policy", concept_definition="Equal treatment for all users"),
        Policy(policy_concept="Accuracy Policy", concept_definition="Factual correctness"),
    ]
    ctx = _build_policy_context("atlas-bias", sample_landscape.policy_mappings, policies)
    assert len(ctx) == 1
    assert ctx[0]["concept"] == "Fairness Policy"
    assert ctx[0]["definition"] == "Equal treatment for all users"


def test_enrich_chains_skips_non_primary(sample_landscape):
    from risk_landscaper.stages.enrich_chains import enrich_chains, _CausalChain, _CausalChainSource, _CausalChainConsequence, _CausalChainImpact
    config = LLMConfig(base_url="http://localhost:8000/v1", model="test-model")
    client = MagicMock()
    client.chat.completions.create.return_value = _CausalChain(
        risk_sources=[_CausalChainSource(description="test", source_type="model")],
        consequences=[_CausalChainConsequence(description="test consequence")],
        impacts=[_CausalChainImpact(description="test impact")],
        materialization_conditions="when tested",
        risk_level="medium",
    )

    policies = [
        Policy(policy_concept="Fairness Policy", concept_definition="Equal treatment"),
        Policy(policy_concept="Accuracy Policy", concept_definition="Factual correctness"),
    ]
    enrich_chains(sample_landscape, policies, client, config)

    # hallucination is "supporting", so only bias should trigger LLM call
    assert client.chat.completions.create.call_count == 1


def test_merge_chain_onto_card():
    from risk_landscaper.stages.enrich_chains import _merge_chain
    from risk_landscaper.stages.enrich_chains import (
        _CausalChain, _CausalChainSource, _CausalChainConsequence, _CausalChainImpact,
    )

    card = RiskCard(
        risk_id="r1", risk_name="R",
        risk_sources=[RiskSource(description="existing", source_type="model")],
    )
    chain = _CausalChain(
        risk_sources=[
            _CausalChainSource(description="Biased training data", source_type="data", likelihood="high"),
        ],
        consequences=[
            _CausalChainConsequence(description="Discriminatory outputs", likelihood="medium", severity="high"),
        ],
        impacts=[
            _CausalChainImpact(
                description="Users receive unfair treatment",
                severity="high", area="non_discrimination",
                affected_stakeholders=["end users"], harm_type="allocative",
            ),
        ],
        materialization_conditions="When model processes data about protected groups",
        risk_level="high",
    )
    _merge_chain(card, chain)

    assert len(card.risk_sources) == 1
    assert card.risk_sources[0].description == "Biased training data"
    assert card.risk_sources[0].source_type == "data"
    assert len(card.consequences) == 1
    assert card.consequences[0].severity == "high"
    assert len(card.impacts) == 1
    assert card.impacts[0].harm_type == "allocative"
    assert card.impacts[0].area == "non_discrimination"
    assert card.materialization_conditions == "When model processes data about protected groups"
    assert card.risk_level == "high"
