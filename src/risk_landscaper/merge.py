import logging
from typing import Callable, TypeVar

from risk_landscaper.models import (
    AiSystem,
    Organization,
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
