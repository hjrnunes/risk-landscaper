# Work Tracker

Status of the AIRO Risk Card alignment implementation.

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

- [x] 6-stage pipeline: ingest -> detect_domain -> map_risks -> build_landscape -> enrich_chains -> assess
- [x] `build_landscape` populates risk_type, descriptors, controls (from Nexus actions), related_policies
- [x] `build_landscape` emits GovernanceProvenance on every landscape
- [x] `ingest` extracts governance_function during enrichment pass
- [x] `ingest` extracts PolicyDecomposition (agent/activity/entity) during enrichment
- [x] `nexus_adapter` uses Organization instead of Stakeholder
- [x] `--skip-enrichment`, `--skip-entity-enrichment`, `--skip-chain-enrichment` CLI flags

### HTML Reports

- [x] Ingest report — policy profile visualization
- [x] Risk landscape report — risk cards with causal chain rendering, coverage summary
- [x] Risk Card report — combined profile + landscape view
- [x] Run report — per-stage token usage, collapsible LLM call inspection, event log
- [x] Tailwind + Alpine.js, `__REPORT_DATA__` JSON embedding pattern

### Policy Examples & Battery

- [x] 11 policy files across 6 domains (banking, healthcare, government, corporate, energy, telecom, insurance)
- [x] `run_all_policies.py` — parallel pipeline execution with `-j` flag
- [x] `justfile` — `just run-all` recipe
- [x] 76 parametrized battery tests (format detection, parsing, ingest orchestration, content checks, domain overrides)

### Causal Chain Population

- [x] Source type inference from `risk_type` → VAIR-inspired `source_type`
- [x] Control type inference from action description keywords
- [x] Control targets inference (source/risk/consequence)
- [x] Incident linking via Nexus `get_related_risk_incidents()`
- [x] LLM-assisted causal chain synthesis (primary-relevance risks only)
- [x] Baseline RiskSource creation from risk description + inferred source_type
- [x] VAIR vocabulary matching — full keyword matching from VAIR v1.0 ontology. Sources (22 types), consequences (7 types), impacts (9 types), impacted areas (5 types). Free-layer enrichment in `build_landscape`.

### Ingest Entity Enrichment

- [x] Pass 4: LLM-based entity enrichment for stakeholders, AI systems, organization, and regulations
- [x] AIRO involvement fields on stakeholders (involvement, activity, awareness, output_control, relationship, interests)
- [x] AI system details (modality, techniques, automation_level)
- [x] Organization governance (governance_roles, management_system, certifications, delegates)
- [x] Regulatory reference details (jurisdiction, reference)
- [x] `--skip-entity-enrichment` CLI flag

### Assessment and Scoring

- [x] Risk level computation — 5x5 risk matrix (likelihood x severity) from causal chain data, fallback to max severity
- [x] AIMS coverage analysis — structural inspection of profile + landscape for A2/A4/A6/A8/A9 satisfaction
- [x] Per-card AIMS activity tagging (aimsA6 always, aimsA8 if controls, aimsA9 if evaluations)
- [x] Dynamic `GovernanceProvenance.aims_activities` (replaces hardcoded `["aimsA6"]`)

### Document Conversion

- [x] PDF, DOCX, HTML input support via markitdown (optional `[docs]` extra)
- [x] Auto-detection by file extension in `_load_input()`
- [x] Graceful error when markitdown not installed

### Tests (294 total)

- [x] 19 model tests
- [x] 32 build_landscape tests (risk_type, controls, provenance, incidents, VAIR, source/control inference)
- [x] 21 ingest tests (context, policies, enrichment, entity enrichment, orchestration)
- [x] 35 map_risks tests (search, filtering, gaps, perspectives)
- [x] 10 nexus_adapter tests
- [x] 9 detect_domain tests
- [x] 5 enrich_chains tests
- [x] 20 VAIR vocabulary matching tests
- [x] 76 policy battery tests across 11 example files
- [x] 30 assessment tests (risk matrix, max level, AIMS coverage, per-card tagging, report events)
- [x] 20 serialize tests (JSON-LD structure, VAIR resolution, causal chain, controls, incidents, evaluations, envelope, provenance, turtle, @reverse context, coverage gaps)
- [x] 15 CLI tests (schema export, document conversion, input validation, export subcommand, --format flag)

### Serialization / Interoperability

- [x] JSON-LD serialization — `landscape_to_jsonld()` with AIRO/VAIR/DPV/Nexus ontology mappings (17 tests)
- [x] Turtle output — `landscape_to_turtle()` via optional `rdflib` dependency (`[rdf]` extra)
- [x] `export` subcommand — post-hoc conversion of YAML to JSON-LD or Turtle
- [x] `--format` flag on `run` — additional JSON-LD/Turtle output alongside YAML

### Documentation

- [x] CLAUDE.md — developer guide
- [x] README.md — project overview
- [x] docs/design.md — full design document
- [x] CHANGELOG.md
- [x] docs/work-tracker.md (this file)

## Remaining

### Causal Chain Population

- [ ] **Evaluation linking** — wire `EvaluationRef` population from lm-eval results or other eval sources.

### Interoperability Projections

- [ ] **RiskCard -> Model Card** — project RiskCard fields to model card `considerations` section.
- [ ] **RiskCard -> lm-eval tasks** — generate lm-eval task configs from RiskCard fields.
- [ ] **lm-eval results -> EvaluationRef** — ingest evaluation results back into RiskCards.

### Infrastructure

- [x] **Nexus-mcp dependency** — vendored `RiskIndex`, `build_structural_context`, and `create_tool_handlers` into `nexus.py`. Depends directly on `ai-atlas-nexus` + `chromadb`.
- [x] **VAIR vocabulary data** — provenance documented in `vair.py` (VAIR v1.0, CC-BY-4.0, https://w3id.org/vair).
- [x] **Output format versioning** — `schema` CLI command exports JSON Schema from Pydantic models. Version field on models (`airo_version`, `version`).

### Known Limitations

- **Nexus pre-parsed inputs skip entity enrichment** — when input is a Nexus JSON payload, the CLI bypasses `ingest()` entirely, so entity enrichment (pass 4) never runs. AIRO involvement fields on stakeholders and AI system attributes remain unpopulated. No natural-language document is available to extract from in this path.
