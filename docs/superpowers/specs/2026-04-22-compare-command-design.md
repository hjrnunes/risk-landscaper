# Compare Command Design

## Purpose

Add a `risk-landscaper compare` CLI command that takes two or more existing run output directories and produces a structured comparison report. This enables stakeholders to answer "how does our AI policy stack up against others?" with evidence grounded in the AI Atlas Nexus knowledge graph.

No LLM calls required — purely structural comparison of existing pipeline outputs.

## CLI Interface

```bash
# Compare two runs
uv run risk-landscaper compare runs/dhs-gov runs/meridian-bank -o output/compare

# Compare three or more
uv run risk-landscaper compare runs/dhs-gov runs/meridian-bank runs/healthcare -o output/compare
```

Each positional argument is a directory containing `risk-landscape.yaml` and `policy-profile.json` (standard pipeline output). The command produces:

```
output/compare/
  comparison.yaml
  comparison-report.html
```

## Comparison Dimensions

1. **Risk overlap** — which `risk_id`s appear in all inputs vs. unique to each. Set operations on knowledge-graph IDs.
2. **Framework coverage delta** — side-by-side framework counts per org (e.g., "DHS covers NIST AI RMF; Meridian doesn't").
3. **Policy coverage** — policy count per org, shared vs. unique policy concepts, which concepts map to different risks.
4. **Risk level distribution** — per-org counts of each severity level (very_high, high, medium, low, very_low, unassessed).
5. **Coverage gaps** — per-org gap lists, highlighting where one org has gaps the other doesn't.
6. **Causal chain depth** — per-org aggregate counts of risk sources, consequences, impacts, and controls.

## Data Model

New Pydantic models in `models.py`:

```python
class LandscapeSummary(BaseModel):
    name: str                          # run directory name / org name
    organization: str | None = None
    domain: list[str] = []
    risk_count: int = 0
    policy_count: int = 0
    timestamp: str = ""

class SharedRisk(BaseModel):
    risk_id: str
    risk_name: str
    risk_framework: str | None = None
    per_landscape: dict[str, str | None]  # name -> risk_level

class RiskRef(BaseModel):
    risk_id: str
    risk_name: str
    risk_framework: str | None = None
    risk_level: str | None = None

class CausalChainStats(BaseModel):
    sources: int = 0
    consequences: int = 0
    impacts: int = 0
    controls: int = 0

class Comparison(BaseModel):
    version: str = "0.1"
    timestamp: str = ""
    landscapes: list[LandscapeSummary] = []
    shared_risks: list[SharedRisk] = []
    unique_risks: dict[str, list[RiskRef]] = {}     # name -> risks only in that landscape
    framework_coverage: dict[str, dict[str, int]] = {}  # name -> {framework: count}
    risk_level_distribution: dict[str, dict[str, int]] = {}  # name -> {level: count}
    coverage_gaps: dict[str, list[CoverageGap]] = {}  # name -> gaps
    causal_chain_stats: dict[str, CausalChainStats] = {}  # name -> stats
```

## Code Changes

| File | Change |
|------|--------|
| `models.py` | Add `LandscapeSummary`, `SharedRisk`, `RiskRef`, `CausalChainStats`, `Comparison` |
| `compare.py` (new) | Comparison logic: load landscapes/profiles, compute all dimensions, return `Comparison` |
| `cli.py` | Add `compare` command that calls `compare.py` and writes outputs |
| `reports.py` | Add `build_comparison_report()` |
| `templates/comparison_report_template.html` (new) | Self-contained HTML report (Tailwind + Alpine.js, `__REPORT_DATA__` pattern) |
| `run_all_policies.py` | After all runs complete, call `risk-landscaper compare` on successful run dirs |

## compare.py

Pure function: `build_comparison(inputs: list[tuple[str, RiskLandscape, PolicyProfile]]) -> Comparison`

Steps:
1. Build `LandscapeSummary` for each input.
2. Compute risk ID sets per landscape. Shared = risks appearing in 2+ landscapes. Unique = risks appearing in exactly one landscape.
3. For shared risks, collect per-landscape risk levels into `SharedRisk.per_landscape`.
4. Collect framework coverage dicts directly from each landscape.
5. Count risk levels per landscape (bucketing `None` as "unassessed").
6. Collect coverage gaps per landscape.
7. Sum causal chain element counts per landscape.

No LLM calls. No Nexus access. Pure data comparison.

## HTML Report

Follows existing report patterns: Tailwind CSS + Alpine.js, `__REPORT_DATA__` JSON embedding, self-contained single file.

Sections:
- **Header** — org names, domains, run timestamps, model used
- **Overview cards** — per-landscape: risk count, policy count, domain
- **Risk overlap** — shared count + per-landscape unique count, visual summary
- **Shared risks table** — risk name, framework, per-landscape risk level (color-coded)
- **Unique risks** — per-landscape expandable list with risk name, framework, level
- **Framework coverage** — side-by-side table with counts per framework per landscape
- **Risk level distribution** — per-landscape bar or count summary
- **Causal chain depth** — per-landscape stats (sources, consequences, impacts, controls)
- **Coverage gaps** — per-landscape gap list (if any)

## Battery Integration

In `run_all_policies.py`, after the parallel execution loop completes:

1. Collect all successful run directories.
2. If 2+ succeeded, invoke `risk-landscaper compare` via subprocess (consistent with how individual runs are invoked).
3. Output goes to `runs/<battery_name>/_comparison/` (underscore prefix distinguishes from individual run dirs).
4. Print comparison summary to stdout.

```
runs/standard/
  dhs-gov/
  meridian-bank/
  healthcare/
  ...
  _comparison/
    comparison.yaml
    comparison-report.html
```

## Demo Narrative

1. Pick two contrasting policies (e.g., DHS government directive vs. Meridian Bank financial services).
2. Run both through the pipeline live or use pre-baked outputs from `runs/`.
3. Run `risk-landscaper compare runs/dhs-gov runs/meridian-bank -o output/compare`.
4. Open comparison report in browser. Walk through:
   - Shared risks across both orgs
   - Unique risks per org (surveillance vs. creditworthiness)
   - Framework coverage gaps (NIST coverage present/absent)
   - Risk level distribution differences
5. Show YAML/JSON-LD outputs to highlight data interop: machine-readable, standards-aligned data for GRC platforms.

## Future Evolution

The `Comparison` model is API-ready — wrapping it in a FastAPI endpoint to build a web explorer (Approach 1) requires minimal additional work. The comparison report becomes the natural landing page for an interactive dashboard.
