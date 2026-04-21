# Causal Chain Population for RiskCards

Populates the empty causal chain fields (`risk_sources`, `consequences`, `impacts`, `incidents`) on RiskCards using a two-phase approach: free structural enrichment from Nexus data, then LLM-assisted synthesis for primary-relevance risks.

## Context

The RiskCard data model has AIRO-aligned causal chain types (RiskSource, RiskConsequence, RiskImpact, RiskIncidentRef) but they're never populated. The Nexus knowledge graph has rich narrative data (description, concern fields) and incident records, but no structured causal chain data. The design note describes a 3-layer sourcing strategy: Nexus lookup (free), VAIR vocabulary matching (cheap), LLM synthesis (expensive). VAIR vocabulary data isn't available in Nexus, so we combine layers 1 and 3.

## Phase 1: Free Enrichment in `build_landscape`

No LLM calls. Structural inference from existing Nexus data.

### Incident Linking

- Fetch incidents via `nexus.get_related_risk_incidents(risk_id=rid)` in `cli.py` after `map_risks` returns matched risk IDs
- Build `risk_incidents: dict[str, list[dict]]` mapping risk_id → incident data
- Pass to `build_landscape`, map to `RiskIncidentRef` objects on each RiskCard
- Map incident `hasStatus` field to RiskIncidentRef.status (Ongoing, Concluded, Mitigated, Halted, NearMiss → lowercase)

### Source Type Inference

- Map `risk_type` to VAIR-inspired `source_type`:
  - `training-data` → `data`
  - `input` → `data`
  - `output` → `model`
  - `inference` → `model`
  - `non-technical` → `organisational`
  - `agentic` → `model`
- Create a baseline `RiskSource` from risk description + inferred source_type on every RiskCard
- This gives the LLM stage a starting point to refine

### Control Type Inference

- Keyword-based inference from action description text:
  - `detect` type: "detect", "monitor", "audit", "alert", "log", "track", "scan"
  - `evaluate` type: "evaluate", "assess", "benchmark", "test", "measure", "review"
  - `mitigate` type: "mitigate", "reduce", "limit", "filter", "moderate", "constrain"
  - `eliminate` type: "eliminate", "prevent", "prohibit", "block", "remove", "disable"
- First keyword match wins; no match → `None` (status quo)
- Also infer `targets` from keywords: "source"/"data"/"input" → `source`, "output"/"result"/"response" → `consequence`, default → `risk`

## Phase 2: LLM Causal Chain Synthesis (`enrich_chains` stage)

New pipeline stage after `build_landscape`. Runs only on primary-relevance risks.

### Scope

- Filter: only risks that appear as `relevance: "primary"` in any PolicyRiskMapping
- Input per risk: risk_name, risk_description, risk_concern, risk_type, existing risk_sources (from Phase 1), related_policies (policy concepts + definitions)
- Output per risk: refined `risk_sources`, `consequences`, `impacts`, `materialization_conditions`, `risk_level`

### LLM Response Model

Private `_CausalChain` model (no docstrings, per project convention):

```python
class _CausalChainSource(BaseModel):
    description: str
    source_type: Literal["data", "model", "attack", "organisational", "performance"]
    likelihood: Literal["very_low", "low", "medium", "high", "very_high"] | None = None

class _CausalChainConsequence(BaseModel):
    description: str
    likelihood: Literal["very_low", "low", "medium", "high", "very_high"] | None = None
    severity: Literal["very_low", "low", "medium", "high", "very_high"] | None = None

class _CausalChainImpact(BaseModel):
    description: str
    severity: Literal["very_low", "low", "medium", "high", "very_high"] | None = None
    area: str | None = None
    affected_stakeholders: list[str] = []
    harm_type: Literal["representational", "allocative", "quality_of_service", "interpersonal", "societal", "legal"] | None = None

class _CausalChain(BaseModel):
    risk_sources: list[_CausalChainSource]
    consequences: list[_CausalChainConsequence]
    impacts: list[_CausalChainImpact]
    materialization_conditions: str
    risk_level: Literal["very_low", "low", "medium", "high", "very_high"]
```

### Prompt Design

System prompt establishes:
- AIRO causal chain model: RiskSource → Risk → Consequence → Impact
- VAIR source types with examples
- Shelby+ harm taxonomy
- AIRO impact areas (health, safety, fundamental_rights, etc.)
- ISO 31000 likelihood/severity scale

User prompt provides:
- Risk identity (name, description, concern, type)
- Existing source_type hint from Phase 1
- Related policies (concept + definition pairs)
- Instruction to produce the causal chain

### Pipeline Integration

- New file: `stages/enrich_chains.py`
- New prompt templates: `enrich_chains_system.j2`, `enrich_chains_user.j2`
- Called from `cli.py` after `build_landscape`, before writing output
- Modifies `RiskLandscape.risks` in-place (merges LLM output onto existing RiskCard fields)
- Parallel execution with `ThreadPoolExecutor` (respects `config.max_concurrent`)
- Skippable with `--skip-chain-enrichment` CLI flag
- Reports events to RunReport

### Primary Risk Identification

To determine which risks are "primary", collect risk IDs from all PolicyRiskMappings where `relevance == "primary"`. Pass this set to `enrich_chains`. This is computed in `cli.py` from the mappings returned by `map_risks`.

## Files Changed

| File | Change |
|---|---|
| `cli.py` | Fetch incidents after map_risks; call enrich_chains stage; pass incidents to build_landscape |
| `stages/build_landscape.py` | Accept risk_incidents param; populate incidents, source_type, control_type on RiskCards |
| `stages/enrich_chains.py` | New file — LLM causal chain synthesis |
| `templates/prompts/enrich_chains_system.j2` | New — system prompt |
| `templates/prompts/enrich_chains_user.j2` | New — user prompt |
| `tests/test_build_landscape.py` | Tests for incident linking, source_type, control_type inference |
| `tests/test_enrich_chains.py` | New — tests for chain synthesis stage |
| `CHANGELOG.md` | Update |
| `docs/work-tracker.md` | Mark items done |

## What This Does NOT Cover

- VAIR vocabulary matching (no VAIR data available in Nexus)
- Evaluation linking (needs external eval results)
- Risk level computation from chain nodes (risk_level is an assessed judgment, set by LLM)
- Incident severity/likelihood fields (Nexus incidents don't populate these)
