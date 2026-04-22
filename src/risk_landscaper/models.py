from typing import Any, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, field_validator, model_validator


class BoundaryExample(BaseModel):
    prohibited: str
    acceptable: str


class NamedEntity(BaseModel):
    name: str
    role: str


# --- AIRO-grounded envelope types ---


class Organization(BaseModel):
    name: str
    description: str | None = None
    governance_roles: list[str] = []
    management_system: str | None = None
    certifications: list[str] = []
    delegates: list[str] = []


class Stakeholder(BaseModel):
    name: str
    roles: list[str] = []
    description: str | None = None
    involvement: Literal["intended", "unintended"] | None = None
    activity: Literal["active", "passive"] | None = None
    awareness: Literal["informed", "uninformed"] | None = None
    output_control: Literal["challenge", "correct", "cannot_opt_out"] | None = None
    relationship: Literal["internal", "external"] | None = None
    interests: list[str] = []


class AiSystem(BaseModel):
    name: str
    description: str | None = None
    purpose: list[str] = []
    risk_level: Literal["high", "limited", "minimal", "unclassified"] | None = None
    modality: str | None = None
    techniques: list[str] = []
    automation_level: str | None = None
    serves_stakeholders: list[str] = []
    assets: list[str] = []


GovernedSystem = AiSystem


class RegulatoryReference(BaseModel):
    name: str
    jurisdiction: str | None = None
    reference: str | None = None


# --- Per-policy decomposition ---


class PolicyDecomposition(BaseModel):
    agent: str | None = None
    activity: str | None = None
    entity: str | None = None


class Policy(BaseModel):
    policy_concept: str
    concept_definition: str
    governance_function: Literal["direct", "evaluate", "monitor"] | None = None
    boundary_examples: list[BoundaryExample] = []
    acceptable_uses: list[str] = []
    risk_controls: list[str] = []
    human_involvement: str | None = None
    affects_stakeholders: list[str] = []
    applies_to_systems: list[str] = []
    decomposition: PolicyDecomposition | None = None


class PolicyProfile(BaseModel):
    airo_version: str = "0.2"
    organization: Organization | None = None
    domain: str | None = None
    purpose: list[str] = []
    ai_systems: list[AiSystem] = []
    stakeholders: list[Stakeholder] = []
    regulations: list[RegulatoryReference] = []
    policies: list[Policy] = []

    @field_validator("organization", mode="before")
    @classmethod
    def _coerce_organization(cls, v):
        if isinstance(v, str):
            return Organization(name=v) if v else None
        if isinstance(v, dict) and "roles" in v:
            return Organization(name=v.get("name", ""))
        return v

    @model_validator(mode="before")
    @classmethod
    def _migrate_governed_systems(cls, data):
        if isinstance(data, dict) and "governed_systems" in data and "ai_systems" not in data:
            data["ai_systems"] = data.pop("governed_systems")
        return data


# --- Causal chain types ---


class RiskSource(BaseModel):
    description: str
    source_type: str | None = None
    likelihood: str | None = None
    exploits_vulnerability: str | None = None
    provenance: Literal["nexus", "vair", "heuristic", "llm"] | None = None


class RiskConsequence(BaseModel):
    description: str
    likelihood: str | None = None
    severity: str | None = None
    provenance: Literal["nexus", "vair", "heuristic", "llm"] | None = None


class RiskImpact(BaseModel):
    description: str
    severity: str | None = None
    area: str | None = None
    affected_stakeholders: list[str] = []
    harm_type: str | None = None
    provenance: Literal["nexus", "vair", "heuristic", "llm"] | None = None


class RiskControl(BaseModel):
    description: str
    control_type: Literal["detect", "evaluate", "mitigate", "eliminate"] | None = None
    targets: str | None = None
    provenance: Literal["nexus", "vair", "heuristic", "llm"] | None = None


class RiskIncidentRef(BaseModel):
    name: str
    description: str | None = None
    source_uri: str | None = None
    status: str | None = None
    provenance: Literal["nexus", "vair", "heuristic", "llm"] | None = None


class EvaluationRef(BaseModel):
    eval_id: str
    eval_type: str | None = None
    timestamp: str | None = None
    summary: str | None = None
    metrics: dict[str, Any] = {}
    source_uri: str | None = None


class GovernanceProvenance(BaseModel):
    produced_by: str | None = None
    governance_function: str | None = None
    aims_activities: list[str] = []
    reviewed_by: list[str] = []
    review_status: str | None = None


# --- Risk matching ---


class RiskMatch(BaseModel):
    risk_id: str
    risk_name: str
    relevance: Literal["primary", "supporting", "tangential"]
    justification: str
    match_distance: float | None = None


class PolicyRiskMapping(BaseModel):
    policy_concept: str
    matched_risks: list[RiskMatch]


class PolicySourceRef(BaseModel):
    organization: str | None = None
    domain: str | None = None
    policy_count: int = 0


class KnowledgeBaseRef(BaseModel):
    nexus_commit: str = ""
    nexus_risk_count: int = 0
    ontology_index_hash: str = ""
    ontology_domains: dict[str, int] = {}
    indexed_at: str = ""


# --- Risk card ---


class RiskCard(BaseModel):
    risk_id: str
    risk_name: str
    risk_description: str | None = ""
    risk_concern: str | None = ""
    risk_framework: str | None = ""
    cross_mappings: list[dict] = []
    risk_type: str | None = None
    descriptors: list[str] = []

    risk_sources: list[RiskSource] = []
    consequences: list[RiskConsequence] = []
    impacts: list[RiskImpact] = []

    trustworthy_characteristics: list[str] = []
    aims_activities: list[str] = []

    controls: list[RiskControl] = []

    materialization_conditions: str | None = None

    incidents: list[RiskIncidentRef] = []

    evaluations: list[EvaluationRef] = []

    risk_level: str | None = None

    related_policies: list[str] = []

    related_actions: list[str] = []


RiskDetail = RiskCard


class WeakMatch(BaseModel):
    risk_id: str
    policy_concept: str
    distance: float


class CoverageGap(BaseModel):
    policy_concept: str
    concept_definition: str
    gap_type: Literal["domain_specialization", "compositional", "novel"]
    confidence: float
    nearest_risks: list[dict]
    reasoning: str
    decomposition: PolicyDecomposition | None = None


class RiskLandscape(BaseModel):
    version: str = "0.2"
    model: str = ""
    timestamp: str = ""
    run_slug: str = ""
    selected_domains: list[str] = []
    policy_source: PolicySourceRef | None = None
    knowledge_base: KnowledgeBaseRef | None = None
    risks: list[RiskCard] = []
    policy_mappings: list[PolicyRiskMapping] = []
    framework_coverage: dict[str, int] = {}
    weak_matches: list[WeakMatch] = []
    coverage_gaps: list[CoverageGap] = []
    provenance: GovernanceProvenance | None = None


@dataclass
class RunReport:
    model: str
    policy_set: str
    timestamp: str
    stages_completed: list[str] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    token_usage: dict | None = None

    def to_dict(self) -> dict:
        d = {
            "model": self.model,
            "policy_set": self.policy_set,
            "timestamp": self.timestamp,
            "stages_completed": self.stages_completed,
            "events": self.events,
        }
        if self.token_usage:
            d["token_usage"] = self.token_usage
        return d
