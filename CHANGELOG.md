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
