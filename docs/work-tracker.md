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

### Causal Chain Population

- [x] Source type inference from `risk_type` → VAIR-inspired `source_type`
- [x] Control type inference from action description keywords
- [x] Control targets inference (source/risk/consequence)
- [x] Incident linking via Nexus `get_related_risk_incidents()`
- [x] LLM-assisted causal chain synthesis (primary-relevance risks only)
- [x] Baseline RiskSource creation from risk description + inferred source_type

### Tests

- [x] 19 model tests covering all new types
- [x] 5 build_landscape tests (risk_type, controls, related_policies, provenance, descriptor coercion)
- [x] Ingest tests updated for governance_function and decomposition
- [x] All 104 tests passing
- [x] 8 control type/targets inference tests
- [x] 9 source type inference + incident linking tests
- [x] 5 enrich_chains tests (primary filtering, policy context, merge, skip non-primary)
- [x] 20 VAIR vocabulary matching tests (risk sources, consequences, impacts, impacted areas)
- [x] 2 VAIR integration tests in build_landscape

### Documentation

- [x] CLAUDE.md — developer guide
- [x] README.md — project overview
- [x] docs/design.md — full design document
- [x] CHANGELOG.md
- [x] docs/work-tracker.md (this file)

## Remaining

### Causal Chain Population

- [x] **VAIR vocabulary matching** — full keyword matching from VAIR v1.0 ontology. Sources (22 types), consequences (7 types), impacts (9 types), impacted areas (5 types). Free-layer enrichment in `build_landscape`.
- [x] **LLM-assisted chain synthesis** — `enrich_chains` stage for primary-relevance risks.
- [x] **Incident linking** — `get_related_risk_incidents()` wired into `build_landscape`.
- [ ] **Evaluation linking** — wire `EvaluationRef` population from lm-eval results or other eval sources.

### Control Enrichment

- [x] **Control type inference** — keyword-based from action description text.
- [x] **Control targets** — inferred from action keywords (source/risk/consequence).

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
