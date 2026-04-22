# src/risk_landscaper/serialize.py
from __future__ import annotations

from risk_landscaper.models import RiskLandscape

JSONLD_CONTEXT = {
    "airo": "https://w3id.org/airo#",
    "vair": "https://w3id.org/vair#",
    "nexus": "https://ibm.github.io/ai-atlas-nexus/ontology/",
    "dpv": "https://w3id.org/dpv#",
    "rl": "https://trustyai.io/risk-landscaper/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}


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
    return node


def landscape_to_jsonld(landscape: RiskLandscape) -> dict:
    doc: dict = {
        "@context": dict(JSONLD_CONTEXT),
        "@id": f"rl:{landscape.run_slug}" if landscape.run_slug else "rl:unnamed",
        "@type": "rl:RiskLandscape",
        "rl:version": landscape.version,
        "rl:hasRiskCard": [_serialize_risk_card(card) for card in landscape.risks],
    }
    return doc
