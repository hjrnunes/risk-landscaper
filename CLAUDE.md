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
  nexus_adapter.py       # Nexus payload -> PolicyProfile projection
  stages/
    ingest.py            # 3-pass LLM: context -> policies -> enrichment
    detect_domain.py     # Domain menu normalization + LLM fallback
    map_risks.py         # Perspective-based search + LLM selection + gap detection
    build_landscape.py   # Assemble RiskLandscape from mappings + Nexus data
  templates/
    prompts/             # Jinja2 templates (system + user per stage)
    ingest_cot.json      # Chain-of-thought examples for ingest
tests/                   # pytest suite (~104 tests)
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

- Ground-truth cross-mappings from knowledge graph, never LLM-generated
- Perspective-based search: base query + concept name + deployer/affected/regulator viewpoints
- Per-call debug logging via `debug.log_call()` when `--debug` is set
- `RunReport` events with `report=None` default + `if report:` guards

### Prompt Templates

- Jinja2 templates in `templates/prompts/`, named `{stage}_system.j2` and `{stage}_user.j2`
- `render_prompt()` returns `list[dict[str, str]]` (messages array)
- System prompt is optional — if template doesn't exist, only user message is sent

## Related Projects

- **taxonomy-refiner**: `/Users/hjrnunes/workspace/redhat/hjrnunes/taxonomy-refiner` — parent repo, red-team pipeline
- **AI Atlas Nexus**: `/Users/hjrnunes/workspace/redhat/ibm/ai-atlas-nexus` — risk knowledge graph (600+ risks, 10 frameworks)
- **Design context**: Obsidian vault `Red Hat`, note `Red Hat/Risk Common Data Foundation/Risk Landscape to AI Card Alignment`

## Important

- always update the changelog