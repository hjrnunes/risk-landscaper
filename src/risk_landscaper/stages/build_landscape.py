from risk_landscaper.models import (
    CoverageGap,
    GovernanceProvenance,
    PolicyProfile,
    PolicyRiskMapping,
    PolicySourceRef,
    RiskCard,
    RiskConsequence,
    RiskControl,
    RiskImpact,
    RiskIncidentRef,
    RiskLandscape,
    RiskSource,
    KnowledgeBaseRef,
    WeakMatch,
)
from risk_landscaper.vair import match_all as vair_match_all

WEAK_MATCH_THRESHOLD = 0.6

FRAMEWORK_PREFIXES = {
    "atlas-": "IBM Risk Atlas",
    "nist-": "NIST AI RMF",
    "owasp-": "OWASP LLM Top 10",
    "llm0": "OWASP LLM Top 10",
    "ai-risk-taxonomy-": "AIR 2024",
    "air-": "AIR 2024",
    "mit-ai-risk": "MIT AI Risk Repository",
    "ail-": "AILuminate",
    "credo-": "Credo AI",
    "aiuc-": "AIUC-1",
    "csiro-": "CSIRO",
    "shieldgemma-": "ShieldGemma",
}


def _detect_framework(risk_id: str) -> str:
    for prefix, framework in FRAMEWORK_PREFIXES.items():
        if risk_id.startswith(prefix):
            return framework
    return "unknown"


_CONTROL_TYPE_KEYWORDS: dict[str, list[str]] = {
    "detect": ["detect", "monitor", "audit", "alert", "log", "track", "scan"],
    "evaluate": ["evaluate", "assess", "benchmark", "test", "measure", "review"],
    "mitigate": ["mitigate", "reduce", "limit", "filter", "moderate", "constrain"],
    "eliminate": ["eliminate", "prevent", "prohibit", "block", "remove", "disable"],
}

_TARGET_KEYWORDS: dict[str, list[str]] = {
    "source": ["source", "data", "input", "training", "dataset"],
    "consequence": ["output", "result", "response", "generation"],
}


def _infer_control_type(description: str) -> str | None:
    lower = description.lower()
    for control_type, keywords in _CONTROL_TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return control_type
    return None


def _infer_control_targets(description: str) -> str:
    lower = description.lower()
    for target, keywords in _TARGET_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return target
    return "risk"


_RISK_TYPE_TO_SOURCE_TYPE: dict[str, str] = {
    "training-data": "data",
    "input": "data",
    "output": "model",
    "inference": "model",
    "non-technical": "organisational",
    "agentic": "model",
}


def _infer_source_type(risk_type: str | None) -> str | None:
    if not risk_type:
        return None
    return _RISK_TYPE_TO_SOURCE_TYPE.get(risk_type)


def _actions_to_controls(action_descriptions: list[str]) -> list[RiskControl]:
    return [
        RiskControl(
            description=desc,
            control_type=_infer_control_type(desc),
            targets=_infer_control_targets(desc),
            provenance="nexus",
        )
        for desc in action_descriptions
        if desc
    ]


def _vair_enrich(description: str, concern: str) -> dict:
    text = f"{description} {concern}"
    matches = vair_match_all(text)
    result: dict = {}
    if matches["risk_sources"]:
        best = matches["risk_sources"][0]
        result["source_type"] = best.parent
        result["source_subtypes"] = [m.id for m in matches["risk_sources"]]
    if matches["consequences"]:
        result["consequences"] = [
            RiskConsequence(description=m.label, provenance="vair")
            for m in matches["consequences"]
        ]
    if matches["impacts"]:
        area_matches = matches["impacted_areas"]
        area = area_matches[0].label.lower() if area_matches else None
        result["impacts"] = [
            RiskImpact(description=m.label, area=area, provenance="vair")
            for m in matches["impacts"]
        ]
    return result


def _collect_related_policies(
    risk_id: str,
    mappings: list[PolicyRiskMapping],
) -> list[str]:
    return [
        m.policy_concept
        for m in mappings
        if any(rm.risk_id == risk_id for rm in m.matched_risks)
    ]


_STATUS_MAP = {
    "Ongoing": "ongoing",
    "Concluded": "concluded",
    "Mitigated": "mitigated",
    "Halted": "halted",
    "NearMiss": "near_miss",
}


