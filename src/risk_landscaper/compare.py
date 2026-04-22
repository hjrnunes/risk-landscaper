"""Compare multiple RiskLandscapes.

Pure logic -- no LLM calls, no external dependencies.  Takes a list of
(name, RiskLandscape, PolicyProfile) tuples and produces a Comparison.
"""

from collections import Counter
from datetime import datetime, timezone

from risk_landscaper.models import (
    CausalChainStats,
    Comparison,
    LandscapeSummary,
    PolicyProfile,
    RiskLandscape,
    RiskRef,
    SharedRisk,
)


def build_comparison(
    inputs: list[tuple[str, RiskLandscape, PolicyProfile]],
) -> Comparison:
    """Build a Comparison from one or more named landscapes.

    Semantics:
    - "shared" = risk_id appears in 2+ landscapes.
    - "unique" = risk_id appears in exactly 1 landscape.
    - Risk levels of None are bucketed as "unassessed".
    """
    landscapes: list[LandscapeSummary] = []
    risk_sets: dict[str, dict[str, dict]] = {}

    for name, landscape, profile in inputs:
        # Resolve organization name: prefer policy_source, fall back to profile
        org_name = None
        if landscape.policy_source and landscape.policy_source.organization:
            org_name = landscape.policy_source.organization
        elif profile.organization:
            org_name = profile.organization.name

        landscapes.append(LandscapeSummary(
            name=name,
            organization=org_name,
            domain=landscape.selected_domains,
            risk_count=len(landscape.risks),
            policy_count=len(profile.policies),
            timestamp=landscape.timestamp,
        ))

        risk_sets[name] = {
            r.risk_id: {
                "risk_name": r.risk_name,
                "risk_framework": r.risk_framework,
                "risk_level": r.risk_level,
            }
            for r in landscape.risks
        }

    all_names = [name for name, _, _ in inputs]

    # Count how many landscapes each risk_id appears in
    id_counts = Counter(
        rid for rs in risk_sets.values() for rid in rs
    )

    shared_ids = {rid for rid, count in id_counts.items() if count >= 2}
    unique_ids_per = {
        name: {rid for rid in rs if id_counts[rid] == 1}
        for name, rs in risk_sets.items()
    }

    # Build shared risks (sorted by id for determinism)
    shared_risks = []
    for rid in sorted(shared_ids):
        first_info = next(rs[rid] for rs in risk_sets.values() if rid in rs)
        per_landscape = {
            name: risk_sets[name][rid]["risk_level"] if rid in risk_sets[name] else None
            for name in all_names
        }
        shared_risks.append(SharedRisk(
            risk_id=rid,
            risk_name=first_info["risk_name"],
            risk_framework=first_info["risk_framework"],
            per_landscape=per_landscape,
        ))

    # Build unique risks per landscape
    unique_risks: dict[str, list[RiskRef]] = {}
    for name in all_names:
        refs = []
        for rid in sorted(unique_ids_per.get(name, set())):
            info = risk_sets[name][rid]
            refs.append(RiskRef(
                risk_id=rid,
                risk_name=info["risk_name"],
                risk_framework=info["risk_framework"],
                risk_level=info["risk_level"],
            ))
        unique_risks[name] = refs

    # Per-landscape aggregations
    framework_coverage: dict[str, dict[str, int]] = {}
    risk_level_distribution: dict[str, dict[str, int]] = {}
    coverage_gaps = {}
    causal_chain_stats: dict[str, CausalChainStats] = {}

    for name, landscape, _profile in inputs:
        framework_coverage[name] = dict(landscape.framework_coverage)

        level_counts: dict[str, int] = {}
        for r in landscape.risks:
            level = r.risk_level or "unassessed"
            level_counts[level] = level_counts.get(level, 0) + 1
        risk_level_distribution[name] = level_counts

        coverage_gaps[name] = list(landscape.coverage_gaps)

        causal_chain_stats[name] = CausalChainStats(
            sources=sum(len(r.risk_sources) for r in landscape.risks),
            consequences=sum(len(r.consequences) for r in landscape.risks),
            impacts=sum(len(r.impacts) for r in landscape.risks),
            controls=sum(len(r.controls) for r in landscape.risks),
        )

    return Comparison(
        timestamp=datetime.now(timezone.utc).isoformat(),
        landscapes=landscapes,
        shared_risks=shared_risks,
        unique_risks=unique_risks,
        framework_coverage=framework_coverage,
        risk_level_distribution=risk_level_distribution,
        coverage_gaps=coverage_gaps,
        causal_chain_stats=causal_chain_stats,
    )
