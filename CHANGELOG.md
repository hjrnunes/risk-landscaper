# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-04-21

AIRO AI Card alignment — evolved the data model and pipeline to produce governance-aware risk artifacts.

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

### Changed

- `nexus_adapter.py` uses `Organization` instead of `Stakeholder` for the org field.
- Ingest enrichment prompt includes `governance_function` and decomposition fields.

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