def _incidents_to_refs(raw_incidents: list[dict] | None) -> list[RiskIncidentRef]:
    if not raw_incidents:
        return []
    return [
        RiskIncidentRef(
            name=inc.get("name", ""),
            description=inc.get("description"),
            source_uri=inc.get("source_uri"),
            status=_STATUS_MAP.get(
                inc.get("hasStatus", ""),
                inc.get("hasStatus", "").lower() if inc.get("hasStatus") else None,
            ),
            provenance="nexus",
        )
        for inc in raw_incidents
    ]


def build_risk_landscape(
    mappings: list[PolicyRiskMapping],
    risk_details_cache: dict[str, dict],
    related_risks: dict[str, list[dict]] | None = None,
    risk_actions: dict[str, list[str]] | None = None,
    risk_incidents: dict[str, list[dict]] | None = None,
    selected_domains: list[str] | None = None,
    model: str = "",
    run_slug: str = "",
    timestamp: str = "",
    policy_profile: PolicyProfile | None = None,
    knowledge_base: KnowledgeBaseRef | None = None,
    coverage_gaps: list[CoverageGap] | None = None,
) -> RiskLandscape:
    related_risks = related_risks or {}
    risk_actions = risk_actions or {}
    risk_incidents = risk_incidents or {}

    seen_risk_ids: set[str] = set()
    risks: list[RiskCard] = []
    framework_counts: dict[str, int] = {}
    weak_matches: list[WeakMatch] = []

    for mapping in mappings:
        for rm in mapping.matched_risks:
            if rm.match_distance is not None and rm.match_distance > WEAK_MATCH_THRESHOLD:
                weak_matches.append(WeakMatch(
                    risk_id=rm.risk_id,
                    policy_concept=mapping.policy_concept,
                    distance=rm.match_distance,
                ))

            if rm.risk_id in seen_risk_ids:
                continue
            seen_risk_ids.add(rm.risk_id)

            details = risk_details_cache.get(rm.risk_id, {})
            framework = _detect_framework(rm.risk_id)
            actions = risk_actions.get(rm.risk_id, [])

            descriptor_raw = details.get("descriptor", [])
            descriptors = descriptor_raw if isinstance(descriptor_raw, list) else (
                [descriptor_raw] if descriptor_raw else []
            )

            description = details.get("description") or ""
            concern = details.get("concern") or ""

            source_type = _infer_source_type(details.get("risk_type"))
            vair = _vair_enrich(description, concern)
            if vair.get("source_type"):
                source_type = vair["source_type"]

            baseline_source = (
                [RiskSource(
                    description=concern or description,
                    source_type=source_type,
                    provenance="heuristic",
                )]
                if concern or description
                else []
            )

            incidents = _incidents_to_refs(risk_incidents.get(rm.risk_id))

            risks.append(RiskCard(
                risk_id=rm.risk_id,
                risk_name=details.get("name") or rm.risk_name or rm.risk_id,
                risk_description=description,
                risk_concern=concern,
                risk_framework=framework,
                cross_mappings=related_risks.get(rm.risk_id, []),
                risk_type=details.get("risk_type"),
                descriptors=descriptors,
                risk_sources=baseline_source,
                consequences=vair.get("consequences", []),
                impacts=vair.get("impacts", []),
                controls=_actions_to_controls(actions),
                related_policies=_collect_related_policies(rm.risk_id, mappings),
                related_actions=actions,
                incidents=incidents,
            ))

            framework_counts[framework] = framework_counts.get(framework, 0) + 1

    policy_source = None
    if policy_profile:
        policy_source = PolicySourceRef(
            organization=policy_profile.organization.name if policy_profile.organization else None,
            domain=policy_profile.domain,
            policy_count=len(policy_profile.policies),
        )

    provenance = GovernanceProvenance(
        produced_by="risk-landscaper",
        governance_function="evaluate",
        aims_activities=["aimsA6"],
        review_status="draft",
    )

    return RiskLandscape(
        model=model,
        timestamp=timestamp,
        run_slug=run_slug,
        selected_domains=selected_domains or [],
        policy_source=policy_source,
        knowledge_base=knowledge_base,
        risks=risks,
        policy_mappings=mappings,
        framework_coverage=framework_counts,
        weak_matches=weak_matches,
        coverage_gaps=coverage_gaps or [],
        provenance=provenance,
    )
