import logging
from typing import Callable, TypeVar

from risk_landscaper.models import (
    AiSystem,
    BoundaryExample,
    Organization,
    Policy,
    PolicyProfile,
    RegulatoryReference,
    Stakeholder,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _union_lists(a: list[str], b: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in a + b:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _merge_by_key(
    items: list[T],
    key_fn: Callable[[T], str],
    merge_fn: Callable[[T, T], T],
) -> list[T]:
    seen: dict[str, T] = {}
    order: list[str] = []
    for item in items:
        k = key_fn(item)
        if k in seen:
            seen[k] = merge_fn(seen[k], item)
        else:
            seen[k] = item
            order.append(k)
    return [seen[k] for k in order]


def _merge_organizations(a: Organization, b: Organization) -> Organization:
    return Organization(
        name=a.name,
        description=a.description or b.description,
        governance_roles=_union_lists(a.governance_roles, b.governance_roles),
        management_system=a.management_system or b.management_system,
        certifications=_union_lists(a.certifications, b.certifications),
        delegates=_union_lists(a.delegates, b.delegates),
    )


def _merge_stakeholders(a: Stakeholder, b: Stakeholder) -> Stakeholder:
    return Stakeholder(
        name=a.name,
        roles=_union_lists(a.roles, b.roles),
        description=a.description or b.description,
        involvement=a.involvement or b.involvement,
        activity=a.activity or b.activity,
        awareness=a.awareness or b.awareness,
        output_control=a.output_control or b.output_control,
        relationship=a.relationship or b.relationship,
        interests=_union_lists(a.interests, b.interests),
    )


def _merge_ai_systems(a: AiSystem, b: AiSystem) -> AiSystem:
    return AiSystem(
        name=a.name,
        description=a.description or b.description,
        purpose=_union_lists(a.purpose, b.purpose),
        risk_level=a.risk_level or b.risk_level,
        modality=a.modality or b.modality,
        techniques=_union_lists(a.techniques, b.techniques),
        automation_level=a.automation_level or b.automation_level,
        serves_stakeholders=_union_lists(a.serves_stakeholders, b.serves_stakeholders),
        assets=_union_lists(a.assets, b.assets),
    )


def _merge_regulations(
    a: RegulatoryReference, b: RegulatoryReference
) -> RegulatoryReference:
    return RegulatoryReference(
        name=a.name,
        jurisdiction=a.jurisdiction or b.jurisdiction,
        reference=a.reference or b.reference,
    )


def _merge_policies(a: Policy, b: Policy) -> Policy:
    definition = a.concept_definition if len(a.concept_definition) >= len(b.concept_definition) else b.concept_definition

    seen_boundaries: set[tuple[str, str]] = {
        (be.prohibited, be.acceptable) for be in a.boundary_examples
    }
    merged_boundaries = list(a.boundary_examples)
    for be in b.boundary_examples:
        key = (be.prohibited, be.acceptable)
        if key not in seen_boundaries:
            merged_boundaries.append(be)
            seen_boundaries.add(key)

    return Policy(
        policy_concept=a.policy_concept,
        concept_definition=definition,
        governance_function=a.governance_function or b.governance_function,
        boundary_examples=merged_boundaries,
        acceptable_uses=_union_lists(a.acceptable_uses, b.acceptable_uses),
        risk_controls=_union_lists(a.risk_controls, b.risk_controls),
        human_involvement=a.human_involvement or b.human_involvement,
        affects_stakeholders=_union_lists(a.affects_stakeholders, b.affects_stakeholders),
        applies_to_systems=_union_lists(a.applies_to_systems, b.applies_to_systems),
        decomposition=a.decomposition or b.decomposition,
        source_documents=_union_lists(a.source_documents, b.source_documents),
    )


def merge_profiles(
    profiles: list[PolicyProfile],
    sources: list[str],
) -> PolicyProfile:
    if not profiles:
        return PolicyProfile(source_documents=sources)

    if len(profiles) == 1:
        p = profiles[0]
        policies = [
            pol.model_copy(update={"source_documents": _union_lists(pol.source_documents, sources[:1])})
            if not pol.source_documents else pol
            for pol in p.policies
        ]
        return p.model_copy(update={
            "policies": policies,
            "source_documents": sources,
        })

    # Merge organizations
    orgs = [p.organization for p in profiles if p.organization]
    org = None
    if orgs:
        org = orgs[0]
        for o in orgs[1:]:
            if o.name.lower() != org.name.lower():
                logger.warning(
                    "Different organization names across documents: %r vs %r — using first",
                    org.name, o.name,
                )
            org = _merge_organizations(org, o)

    # Merge domain — keep longest (most specific)
    domains = [p.domain for p in profiles if p.domain]
    domain = max(domains, key=len) if domains else None

    # Merge purpose
    all_purposes: list[str] = []
    for p in profiles:
        all_purposes.extend(p.purpose)
    purpose = _union_lists(all_purposes, [])

    # Merge entities (case-insensitive)
    all_stakeholders = [s for p in profiles for s in p.stakeholders]
    stakeholders = _merge_by_key(all_stakeholders, lambda s: s.name.lower(), _merge_stakeholders)

    all_systems = [s for p in profiles for s in p.ai_systems]
    ai_systems = _merge_by_key(all_systems, lambda s: s.name.lower(), _merge_ai_systems)

    all_regs = [r for p in profiles for r in p.regulations]
    regulations = _merge_by_key(all_regs, lambda r: r.name.lower(), _merge_regulations)

    # Merge policies (exact match on policy_concept)
    all_policies = [pol for p in profiles for pol in p.policies]
    policies = _merge_by_key(all_policies, lambda p: p.policy_concept, _merge_policies)

    return PolicyProfile(
        organization=org,
        domain=domain,
        purpose=purpose,
        ai_systems=ai_systems,
        stakeholders=stakeholders,
        regulations=regulations,
        policies=policies,
        source_documents=sources,
    )
