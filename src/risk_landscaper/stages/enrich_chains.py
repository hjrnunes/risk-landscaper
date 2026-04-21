import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

import instructor
from pydantic import BaseModel

from risk_landscaper import debug
from risk_landscaper.llm import LLMConfig
from risk_landscaper.models import (
    Policy,
    PolicyRiskMapping,
    RiskCard,
    RiskConsequence,
    RiskImpact,
    RiskLandscape,
    RiskSource,
)
from risk_landscaper.prompts import render_prompt

logger = logging.getLogger(__name__)

_LIKELIHOOD = Literal["very_low", "low", "medium", "high", "very_high"]
_SEVERITY = Literal["very_low", "low", "medium", "high", "very_high"]


class _CausalChainSource(BaseModel):
    description: str
    source_type: Literal["data", "model", "attack", "organisational", "performance"]
    likelihood: _LIKELIHOOD | None = None


class _CausalChainConsequence(BaseModel):
    description: str
    likelihood: _LIKELIHOOD | None = None
    severity: _SEVERITY | None = None


class _CausalChainImpact(BaseModel):
    description: str
    severity: _SEVERITY | None = None
    area: str | None = None
    affected_stakeholders: list[str] = []
    harm_type: Literal[
        "representational", "allocative", "quality_of_service",
        "interpersonal", "societal", "legal",
    ] | None = None


class _CausalChain(BaseModel):
    risk_sources: list[_CausalChainSource]
    consequences: list[_CausalChainConsequence]
    impacts: list[_CausalChainImpact]
    materialization_conditions: str
    risk_level: _LIKELIHOOD


def _collect_primary_risk_ids(mappings: list[PolicyRiskMapping]) -> set[str]:
    return {
        rm.risk_id
        for m in mappings
        for rm in m.matched_risks
        if rm.relevance == "primary"
    }


def _build_policy_context(
    risk_id: str,
    mappings: list[PolicyRiskMapping],
    policies: list[Policy],
) -> list[dict[str, str]]:
    related_concepts = {
        m.policy_concept
        for m in mappings
        if any(rm.risk_id == risk_id for rm in m.matched_risks)
    }
    policy_by_concept = {p.policy_concept: p for p in policies}
    return [
        {"concept": c, "definition": policy_by_concept[c].concept_definition}
        for c in sorted(related_concepts)
        if c in policy_by_concept
    ]


def _merge_chain(card: RiskCard, chain: _CausalChain) -> None:
    card.risk_sources = [
        RiskSource(
            description=s.description,
            source_type=s.source_type,
            likelihood=s.likelihood,
        )
        for s in chain.risk_sources
    ]
    card.consequences = [
        RiskConsequence(
            description=c.description,
            likelihood=c.likelihood,
            severity=c.severity,
        )
        for c in chain.consequences
    ]
    card.impacts = [
        RiskImpact(
            description=i.description,
            severity=i.severity,
            area=i.area,
            affected_stakeholders=i.affected_stakeholders,
            harm_type=i.harm_type,
        )
        for i in chain.impacts
    ]
    card.materialization_conditions = chain.materialization_conditions
    card.risk_level = chain.risk_level


def _enrich_single_risk(
    card: RiskCard,
    policy_context: list[dict[str, str]],
    client: instructor.Instructor,
    config: LLMConfig,
    report=None,
) -> None:
    source_type_hint = (
        card.risk_sources[0].source_type if card.risk_sources else None
    )
    messages = render_prompt("enrich_chains", {
        "risk_name": card.risk_name,
        "risk_description": card.risk_description or "",
        "risk_concern": card.risk_concern or "",
        "risk_type": card.risk_type or "",
        "source_type_hint": source_type_hint or "",
        "policies": policy_context,
    })
    t0 = time.monotonic()
    chain = client.chat.completions.create(
        model=config.model,
        response_model=_CausalChain,
        messages=messages,
        temperature=config.temperature,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
    )
    duration_ms = (time.monotonic() - t0) * 1000
    debug.log_call("enrich_chains", messages, chain, context={
        "risk_id": card.risk_id,
    }, report=report, duration_ms=duration_ms)
    _merge_chain(card, chain)

    if report:
        report.events.append({
            "stage": "enrich_chains",
            "event": "chain_synthesized",
            "risk_id": card.risk_id,
            "sources": len(chain.risk_sources),
            "consequences": len(chain.consequences),
            "impacts": len(chain.impacts),
            "risk_level": chain.risk_level,
        })


def enrich_chains(
    landscape: RiskLandscape,
    policies: list[Policy],
    client: instructor.Instructor,
    config: LLMConfig,
    report=None,
) -> None:
    primary_ids = _collect_primary_risk_ids(landscape.policy_mappings)
    if not primary_ids:
        logger.info("enrich_chains: no primary-relevance risks, skipping")
        return

    cards_to_enrich = [c for c in landscape.risks if c.risk_id in primary_ids]
    logger.info(
        "enrich_chains: enriching %d/%d risks (primary relevance)",
        len(cards_to_enrich), len(landscape.risks),
    )

    def _process(card: RiskCard) -> None:
        policy_ctx = _build_policy_context(
            card.risk_id, landscape.policy_mappings, policies,
        )
        _enrich_single_risk(card, policy_ctx, client, config, report)

    max_workers = min(config.max_concurrent, len(cards_to_enrich))
    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(_process, cards_to_enrich))
    else:
        for card in cards_to_enrich:
            _process(card)
