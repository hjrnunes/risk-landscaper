# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **`source_documents` provenance field** — `list[str]` field on `Policy` and `PolicyProfile` (defaults to `[]`) for tracking which input documents contributed each policy and the overall profile. Backward compatible with existing serialized data.
- **JSON-LD serialization** — `serialize.py` module exports RiskLandscape to JSON-LD with AIRO/VAIR/DPV/Nexus ontology mappings. `landscape_to_jsonld()` produces valid JSON-LD with `@context` (including `@reverse` annotations for correct RDF directionality) and structured RiskCard nodes. Complete causal chain serialization: risk sources (with VAIR type mapping), consequences, impacts (with harm types and impacted areas), typed controls (AIRO property mapping), incidents (`rl:hasIncident`), evaluations (`rl:Evaluation`), coverage gaps (`rl:coverageGap`), envelope metadata, and governance provenance. Composable with AIROO advisory data foundation triples via shared `nexus:` identifiers. 20 tests.
- **Turtle serialization** — `landscape_to_turtle()` converts RiskLandscape to RDF Turtle format via optional `rdflib` dependency. Optional `[rdf]` extra (`pip install 'risk-landscaper[rdf]'`). Raises helpful ImportError when rdflib not installed.
- **Export subcommand** — `risk-landscaper export` CLI command converts existing risk landscape YAML files to JSON-LD or Turtle format. `--format` flag defaults to `jsonld`, also supports `turtle`. Outputs to `risk-landscape.jsonld` or `risk-landscape.ttl` in the specified directory.
- **`--format` flag on `run`** — `risk-landscaper run --format jsonld` or `--format turtle` writes additional serialization alongside YAML output.

## [0.2.0] - 2026-04-21

AIRO Risk Card alignment — evolved the data model and pipeline to produce governance-aware risk artifacts.

### Added

- **AIRO-aligned data model** — `RiskCard` replaces `RiskDetail` with full causal chain (`RiskSource`, `RiskConsequence`, `RiskImpact`), typed `RiskControl`s, evidence references (`RiskIncidentRef`, `EvaluationRef`), and governance metadata (`GovernanceProvenance`).
- **Organization type** — dedicated model for the disclosing entity, distinct from `Stakeholder`. Validator `_coerce_organization` handles legacy Stakeholder-shaped dicts.
- **Enriched Stakeholder** — AIRO involvement modeling: `involvement`, `activity`, `awareness`, `output_control`, `relationship`, `interests`.
- **Enriched AiSystem** — `modality`, `techniques`, `automation_level`, `serves_stakeholders`, `assets`.
- **Policy governance_function** — `direct`, `evaluate`, or `monitor` (Lewis et al ISO/IEC 38500). Extracted during ingest enrichment pass.
- **PolicyDecomposition** — `agent`/`activity`/`entity` triple extracted from policy text.
- **build_landscape enrichment** — populates `risk_type`, `descriptors`, `controls` (from Nexus actions), and `related_policies` (back-linked from mappings) on each RiskCard.
- **GovernanceProvenance** on every RiskLandscape — `produced_by`, `governance_function`, `aims_activities`, `review_status`.
- **Backward compatibility** — `RiskDetail = RiskCard` alias, `GovernedSystem = AiSystem` alias, `related_actions` preserved, `_migrate_governed_systems` validator, all new fields default to `None`/`[]`.
- 19 model tests, 5 build_landscape tests, updated ingest tests.
- **Policy examples** — 11 real policy files across 6 domains (banking, healthcare, government, corporate, energy, telecom, insurance) in `policy_examples/`.
- **Test battery** — 76 parametrized tests exercising format detection, JSON/nexus parsing, ingest orchestration, content checks, and domain overrides against all policy examples.
- **run_all_policies.py** — script to run the pipeline against every policy example in parallel, outputs to `runs/`. `-j` flag controls concurrency (defaults to CPU count).
- **justfile** — `just run-all <base_url> <model>` recipe.
- **HTML reports** — self-contained ingest, risk landscape, and run reports generated alongside YAML/JSON artifacts. Ported from taxonomy-refiner. Tailwind + Alpine.js, `__REPORT_DATA__` JSON embedding pattern.
- **Causal chain population** — RiskCards now populated with `risk_sources`, `consequences`, `impacts`, and `incidents`.
  - Incident linking from AI Atlas Nexus knowledge graph (`get_related_risk_incidents`).
  - Source type inference from `risk_type` → VAIR vocabulary (`data`, `model`, `attack`, `organisational`, `performance`).
  - VAIR v1.0 keyword matching — free-layer enrichment of consequences (7 types) and impacts (9 types) from risk description/concern text, no LLM calls.
  - Control type and targets inference from action description keywords.
  - LLM-assisted causal chain synthesis for primary-relevance risks (new `enrich_chains` pipeline stage). Skippable with `--skip-chain-enrichment`.
