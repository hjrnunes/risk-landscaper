# Risk Landscaper

Policy-driven AI risk landscape generation, aligned with [AIRO](https://delaramglp.github.io/airo/) (AI Risk Ontology) and the [AI Card](https://delaramglp.github.io/aicards/example/) documentation pattern.

Takes policy documents (markdown, JSON, or AI Atlas Nexus payloads) and produces structured risk artifacts: a **PolicyProfile** (system envelope) and a **RiskLandscape** (risk analysis with RiskCards). Together these constitute a complete AI Card.

## What It Does

```
Policy Document          AI Atlas Nexus (600+ risks, 10 frameworks)
       |                              |
       v                              v
  +---------+    +----------+    +----------+    +----------+
  | Ingest  | -> | Detect   | -> | Map      | -> | Build    |
  | context |    | domain   |    | risks    |    | landscape|
  | policies|    |          |    | gaps     |    | cards    |
  +---------+    +----------+    +----------+    +----------+
       |                                              |
       v                                              v
  policy-profile.json                     risk-landscape.yaml
                                          run-report.json
```

**Ingest** extracts organizational context, policies, and boundary examples from documents via LLM. **Detect domain** maps the organization to a domain menu. **Map risks** performs perspective-based semantic search against the Nexus knowledge graph, with LLM-based relevance selection and coverage gap detection. **Build landscape** assembles deduplicated RiskCards with causal chains, typed controls, cross-framework mappings, and governance provenance.

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
```

Requires a local clone of [AI Atlas Nexus](https://github.com/ibm/ai-atlas-nexus) and an OpenAI-compatible LLM endpoint.

## Usage

```bash
# Full pipeline
uv run risk-landscaper run policy.json -o output/ \
  --base-url http://localhost:8000/v1 \
  --model gemma-3-12b-it \
  --nexus-base-dir /path/to/ai-atlas-nexus

# Skip ingest enrichment (faster, less detail)
uv run risk-landscaper run policy.json -o output/ \
  --base-url ... --model ... --nexus-base-dir ... \
  --skip-enrichment

# With debug logging
uv run risk-landscaper run policy.json -o output/ \
  --base-url ... --model ... --nexus-base-dir ... \
  --debug output/debug/
```

### Input Formats

- **Markdown/text** — free-form policy documents (3 LLM passes: context, policies, enrichment)
- **JSON array** — `[{policy_concept, concept_definition}, ...]` (skips policy extraction pass)
- **Nexus format** — `{ai_system, risks, risk_controls}` (pre-parsed, no ingest LLM calls)

## Output

```
output/
  policy-profile.json    # System envelope (PolicyProfile)
  risk-landscape.yaml    # Risk analysis (RiskLandscape with RiskCards)
  run-report.json        # Execution metadata + token usage
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
uv run pytest           # 104 tests
```

See [CLAUDE.md](CLAUDE.md) for development conventions, [docs/design.md](docs/design.md) for the full design, and [docs/work-tracker.md](docs/work-tracker.md) for implementation status.

## License

TBD
