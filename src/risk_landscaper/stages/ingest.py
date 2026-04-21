import json
import logging
from typing import Literal

import instructor
from pydantic import BaseModel
from risk_landscaper.llm import LLMConfig
from risk_landscaper.models import (
    BoundaryExample,
    AiSystem,
    Policy,
    PolicyDecomposition,
    PolicyProfile,
    RegulatoryReference,
    RunReport,
    Stakeholder,
)
from risk_landscaper.prompts import render_prompt, load_cot
from risk_landscaper import debug

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Slim response models (private, no docstrings)
# ---------------------------------------------------------------------------

class _SlimNamedEntity(BaseModel):
    name: str
    role: str


class _SlimContext(BaseModel):
    organization: str
    domain: str
    purpose: list[str]
    ai_systems: list[str]
    ai_users: list[str]
    ai_subjects: list[str]
    governing_regulations: list[str]
    named_entities: list[_SlimNamedEntity]


class _SlimPolicy(BaseModel):
    policy_concept: str
    concept_definition: str


class _SlimPolicyList(BaseModel):
    policies: list[_SlimPolicy]


class _SlimBoundaryExample(BaseModel):
    prohibited: str
    acceptable: str


class _SlimEnrichment(BaseModel):
    policy_concept: str
    boundary_examples: list[_SlimBoundaryExample]
    acceptable_uses: list[str]
    risk_controls: list[str]
    human_involvement: str = ""
    agent: str = ""
    activity: str = ""
    entity: str = ""


class _SlimEnrichmentList(BaseModel):
    enrichments: list[_SlimEnrichment]


# ---------------------------------------------------------------------------
# Prompt rendering
# ---------------------------------------------------------------------------

def _render_context_messages(document_text: str) -> list[dict[str, str]]:
    cot = load_cot()
    return render_prompt("ingest_context", {
        "document_text": document_text,
        "cot_examples": cot.get("context_examples", []),
    })


def _render_policies_messages(document_text: str, context: _SlimContext) -> list[dict[str, str]]:
    cot = load_cot()
    return render_prompt("ingest_policies", {
        "document_text": document_text,
        "organization": context.organization,
        "domain": context.domain,
        "cot_examples": cot.get("policy_examples", []),
    })


def _render_enrichment_messages(
    document_text: str,
    context: _SlimContext,
    policies: list[Policy],
) -> list[dict[str, str]]:
    cot = load_cot()
    return render_prompt("ingest_enrichment", {
        "document_text": document_text,
        "organization": context.organization,
        "domain": context.domain,
        "policies": policies,
        "cot_examples": cot.get("enrichment_examples", []),
    })


# ---------------------------------------------------------------------------
# Pass 1: Context extraction
# ---------------------------------------------------------------------------

def extract_context(
    document_text: str,
    client: instructor.Instructor,
    config: LLMConfig,
    report: RunReport | None = None,
) -> _SlimContext:
    messages = _render_context_messages(document_text)

    result = client.chat.completions.create(
        model=config.model,
        response_model=_SlimContext,
        messages=messages,
        temperature=config.temperature,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
    )
    debug.log_call("ingest_context", messages, result)

    if report:
        # Count populated fields
        fields_populated = sum(1 for v in [
            result.organization, result.domain, result.purpose,
            result.ai_systems, result.ai_users, result.ai_subjects,
            result.governing_regulations, result.named_entities,
        ] if v)
        report.events.append({
            "stage": "ingest",
            "event": "context_extracted",
            "organization": result.organization,
            "domain": result.domain,
            "fields_populated": fields_populated,
        })

        # Warn on missing critical fields
        missing = []
        if not result.organization:
            missing.append("organization")
        if not result.domain:
            missing.append("domain")
        if missing:
            report.events.append({
                "stage": "ingest",
                "event": "context_weak_inference",
                "missing_fields": missing,
            })

    return result


# ---------------------------------------------------------------------------
# Pass 2: Policy extraction
# ---------------------------------------------------------------------------

def extract_policies(
    document_text: str,
    context: _SlimContext,
    client: instructor.Instructor,
    config: LLMConfig,
    report: RunReport | None = None,
) -> list[Policy]:
    messages = _render_policies_messages(document_text, context)

    result = client.chat.completions.create(
        model=config.model,
        response_model=_SlimPolicyList,
        messages=messages,
        temperature=config.temperature,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
    )
    debug.log_call("ingest_policies", messages, result)

    policies = [
        Policy(
            policy_concept=p.policy_concept,
            concept_definition=p.concept_definition,
        )
        for p in result.policies
    ]

    if report:
        report.events.append({
            "stage": "ingest",
            "event": "policies_extracted",
            "count": len(policies),
        })

    return policies


# ---------------------------------------------------------------------------
# JSON array parser (pure function, no LLM)
# ---------------------------------------------------------------------------

def parse_json_policies(json_text: str) -> list[Policy]:
    raw = json.loads(json_text)
    return [
        Policy(
            policy_concept=entry.get("policy_concept", ""),
            concept_definition=entry.get("concept_definition", ""),
        )
        for entry in raw
    ]


