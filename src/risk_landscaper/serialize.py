# src/risk_landscaper/serialize.py
from __future__ import annotations

from risk_landscaper.models import RiskLandscape
from risk_landscaper.vair import RISK_SOURCES, CONSEQUENCES, IMPACTS, IMPACTED_AREAS

JSONLD_CONTEXT = {
    "airo": "https://w3id.org/airo#",
    "vair": "https://w3id.org/vair#",
    "nexus": "https://ibm.github.io/ai-atlas-nexus/ontology/",
    "dpv": "https://w3id.org/dpv#",
    "rl": "https://trustyai.io/risk-landscaper/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}

SOURCE_TYPE_TO_VAIR = {
    "attack": "vair:Attack",
    "data": "vair:DataRiskSource",
    "organisational": "vair:OrganisationalRiskSource",
    "performance": "vair:PerformanceRiskSource",
    "system": "vair:SystemRiskSource",
}

CONTROL_TYPE_TO_IRI = {
    "detect": "airo:detectsRiskConcept",
    "evaluate": "rl:evaluatesRiskConcept",
    "mitigate": "airo:mitigatesRiskConcept",
    "eliminate": "airo:eliminatesRiskConcept",
}

_VAIR_IDS = {t.id for t in RISK_SOURCES + CONSEQUENCES + IMPACTS + IMPACTED_AREAS}
_IMPACTED_AREA_IDS = {t.id for t in IMPACTED_AREAS}


def _vair_iri(value: str) -> str | None:
    if value in _VAIR_IDS:
        return f"vair:{value}"
    return None


def _serialize_risk_source(src) -> dict:
    types: list[str] = ["airo:RiskSource"]
    if src.source_type:
        vair = SOURCE_TYPE_TO_VAIR.get(src.source_type) or _vair_iri(src.source_type)
        if vair:
            types.append(vair)
    node: dict = {"@type": types if len(types) > 1 else types[0], "rdfs:comment": src.description}
    if src.likelihood:
        node["airo:hasLikelihood"] = src.likelihood
    if src.exploits_vulnerability:
        node["rl:exploitsVulnerability"] = src.exploits_vulnerability
    return node


def _serialize_consequence(cons) -> dict:
    node: dict = {"@type": "airo:Consequence", "rdfs:comment": cons.description}
    if cons.likelihood:
        node["airo:hasLikelihood"] = cons.likelihood
    if cons.severity:
        node["airo:hasSeverity"] = cons.severity
    return node


def _serialize_impact(imp) -> dict:
    types: list[str] = ["airo:Impact"]
    if imp.harm_type:
        vair = _vair_iri(imp.harm_type)
        if vair:
            types.append(vair)
    node: dict = {"@type": types if len(types) > 1 else types[0], "rdfs:comment": imp.description}
    if imp.severity:
        node["airo:hasSeverity"] = imp.severity
    if imp.area:
        area_iri = _vair_iri(imp.area)
        node["airo:hasImpactOnArea"] = area_iri if area_iri else imp.area
    if imp.affected_stakeholders:
        node["airo:hasImpactOnStakeholder"] = imp.affected_stakeholders
    return node


def _serialize_control(ctrl) -> dict:
    node: dict = {"@type": "airo:RiskControl", "rdfs:comment": ctrl.description}
    if ctrl.control_type:
        iri = CONTROL_TYPE_TO_IRI.get(ctrl.control_type)
        if iri:
            node["rl:controlFunction"] = iri
    if ctrl.targets:
        node["rl:controlTargets"] = ctrl.targets
    return node


def _serialize_incident(inc) -> dict:
    node: dict = {"@type": "dpv:Incident", "rdfs:label": inc.name}
    if inc.description:
        node["rdfs:comment"] = inc.description
    if inc.source_uri:
        node["rdfs:seeAlso"] = inc.source_uri
    if inc.status:
        node["rl:incidentStatus"] = inc.status
    return node


def _serialize_evaluation(ev) -> dict:
    node: dict = {"@type": "rl:Evaluation", "@id": ev.eval_id}
    if ev.eval_type:
        node["rl:evalType"] = ev.eval_type
    if ev.summary:
        node["rdfs:comment"] = ev.summary
    if ev.metrics:
        node["rl:metrics"] = ev.metrics
    if ev.source_uri:
        node["rdfs:seeAlso"] = ev.source_uri
    if ev.timestamp:
        node["rl:timestamp"] = ev.timestamp
    return node


def _serialize_provenance(prov) -> dict:
    node: dict = {}
    if prov.produced_by:
        node["rl:producedBy"] = prov.produced_by
    if prov.governance_function:
        node["rl:governanceFunction"] = prov.governance_function
    if prov.aims_activities:
        node["rl:aimsActivity"] = prov.aims_activities
    if prov.reviewed_by:
        node["rl:reviewedBy"] = prov.reviewed_by
    if prov.review_status:
        node["rl:reviewStatus"] = prov.review_status
    return node


def _serialize_risk_card(card) -> dict:
    node: dict = {
        "@id": f"nexus:{card.risk_id}",
        "@type": "airo:Risk",
        "rdfs:label": card.risk_name,
    }
    if card.risk_description:
        node["rdfs:comment"] = card.risk_description
    if card.risk_concern:
        node["rl:riskConcern"] = card.risk_concern
    if card.risk_framework:
        node["rl:riskFramework"] = card.risk_framework
    if card.cross_mappings:
        node["rl:crossMapping"] = card.cross_mappings
    if card.risk_type:
        node["rl:riskType"] = card.risk_type
    if card.descriptors:
        node["rl:descriptor"] = card.descriptors
    if card.trustworthy_characteristics:
        node["rl:trustworthyCharacteristic"] = card.trustworthy_characteristics
    if card.aims_activities:
        node["rl:aimsActivity"] = card.aims_activities
    if card.materialization_conditions:
        node["rl:materializationConditions"] = card.materialization_conditions
    if card.risk_level:
        node["rl:riskLevel"] = card.risk_level
    if card.related_policies:
        node["rl:relatedPolicy"] = card.related_policies
    if card.risk_sources:
        node["airo:isRiskSourceFor"] = [_serialize_risk_source(s) for s in card.risk_sources]
    if card.consequences:
        node["airo:hasConsequence"] = [_serialize_consequence(c) for c in card.consequences]
    if card.impacts:
        node["airo:hasImpact"] = [_serialize_impact(i) for i in card.impacts]
    if card.controls:
        node["airo:modifiesRiskConcept"] = [_serialize_control(c) for c in card.controls]
    if card.incidents:
        node["dpv:Incident"] = [_serialize_incident(i) for i in card.incidents]
    if card.evaluations:
        node["rl:evaluation"] = [_serialize_evaluation(e) for e in card.evaluations]
    return node


def landscape_to_jsonld(landscape: RiskLandscape) -> dict:
    doc: dict = {
        "@context": dict(JSONLD_CONTEXT),
        "@id": f"rl:{landscape.run_slug}" if landscape.run_slug else "rl:unnamed",
        "@type": "rl:RiskLandscape",
        "rl:version": landscape.version,
        "rl:hasRiskCard": [_serialize_risk_card(card) for card in landscape.risks],
    }
    if landscape.timestamp:
        doc["rl:timestamp"] = landscape.timestamp
    if landscape.model:
        doc["rl:model"] = landscape.model
    if landscape.selected_domains:
        doc["rl:selectedDomains"] = landscape.selected_domains
    if landscape.framework_coverage:
        doc["rl:frameworkCoverage"] = landscape.framework_coverage
    if landscape.policy_source:
        doc["rl:policySource"] = {
            k: v for k, v in landscape.policy_source.model_dump().items() if v
        }
    if landscape.knowledge_base:
        kb = landscape.knowledge_base.model_dump()
        doc["rl:knowledgeBase"] = {k: v for k, v in kb.items() if v}
    if landscape.provenance:
        doc["rl:provenance"] = _serialize_provenance(landscape.provenance)
    return doc
