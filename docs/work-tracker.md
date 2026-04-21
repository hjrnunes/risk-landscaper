# Work Tracker

Status of the AIRO AI Card alignment implementation.

## Done

### Data Model (v0.2)

- [x] `Organization` type with governance_roles, management_system, certifications, delegates
- [x] `Stakeholder` with AIRO involvement modeling (involvement, activity, awareness, output_control, relationship, interests)
- [x] `AiSystem` with modality, techniques, automation_level, serves_stakeholders, assets
- [x] `Policy` with governance_function, PolicyDecomposition (agent/activity/entity)
- [x] `RiskCard` with causal chain (RiskSource, RiskConsequence, RiskImpact)
- [x] `RiskControl` with control_type and targets
- [x] `RiskIncidentRef` and `EvaluationRef` evidence types
- [x] `GovernanceProvenance` on RiskLandscape
- [x] Backward compatibility: RiskDetail alias, _coerce_organization, _migrate_governed_systems, related_actions preserved

### Pipeline

- [x] `build_landscape` populates risk_type, descriptors, controls (from Nexus actions), related_policies
- [x] `build_landscape` emits GovernanceProvenance on every landscape
- [x] `ingest` extracts governance_function during enrichment pass
- [x] `ingest` extracts PolicyDecomposition (agent/activity/entity) during enrichment
- [x] `nexus_adapter` uses Organization instead of Stakeholder

### Tests

- [x] 19 model tests covering all new types
- [x] 5 build_landscape tests (risk_type, controls, related_policies, provenance, descriptor coercion)
- [x] Ingest tests updated for governance_function and decomposition
- [x] All 104 tests passing

### Documentation

- [x] CLAUDE.md — developer guide
- [x] README.md — project overview
- [x] docs/design.md — full design document
- [x] CHANGELOG.md
- [x] docs/work-tracker.md (this file)

## Remaining

### Causal Chain Population

- [ ] **VAIR vocabulary matching** — map risk descriptions against VAIR enumerated source/consequence/impact types. Structured labels, no LLM calls.
- [ ] **LLM-assisted chain synthesis** — given risk description + concern + policy context, generate RiskSource, RiskConsequence, RiskImpact with proper VAIR types.
- [ ] **Incident linking** — use Nexus `get_related_risk_incidents()` to populate `RiskCard.incidents` with `RiskIncidentRef` objects.
- [ ] **Evaluation linking** — wire `EvaluationRef` population from lm-eval results or other eval sources.

### Control Enrichment

- [ ] **Control type inference** — infer `control_type` (detect/evaluate/mitigate/eliminate) from action description text (currently defaults to None).
- [ ] **Control targets** — infer which chain level each control targets (source/risk/consequence/impact).

### Ingest Enrichment

- [ ] **Stakeholder extraction** — extract AIRO involvement fields (involvement, activity, awareness, output_control) from document text.
- [ ] **AiSystem extraction** — extract modality, techniques, automation_level from document text.
- [ ] **Organization governance** — extract governance_roles, management_system, certifications.
- [ ] **Regulatory references** — extract jurisdiction, authority, compliance_status from document text.

### Interoperability Projections

- [ ] **RiskCard -> Model Card** — project RiskCard fields to model card `considerations` section.
- [ ] **RiskCard -> lm-eval tasks** — generate lm-eval task configs from RiskCard fields.
- [ ] **lm-eval results -> EvaluationRef** — ingest evaluation results back into RiskCards.

### Assessment and Scoring

- [ ] **Risk level computation** — derive risk_level from likelihood/severity across the causal chain (currently set manually or left empty).
- [ ] **Coverage analysis** — identify which AIMS activities are satisfied vs gaps.

### Infrastructure

- [ ] **Nexus-mcp dependency** — currently uses `path = "../taxonomy-refiner/nexus-mcp"`. Needs to be published or vendored for standalone use.
- [ ] **VAIR vocabulary data** — source and package VAIR type enumerations for matching.
- [ ] **Output format versioning** — version field on risk-landscape.yaml for schema evolution.