# ---------------------------------------------------------------------------
# Pass 3: Policy enrichment
# ---------------------------------------------------------------------------

def enrich_policies(
    document_text: str,
    context: _SlimContext,
    policies: list[Policy],
    client: instructor.Instructor,
    config: LLMConfig,
    report: RunReport | None = None,
) -> list[Policy]:
    messages = _render_enrichment_messages(document_text, context, policies)

    result = client.chat.completions.create(
        model=config.model,
        response_model=_SlimEnrichmentList,
        messages=messages,
        temperature=config.temperature,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
    )
    debug.log_call("ingest_enrichment", messages, result)

    # Build lookup by policy_concept
    enrichment_map: dict[str, _SlimEnrichment] = {}
    for e in result.enrichments:
        enrichment_map[e.policy_concept] = e

    # Create new Policy objects (don't mutate inputs)
    enriched: list[Policy] = []
    policies_enriched = 0
    boundary_pairs_total = 0
    policies_with_zero_pairs = 0

    for p in policies:
        e = enrichment_map.get(p.policy_concept)
        if e is not None:
            policies_enriched += 1
            boundary_pairs_total += len(e.boundary_examples)
            if not e.boundary_examples:
                policies_with_zero_pairs += 1
            decomposition = None
            if e.agent or e.activity or e.entity:
                decomposition = PolicyDecomposition(
                    agent=e.agent or None,
                    activity=e.activity or None,
                    entity=e.entity or None,
                )
            enriched.append(Policy(
                policy_concept=p.policy_concept,
                concept_definition=p.concept_definition,
                boundary_examples=[
                    BoundaryExample(prohibited=b.prohibited, acceptable=b.acceptable)
                    for b in e.boundary_examples
                ],
                acceptable_uses=e.acceptable_uses,
                risk_controls=e.risk_controls,
                human_involvement=e.human_involvement if e.human_involvement else None,
                decomposition=decomposition,
            ))
        else:
            policies_with_zero_pairs += 1
            enriched.append(Policy(
                policy_concept=p.policy_concept,
                concept_definition=p.concept_definition,
            ))

    if report:
        report.events.append({
            "stage": "ingest",
            "event": "enrichment_stats",
            "policies_enriched": policies_enriched,
            "boundary_pairs_total": boundary_pairs_total,
            "policies_with_zero_pairs": policies_with_zero_pairs,
        })

    return enriched


# ---------------------------------------------------------------------------
# Helper: build PolicyProfile from context + policies
# ---------------------------------------------------------------------------

def _build_document(context: _SlimContext, policies: list[Policy]) -> PolicyProfile:
    stakeholders: list[Stakeholder] = []
    for u in context.ai_users:
        stakeholders.append(Stakeholder(name=u, roles=["airo:AIUser"]))
    for s in context.ai_subjects:
        stakeholders.append(Stakeholder(name=s, roles=["airo:AISubject"]))
    for ne in context.named_entities:
        stakeholders.append(Stakeholder(name=ne.name, roles=[ne.role]))
    return PolicyProfile(
        organization=Stakeholder(name=context.organization) if context.organization else None,
        domain=context.domain,
        purpose=context.purpose,
        ai_systems=[AiSystem(name=s) for s in context.ai_systems],
        stakeholders=stakeholders,
        regulations=[RegulatoryReference(name=r) for r in context.governing_regulations],
        policies=policies,
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def ingest(
    document_text: str,
    input_format: Literal["markdown", "json_array"],
    client: instructor.Instructor,
    config: LLMConfig,
    skip_enrichment: bool = False,
    until: str | None = None,
    domain_override: str | None = None,
    organization_override: str | None = None,
    report: RunReport | None = None,
) -> PolicyProfile:
    if report:
        report.events.append({
            "stage": "ingest",
            "event": "input_format_detected",
            "format": input_format,
        })

    # Pass 1: Context extraction (always)
    context = extract_context(document_text, client, config, report=report)

    # Apply overrides
    if domain_override:
        context = context.model_copy(update={"domain": domain_override})
    if organization_override:
        context = context.model_copy(update={"organization": organization_override})

    if until == "context":
        return _build_document(context, [])

    # Pass 2: Policy extraction
    if input_format == "json_array":
        policies = parse_json_policies(document_text)
        if report:
            report.events.append({
                "stage": "ingest",
                "event": "policies_extracted",
                "count": len(policies),
                "skipped": True,
            })
    else:
        policies = extract_policies(document_text, context, client, config, report=report)

    if until == "policies":
        return _build_document(context, policies)

    # Pass 3: Enrichment
    if not skip_enrichment:
        policies = enrich_policies(
            document_text, context, policies, client, config, report=report,
        )
    else:
        if report:
            report.events.append({
                "stage": "ingest",
                "event": "enrichment_skipped",
            })

    return _build_document(context, policies)