- **Causal chain in reports** — risk landscape report and Risk Card now render the full causal chain per risk: risk sources (with VAIR source type), consequences, impacts (with area and severity), typed controls (with targets), and linked incidents (with status and source URI). Collapsed preview badges show enrichment counts at a glance. New "Causal Chain Coverage" summary section in the risk landscape report.
- **Run report event log** — full LLM call capture (prompts, responses, duration) in the event log. Stage timing for all pipeline stages. Rewritten run report template with per-stage token usage breakdown, collapsible LLM call inspection, and event rendering for all risk-landscaper stages (ingest, detect_domain, map_risks, build_landscape, enrich_chains).
- **Entity enrichment (ingest pass 4)** — dedicated LLM pass enriches extracted entities with AIRO-grounded attributes. Stakeholders gain involvement, activity, awareness, output_control, relationship, and interests. AI systems gain modality, techniques, and automation_level. Organization gains governance_roles, management_system, certifications, and delegates. Regulatory references gain jurisdiction and reference. Skippable with `--skip-entity-enrichment`.
- **Assessment stage** — new post-pipeline stage computes risk levels and AIMS coverage without LLM calls.
  - Risk level computation: 5x5 risk matrix (likelihood x severity) applied to causal chain data. Falls back to max severity when no likelihood is available.
  - AIMS coverage analysis: inspects profile and landscape to determine which ISO/IEC 42001 AIMS activities are satisfied (A2 stakeholders, A4 policies, A6 risk assessment, A8 controls, A9 evaluations). Updates `GovernanceProvenance.aims_activities` dynamically and tags individual RiskCards.

- **JSON Schema export** — `risk-landscaper schema` CLI command exports JSON Schema for `PolicyProfile` and `RiskLandscape` output formats. Enables downstream tooling to validate outputs and track schema evolution.
- **VAIR provenance documentation** — `vair.py` module docstring documents the source ontology (VAIR v1.0, CC-BY-4.0, https://w3id.org/vair), authorship, and the boundary between ontology-derived types and project-specific keywords.
- **Vendored nexus-mcp** — `RiskIndex`, `build_structural_context`, and `create_tool_handlers` extracted into `nexus.py`. Removed `nexus-mcp` path dependency; depends directly on `ai-atlas-nexus` (git) + `chromadb`.
- **Document conversion** — PDF, DOCX, HTML input support via [markitdown](https://github.com/microsoft/markitdown). Optional `[docs]` extra (`pip install 'risk-landscaper[docs]'`). Auto-detected by file extension, converted to markdown before ingest.
- **Data provenance tracking** — `provenance` field (`nexus`, `vair`, `heuristic`, `llm`) on causal chain items (`RiskSource`, `RiskConsequence`, `RiskImpact`, `RiskControl`, `RiskIncidentRef`). Tagged at creation time in `build_landscape` and `enrich_chains`. Rendered as color-coded badges in risk landscape and Risk Card reports with legend.
- **Document chunking** — large documents that exceed the model context window are automatically split by markdown sections and processed in chunks. `--max-context` CLI option sets the model's context window size to enable chunking. Policies are deduplicated across chunks; enrichments are merged.
- **Frontier safety policies** — 24 policy documents (18 PDFs + 2 markdown) from 12 organizations (Anthropic, OpenAI, DeepMind, Meta, Microsoft, xAI, NVIDIA, Amazon, G42, Cohere, NAVER, Magic) in `policy_examples/frontier_safety/`.
- **Battery script subdirectory support** — `run_all_policies.py` gains `-d` flag to target a subdirectory of `policy_examples/`, with `just run-frontier` recipe for frontier safety policies. Uses `rglob` to discover files recursively.

### Changed

- `nexus_adapter.py` uses `Organization` instead of `Stakeholder` for the org field.
- Ingest enrichment prompt includes `governance_function` and decomposition fields.
- Project version bumped to 0.2.0.

## [0.1.0] - 2026-04-21

Initial extraction from `taxonomy-refiner/risk-landscaper/`.

### Added

- 4-stage pipeline: ingest -> detect_domain -> map_risks -> build_landscape.
- 3-pass LLM ingest: context extraction, policy extraction, policy enrichment.
- Perspective-based semantic search against AI Atlas Nexus (600+ risks, 10 frameworks).
- LLM-based relevance selection with coverage gap detection.
- Typer CLI with `run` command.
- Instructor-based structured LLM output.
- Jinja2 prompt templates with chain-of-thought examples.
- Per-call debug logging.
- 104 tests passing.
