from typing import Literal

from risk_landscaper.models import (
    GovernanceProvenance,
    PolicyProfile,
    RiskCard,
    RiskLandscape,
    RunReport,
)

_LEVEL = Literal["very_low", "low", "medium", "high", "very_high"]

_LEVEL_ORD: dict[str, int] = {
    "very_low": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "very_high": 4,
}

_RISK_MATRIX: list[list[_LEVEL]] = [
    # severity ->  very_low    low        medium     high       very_high
    ["very_low",  "very_low", "low",     "low",     "medium"],     # likelihood: very_low
    ["very_low",  "low",      "medium",  "medium",  "high"],       # likelihood: low
    ["low",       "medium",   "medium",  "high",    "high"],       # likelihood: medium
    ["medium",    "medium",   "high",    "high",    "very_high"],  # likelihood: high
    ["medium",    "high",     "high",    "very_high","very_high"], # likelihood: very_high
]


def _max_level(values: list[str | None]) -> str | None:
    valid = [v for v in values if v and v in _LEVEL_ORD]
    if not valid:
        return None
    return max(valid, key=lambda v: _LEVEL_ORD[v])


def compute_risk_level(card: RiskCard) -> str | None:
    likelihoods: list[str | None] = []
    for s in card.risk_sources:
        likelihoods.append(s.likelihood)
    for c in card.consequences:
        likelihoods.append(c.likelihood)

    severities: list[str | None] = []
    for c in card.consequences:
        severities.append(c.severity)
    for i in card.impacts:
        severities.append(i.severity)

    max_likelihood = _max_level(likelihoods)
    max_severity = _max_level(severities)

    if max_likelihood and max_severity:
        li = _LEVEL_ORD[max_likelihood]
        si = _LEVEL_ORD[max_severity]
        return _RISK_MATRIX[li][si]

    if max_severity:
        return max_severity

    return None


def assess_risk_levels(
    landscape: RiskLandscape,
    report: RunReport | None = None,
) -> None:
    computed = 0
    for card in landscape.risks:
        level = compute_risk_level(card)
        if level:
            card.risk_level = level
            computed += 1

    if report:
        report.events.append({
            "stage": "assess",
            "event": "risk_levels_computed",
            "computed": computed,
            "total": len(landscape.risks),
        })


_AIMS_DESCRIPTIONS: dict[str, str] = {
    "aimsA2": "Stakeholder identification",
    "aimsA4": "AI policy establishment",
    "aimsA6": "Risk assessment",
    "aimsA8": "Controls implementation",
    "aimsA9": "Performance evaluation",
}


def compute_aims_coverage(
    profile: PolicyProfile,
    landscape: RiskLandscape,
    report: RunReport | None = None,
) -> list[str]:
    satisfied: list[str] = []

    has_stakeholder_detail = any(
        s.involvement for s in profile.stakeholders
    )
    if has_stakeholder_detail:
        satisfied.append("aimsA2")

    has_governance_function = any(
        p.governance_function for p in profile.policies
    )
    if profile.policies and has_governance_function:
        satisfied.append("aimsA4")

    if landscape.risks:
        satisfied.append("aimsA6")

    has_controls = any(
        card.controls for card in landscape.risks
    )
    if has_controls:
        satisfied.append("aimsA8")

    has_evaluations = any(
        card.evaluations for card in landscape.risks
    )
    if has_evaluations:
        satisfied.append("aimsA9")

    if landscape.provenance:
        landscape.provenance.aims_activities = satisfied
    else:
        landscape.provenance = GovernanceProvenance(
            produced_by="risk-landscaper",
            governance_function="evaluate",
            aims_activities=satisfied,
            review_status="draft",
        )

    for card in landscape.risks:
        card_aims: list[str] = ["aimsA6"]
        if card.controls:
            card_aims.append("aimsA8")
        if card.evaluations:
            card_aims.append("aimsA9")
        card.aims_activities = card_aims

    if report:
        report.events.append({
            "stage": "assess",
            "event": "aims_coverage_computed",
            "satisfied": satisfied,
            "gaps": [k for k in _AIMS_DESCRIPTIONS if k not in satisfied],
        })

    return satisfied
