# Risk Landscaper

Policy-driven AI risk landscape generation, aligned with [AIRO](https://delaramglp.github.io/airo/) (AI Risk Ontology) and the [Risk Card](https://delaramglp.github.io/aicards/example/) documentation pattern.

Takes one or more policy documents (markdown, JSON, PDF, DOCX, HTML, or AI Atlas Nexus payloads) and produces structured risk artifacts: a **PolicyProfile** (system envelope) and a **RiskLandscape** (risk analysis with RiskCards). Together these constitute a complete Risk Card. Multiple documents for the same organization are ingested independently and merged into a single profile.

## What It Does

```
Policy Document          AI Atlas Nexus (600+ risks, 10 frameworks)
       |                              |
       v                              v
  +---------+    +----------+    +----------+    +----------+    +---------+    +--------+
  | Ingest  | -> | Detect   | -> | Map      | -> | Build    | -> | Enrich  | -> | Assess |
  | context |    | domain   |    | risks    |    | landscape|    | chains  |    | levels |
  | policies|    |          |    | gaps     |    | cards    |    |         |    | AIMS   |
  | entities|    +----------+    +----------+    +----------+    +---------+    +--------+
  +---------+                                         |               |             |
       |                                              v               v             v
       v                                    risk-landscape.yaml (with causal chains + levels)
  policy-profile.json                       run-report.json
```

**Ingest** extracts organizational context, policies, boundary examples, and entity details (stakeholder involvement, AI system attributes, org governance, regulatory references) from documents via LLM (4 passes). **Detect domain** maps the organization to a domain menu. **Map risks** performs perspective-based semantic search against the Nexus knowledge graph, with LLM-based relevance selection and coverage gap detection. **Build landscape** assembles deduplicated RiskCards with VAIR-matched causal chains, typed controls, incident references, cross-framework mappings, and governance provenance. **Enrich chains** uses LLM synthesis to populate causal chains for primary-relevance risks. **Assess** computes risk levels via a 5x5 risk matrix and determines AIMS coverage across the landscape (no LLM calls).

## RiskCard

The core output unit. Each card documents a single risk with:

- **Identity** — ID, name, description, concern, framework, cross-mappings, risk type
- **Causal chain** — sources -> risk -> consequences -> impacts (AIRO/ISO 31000)
- **Controls** — typed as detect, evaluate, mitigate, or eliminate
- **Materialization** — conditions under which harm surfaces
- **Evidence** — incident references, evaluation results
- **Governance** — trustworthy characteristics, AIMS activities, risk level
- **Policy links** — which policies address this risk

A card is valid with just identity + policy links. The causal chain enriches it progressively.

## Installation

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync

# Optional: enable PDF, DOCX, HTML input support
uv pip install 'risk-landscaper[docs]'
```

Requires an OpenAI-compatible LLM endpoint. [AI Atlas Nexus](https://github.com/ibm/ai-atlas-nexus) is installed automatically from git.

## Usage

```bash
# Full pipeline
uv run risk-landscaper run policy.json -o output/ \
  --base-url http://localhost:8000/v1 \
  --model gemma-4-26b-a4b-it \
  --nexus-base-dir /path/to/ai-atlas-nexus

# Multiple documents for the same org (PDF + markdown + annex)
uv run risk-landscaper run policy.pdf faq.md annex.docx -o output/ \
  --base-url http://localhost:8000/v1 \
  --model gemma-4-26b-a4b-it \
  --nexus-base-dir /path/to/ai-atlas-nexus

# Skip optional passes (faster, less detail)
uv run risk-landscaper run policy.json -o output/ \
  --base-url ... --model ... --nexus-base-dir ... \
  --skip-enrichment \
  --skip-entity-enrichment \
  --skip-chain-enrichment

# Run policy batteries in parallel
python run_all_policies.py batteries/standard.yaml --base-url http://localhost:8000/v1
python run_all_policies.py batteries/frontier.yaml --base-url http://localhost:8000/v1 --model override-model -j 4

# With debug logging
uv run risk-landscaper run policy.json -o output/ \
  --base-url ... --model ... --nexus-base-dir ... \
  --debug output/debug/

# Export JSON Schema for output formats
uv run risk-landscaper schema -o schemas/
```

### Input Formats

- **Markdown/text** — free-form policy documents (4 LLM passes: context, policies, enrichment, entity enrichment)
- **PDF, DOCX, HTML** — converted to markdown via [markitdown](https://github.com/microsoft/markitdown), then processed as above. Requires `risk-landscaper[docs]` extra.
- **JSON array** — `[{policy_concept, concept_definition}, ...]` (skips policy extraction pass)
- **Nexus format** — `{ai_system, risks, risk_controls}` (pre-parsed, no ingest LLM calls; entity enrichment not available since there is no source document to extract from)

Multiple files can be passed as positional arguments. Each document is ingested independently (with its own format detection), then the resulting `PolicyProfile` objects are merged — policies deduplicated by concept, entities merged by name. This supports mixed-format inputs (e.g., a PDF policy document alongside a markdown FAQ).

## Output

```
output/
  policy-profile.json         # System envelope (PolicyProfile)
  risk-landscape.yaml         # Risk analysis (RiskLandscape with RiskCards)
  run-report.json             # Execution metadata + token usage
  ingest-report.html          # Ingest visualization
  risk-landscape.html         # Risk landscape report with causal chains
  ai-card.html                # Risk Card report
  run-report.html             # Pipeline execution report with LLM call details
```

## Standards Alignment

- **AIRO** (AI Risk Ontology) — causal chain: RiskSource -> Risk -> Consequence -> Impact
- **VAIR** (Vocabulary of AI Risks) — AI-specific subtypes for chain nodes
- **DPV risk extension** (W3C) — base vocabulary, risk matrices
- **ISO 31000/31073** — conceptual risk model
- **Lewis et al** — governance chain: Organization -> Policy -> Risk Assessment -> Performance
- **ISO/IEC 42001 AIMS** — AI management system activity mapping

## Development

```bash
uv run pytest           # 268 tests
uv run pytest -v        # verbose
```

11 standard policy examples across 6 domains (banking, healthcare, government, corporate, energy, telecom, insurance) and 12 frontier safety policy runs (from 12 organizations, 3 multi-doc groups) in `policy_examples/`. YAML battery configs in `batteries/` define run sets. 76 parametrized battery tests exercise format detection, parsing, ingest orchestration, content checks, and domain overrides against all examples.

See [CLAUDE.md](CLAUDE.md) for development conventions, [docs/design.md](docs/design.md) for the full design, and [docs/work-tracker.md](docs/work-tracker.md) for implementation status.

## License

TBD
