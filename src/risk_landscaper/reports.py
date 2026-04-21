"""HTML report builders for pipeline artifacts."""

import json
from pathlib import Path

from risk_landscaper.models import PolicyProfile, RiskLandscape, RunReport

TEMPLATE_DIR = Path(__file__).parent / "templates"

_AIRO_ROLES = {"airo:AIUser", "airo:AISubject", "airo:AIProvider", "airo:AIDeployer"}


def _render(template_name: str, data: dict | list, output_path: Path) -> Path:
    html = (TEMPLATE_DIR / template_name).read_text().replace(
        "__REPORT_DATA__", json.dumps(data, default=str)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    return output_path


def build_risk_landscape_report(data: dict, output_path: Path) -> Path:
    return _render("risk_landscape_report_template.html", data, output_path)


def build_run_report_html(data: dict, output_path: Path) -> Path:
    return _render("run_report_template.html", data, output_path)


def build_ai_card_report(
    profile: PolicyProfile,
    landscape: RiskLandscape,
    output_path: Path,
) -> Path:
    data = {
        "profile": profile.model_dump(),
        "landscape": landscape.model_dump(),
    }
    return _render("ai_card_template.html", data, output_path)


# ---- Ingest report ----

def _context_confidence(doc: PolicyProfile) -> dict:
    ctx = {}
    ctx["organization"] = "green" if doc.organization and doc.organization.name else "red"
    ctx["domain"] = "green" if doc.domain else "red"
    ctx["purpose"] = "green" if doc.purpose else "red"
    ctx["ai_systems"] = "green" if doc.ai_systems else "red"

    if not doc.stakeholders:
        ctx["stakeholders"] = "red"
    else:
        has_governance = any(
            role and role not in _AIRO_ROLES
            for s in doc.stakeholders
            for role in s.roles
        )
        ctx["stakeholders"] = "green" if has_governance else "amber"

    if not doc.regulations:
        ctx["regulations"] = "red"
    else:
        all_complete = all(r.jurisdiction or r.reference for r in doc.regulations)
        ctx["regulations"] = "green" if all_complete else "amber"

    return ctx


def _policy_confidence(doc: PolicyProfile) -> list[dict]:
    results = []
    for p in doc.policies:
        pc = {"policy_concept": p.policy_concept}
        pc["boundary_examples"] = "green" if p.boundary_examples else "red"
        pc["acceptable_uses"] = "green" if p.acceptable_uses else "amber"
        pc["risk_controls"] = "green" if p.risk_controls else "amber"
        pc["human_involvement"] = "green" if p.human_involvement else "amber"

        if p.decomposition is None:
            pc["decomposition"] = "red"
        else:
            filled = sum(1 for f in [p.decomposition.agent, p.decomposition.activity, p.decomposition.entity] if f)
            if filled == 3:
                pc["decomposition"] = "green"
            elif filled >= 1:
                pc["decomposition"] = "amber"
            else:
                pc["decomposition"] = "red"

        results.append(pc)
    return results


def group_stakeholders(doc: PolicyProfile) -> dict:
    result = {
        "organisation": {"name": doc.organization.name} if doc.organization and doc.organization.name else None,
        "governance": [],
        "users": [],
        "subjects": [],
    }

    for s in doc.stakeholders:
        roles_set = set(s.roles)
        non_airo = {r for r in roles_set if r} - _AIRO_ROLES
        if non_airo:
            result["governance"].append({"name": s.name, "roles": s.roles})
        elif "airo:AISubject" in roles_set:
            result["subjects"].append({"name": s.name, "roles": s.roles})
        elif "airo:AIUser" in roles_set:
            result["users"].append({"name": s.name, "roles": s.roles})

    return result


def _summary(doc: PolicyProfile, report: RunReport) -> dict:
    policies_enriched = sum(
        1 for p in doc.policies if p.boundary_examples or p.acceptable_uses or p.risk_controls
    )
    boundary_pairs_total = sum(len(p.boundary_examples) for p in doc.policies)
    policies_with_zero_pairs = sum(1 for p in doc.policies if not p.boundary_examples)

    weak_inferences = []
    for ev in report.events:
        if ev.get("event") == "context_weak_inference":
            weak_inferences.extend(ev.get("missing_fields", []))

    return {
        "policies_total": len(doc.policies),
        "policies_enriched": policies_enriched,
        "boundary_pairs_total": boundary_pairs_total,
        "policies_with_zero_pairs": policies_with_zero_pairs,
        "weak_inferences": weak_inferences,
    }


def build_ingest_report_data(
    doc: PolicyProfile,
    report: RunReport,
    meta: dict,
) -> dict:
    return {
        "meta": meta,
        "profile": doc.model_dump(),
        "stakeholder_groups": group_stakeholders(doc),
        "confidence": {
            "context": _context_confidence(doc),
            "policies": _policy_confidence(doc),
            "summary": _summary(doc, report),
        },
    }


def build_ingest_report(
    doc: PolicyProfile,
    report: RunReport,
    output_path: Path,
    meta: dict,
) -> Path:
    data = build_ingest_report_data(doc, report, meta)
    return _render("ingest_report_template.html", data, output_path)
