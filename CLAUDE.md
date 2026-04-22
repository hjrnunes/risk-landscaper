# Risk Landscaper

AIRO-aligned AI risk documentation tool. Produces structured risk artifacts (PolicyProfile + RiskLandscape with RiskCards) from policy documents and the AI Atlas Nexus knowledge graph.

Extracted from `taxonomy-refiner/risk-landscaper/`. The refiner downstream has its own copy of models at `refiner/src/refiner/models.py` and reads `risk-landscape.yaml` — backward compatibility matters.

## Directory Structure

```
src/risk_landscaper/
  cli.py                 # Typer CLI: `risk-landscaper run`
  models.py              # Pydantic data model (v0.2, AIRO-aligned)
  llm.py                 # LLM client config, token tracking
  debug.py               # Per-call debug logging
  prompts.py             # Jinja2 prompt rendering
  reports.py             # HTML report generation (ingest, landscape, AI card, run)
  nexus.py               # Vendored risk index + query handlers (from nexus-mcp)
  nexus_adapter.py       # Nexus payload -> PolicyProfile projection
  vair.py                # VAIR v1.0 vocabulary matching for causal chains
  stages/
    ingest.py            # 4-pass LLM: context -> policies -> enrichment -> entity enrichment
    detect_domain.py     # Domain menu normalization + LLM fallback
    map_risks.py         # Perspective-based search + LLM selection + gap detection
    build_landscape.py   # Assemble RiskLandscape from mappings + Nexus data
    enrich_chains.py     # LLM-assisted causal chain synthesis for primary risks
    assess.py            # Risk level computation + AIMS coverage analysis (no LLM)
  templates/
    prompts/             # Jinja2 templates (system + user per stage)
    ingest_cot.json      # Chain-of-thought examples for ingest
    *_template.html      # HTML report templates (Tailwind + Alpine.js)
tests/                   # pytest suite (276 tests)
policy_examples/         # 11 policy files across 6 domains + 24 frontier safety policies
docs/
  design.md              # AIRO AI Card alignment design
  work-tracker.md        # Implementation status and remaining work
```

## Running

```bash
uv sync
uv run risk-landscaper run policy.json -o output/ \
  --base-url $REFINER_BASE_URL --model $REFINER_MODEL \
  --nexus-base-dir $NEXUS_BASE_DIR
```

## Testing

```bash
uv run pytest         # all tests
uv run pytest -v      # verbose
uv run pytest tests/test_models.py  # single file
```

## Environment

| Variable           | Purpose                     |
|--------------------|-----------------------------|
| `REFINER_BASE_URL` | LLM endpoint                |
| `REFINER_MODEL`    | Model name                  |
| `REFINER_API_KEY`  | API key (default: "none")   |
| `NEXUS_BASE_DIR`   | Path to ai-atlas-nexus repo |
| `NEXUS_CHROMA_DIR` | Nexus ChromaDB path         |

## Code Conventions

### Pydantic Models for LLM Calls

- Private `_`-prefixed models (e.g. `_SlimRiskMatch`) contain only fields the LLM must reason about
- NO docstrings on these models — Instructor embeds them in JSON schema, confusing small models
- Known metadata stitched back programmatically after LLM response

### Data Model

- `RiskCard` is the primary risk type (v0.2). `RiskDetail` is a backward-compat alias.
- `Organization` is the envelope org type. `_coerce_organization` migrates legacy `Stakeholder`-shaped dicts.
- All new fields default to `None`/`[]` so existing serialized data parses without changes.
- Causal chain: `RiskSource -> Risk -> RiskConsequence -> RiskImpact` (AIRO/ISO 31000)
- Controls typed as `detect | evaluate | mitigate | eliminate` (AIRO + advisory extension)

### Pipeline Pattern

- 6-stage pipeline: ingest -> detect_domain -> map_risks -> build_landscape -> enrich_chains -> assess
- Document conversion: PDF, DOCX, HTML converted to markdown via markitdown (optional `[docs]` extra) before ingest
- Document chunking: large documents auto-split by markdown sections when `--max-context` is set. Policies deduplicated across chunks.
- Ingest has 4 LLM passes: context extraction, policy extraction, policy enrichment, entity enrichment
- Entity enrichment (pass 4) populates AIRO fields on stakeholders, AI systems, organization, and regulations. Skipped for Nexus pre-parsed inputs (no source document to extract from).
- Ground-truth cross-mappings from knowledge graph, never LLM-generated
- Perspective-based search: base query + concept name + deployer/affected/regulator viewpoints
- VAIR vocabulary matching: keyword-based enrichment of causal chain types (sources, consequences, impacts, impacted areas) without LLM calls
- Per-call debug logging via `debug.log_call()` when `--debug` is set
- `RunReport` events with `report=None` default + `if report:` guards
- HTML reports generated alongside YAML/JSON artifacts (Tailwind + Alpine.js, `__REPORT_DATA__` JSON embedding)

### Prompt Templates

- Jinja2 templates in `templates/prompts/`, named `{stage}_system.j2` and `{stage}_user.j2`
- `render_prompt()` returns `list[dict[str, str]]` (messages array)
- System prompt is optional — if template doesn't exist, only user message is sent

## Related Projects

- **taxonomy-refiner**: `/Users/hjrnunes/workspace/redhat/hjrnunes/taxonomy-refiner` — parent repo, red-team pipeline
- **AI Atlas Nexus**: `/Users/hjrnunes/workspace/redhat/ibm/ai-atlas-nexus` — risk knowledge graph (600+ risks, 10 frameworks)
- **Design context**: see `docs/design.md`

## Important

- always update the changelog