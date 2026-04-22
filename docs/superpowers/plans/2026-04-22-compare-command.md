# Compare Command Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `risk-landscaper compare` CLI command that structurally compares two or more pipeline run outputs and produces a comparison YAML + HTML report.

**Architecture:** Pure data comparison (no LLM, no Nexus). New `compare.py` module loads `RiskLandscape` and `PolicyProfile` from run directories, computes set-based risk overlap, framework deltas, severity distribution, and causal chain stats, returns a `Comparison` Pydantic model. CLI command writes YAML + HTML. Battery script calls compare after all runs complete.

**Tech Stack:** Pydantic models, PyYAML, Typer CLI, Tailwind CSS + Alpine.js HTML template

---

### Task 1: Add comparison data models to models.py

**Files:**
- Modify: `src/risk_landscaper/models.py:237-268` (after `RiskDetail` alias, before `WeakMatch`)
- Test: `tests/test_models.py`

- [ ] **Step 1: Write tests for new models**

Add to `tests/test_models.py`:

```python
from risk_landscaper.models import (
    LandscapeSummary,
    SharedRisk,
    RiskRef,
    CausalChainStats,
    Comparison,
    CoverageGap,
)


def test_landscape_summary_defaults():
    s = LandscapeSummary(name="test-run")
    assert s.organization is None
    assert s.domain == []
    assert s.risk_count == 0
    assert s.policy_count == 0
    assert s.timestamp == ""


def test_shared_risk_per_landscape():
    sr = SharedRisk(
        risk_id="r1",
        risk_name="Test Risk",
        risk_framework="NIST",
        per_landscape={"org-a": "high", "org-b": None},
    )
    assert sr.per_landscape["org-a"] == "high"
    assert sr.per_landscape["org-b"] is None


def test_risk_ref_minimal():
    r = RiskRef(risk_id="r1", risk_name="Test Risk")
    assert r.risk_framework is None
    assert r.risk_level is None


def test_causal_chain_stats_defaults():
    s = CausalChainStats()
    assert s.sources == 0
    assert s.consequences == 0
    assert s.impacts == 0
    assert s.controls == 0


def test_comparison_defaults():
    c = Comparison()
    assert c.version == "0.1"
    assert c.landscapes == []
    assert c.shared_risks == []
    assert c.unique_risks == {}
    assert c.framework_coverage == {}
    assert c.risk_level_distribution == {}
    assert c.coverage_gaps == {}
    assert c.causal_chain_stats == {}


def test_comparison_roundtrip():
    c = Comparison(
        landscapes=[LandscapeSummary(name="a", risk_count=3)],
        shared_risks=[SharedRisk(risk_id="r1", risk_name="R", per_landscape={"a": "high"})],
        unique_risks={"a": [RiskRef(risk_id="r2", risk_name="R2")]},
        causal_chain_stats={"a": CausalChainStats(sources=5, controls=2)},
    )
    d = c.model_dump()
    c2 = Comparison(**d)
    assert c2.landscapes[0].risk_count == 3
    assert c2.shared_risks[0].per_landscape == {"a": "high"}
    assert len(c2.unique_risks["a"]) == 1
    assert c2.causal_chain_stats["a"].sources == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v -k "landscape_summary or shared_risk or risk_ref or causal_chain_stats or comparison_defaults or comparison_roundtrip"`
Expected: FAIL with `ImportError: cannot import name 'LandscapeSummary'`

- [ ] **Step 3: Add models to models.py**

Add the following after the `RiskDetail = RiskCard` line (line 236) and before the `WeakMatch` class (line 239):

```python
class LandscapeSummary(BaseModel):
    name: str
    organization: str | None = None
    domain: list[str] = []
    risk_count: int = 0
    policy_count: int = 0
    timestamp: str = ""


class SharedRisk(BaseModel):
    risk_id: str
    risk_name: str
    risk_framework: str | None = None
    per_landscape: dict[str, str | None] = {}


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
```

Then add the `Comparison` class after `RiskLandscape` (after line 269 in the original, which becomes later after the above insertions):

```python
class Comparison(BaseModel):
    version: str = "0.1"
    timestamp: str = ""
    landscapes: list[LandscapeSummary] = []
    shared_risks: list[SharedRisk] = []
    unique_risks: dict[str, list[RiskRef]] = {}
    framework_coverage: dict[str, dict[str, int]] = {}
    risk_level_distribution: dict[str, dict[str, int]] = {}
    coverage_gaps: dict[str, list[CoverageGap]] = {}
    causal_chain_stats: dict[str, CausalChainStats] = {}
```

Note: `Comparison` must come after `CoverageGap` since it references it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v -k "landscape_summary or shared_risk or risk_ref or causal_chain_stats or comparison_defaults or comparison_roundtrip"`
Expected: All 6 tests PASS

- [ ] **Step 5: Run full model test suite to check for regressions**

Run: `uv run pytest tests/test_models.py -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add src/risk_landscaper/models.py tests/test_models.py
git commit -m "feat: add Comparison data models for compare command"
```

---

### Task 2: Implement compare.py core logic

**Files:**
- Create: `src/risk_landscaper/compare.py`
- Test: `tests/test_compare.py`

- [ ] **Step 1: Write tests for build_comparison**

Create `tests/test_compare.py`:

```python
from risk_landscaper.models import (
    RiskLandscape,
    RiskCard,
    RiskSource,
    RiskConsequence,
    RiskImpact,
    RiskControl,
    PolicyRiskMapping,
    RiskMatch,
    PolicyProfile,
    Organization,
    Policy,
    PolicySourceRef,
    CoverageGap,
)
from risk_landscaper.compare import build_comparison


def _make_landscape(
    risks: list[RiskCard],
    mappings: list[PolicyRiskMapping] | None = None,
    framework_coverage: dict[str, int] | None = None,
    coverage_gaps: list[CoverageGap] | None = None,
    selected_domains: list[str] | None = None,
    policy_source: PolicySourceRef | None = None,
) -> RiskLandscape:
    return RiskLandscape(
        run_slug="test",
        timestamp="2026-01-01T00:00:00Z",
        risks=risks,
        policy_mappings=mappings or [],
        framework_coverage=framework_coverage or {},
        coverage_gaps=coverage_gaps or [],
        selected_domains=selected_domains or [],
        policy_source=policy_source,
    )


def _make_profile(
    org_name: str = "TestOrg",
    domain: str = "test",
    policies: list[Policy] | None = None,
) -> PolicyProfile:
    return PolicyProfile(
        organization=Organization(name=org_name),
        domain=domain,
        policies=policies or [],
    )


def _make_risk(
    risk_id: str,
    risk_name: str = "Risk",
    risk_framework: str = "Test",
    risk_level: str | None = None,
    sources: int = 0,
    consequences: int = 0,
    impacts: int = 0,
    controls: int = 0,
) -> RiskCard:
    return RiskCard(
        risk_id=risk_id,
        risk_name=risk_name,
        risk_framework=risk_framework,
        risk_level=risk_level,
        risk_sources=[RiskSource(description=f"src-{i}") for i in range(sources)],
        consequences=[RiskConsequence(description=f"cons-{i}") for i in range(consequences)],
        impacts=[RiskImpact(description=f"imp-{i}") for i in range(impacts)],
        controls=[RiskControl(description=f"ctrl-{i}") for i in range(controls)],
    )


# --- Landscape summaries ---


def test_comparison_landscape_summaries():
    la = _make_landscape(
        risks=[_make_risk("r1"), _make_risk("r2")],
        selected_domains=["finance"],
        policy_source=PolicySourceRef(organization="Alpha", domain="finance", policy_count=3),
    )
    pa = _make_profile(org_name="Alpha", domain="finance", policies=[
        Policy(policy_concept="P1", concept_definition="D1"),
        Policy(policy_concept="P2", concept_definition="D2"),
        Policy(policy_concept="P3", concept_definition="D3"),
    ])
    lb = _make_landscape(
        risks=[_make_risk("r1")],
        selected_domains=["gov"],
        policy_source=PolicySourceRef(organization="Beta", domain="gov", policy_count=1),
    )
    pb = _make_profile(org_name="Beta", domain="gov", policies=[
        Policy(policy_concept="P1", concept_definition="D1"),
    ])

    result = build_comparison([("alpha", la, pa), ("beta", lb, pb)])
    assert len(result.landscapes) == 2
    assert result.landscapes[0].name == "alpha"
    assert result.landscapes[0].organization == "Alpha"
    assert result.landscapes[0].risk_count == 2
    assert result.landscapes[0].policy_count == 3
    assert result.landscapes[1].name == "beta"
    assert result.landscapes[1].risk_count == 1


# --- Shared and unique risks ---


def test_shared_and_unique_risks():
    la = _make_landscape(risks=[
        _make_risk("r1", risk_level="high"),
        _make_risk("r2", risk_level="low"),
    ])
    lb = _make_landscape(risks=[
        _make_risk("r1", risk_level="very_high"),
        _make_risk("r3"),
    ])
    pa = _make_profile()
    pb = _make_profile()

    result = build_comparison([("a", la, pa), ("b", lb, pb)])

    assert len(result.shared_risks) == 1
    assert result.shared_risks[0].risk_id == "r1"
    assert result.shared_risks[0].per_landscape == {"a": "high", "b": "very_high"}

    assert len(result.unique_risks["a"]) == 1
    assert result.unique_risks["a"][0].risk_id == "r2"
    assert len(result.unique_risks["b"]) == 1
    assert result.unique_risks["b"][0].risk_id == "r3"


def test_shared_risks_three_landscapes():
    """Shared = present in 2+ landscapes."""
    la = _make_landscape(risks=[_make_risk("r1"), _make_risk("r2")])
    lb = _make_landscape(risks=[_make_risk("r1"), _make_risk("r3")])
    lc = _make_landscape(risks=[_make_risk("r2"), _make_risk("r3"), _make_risk("r4")])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p), ("c", lc, p)])

    shared_ids = {sr.risk_id for sr in result.shared_risks}
    assert shared_ids == {"r1", "r2", "r3"}

    assert len(result.unique_risks.get("a", [])) == 0
    assert len(result.unique_risks.get("b", [])) == 0
    assert len(result.unique_risks["c"]) == 1
    assert result.unique_risks["c"][0].risk_id == "r4"


def test_shared_risk_per_landscape_none_when_absent():
    """If a risk is shared (in 2+) but not in all, absent entries are None."""
    la = _make_landscape(risks=[_make_risk("r1", risk_level="high")])
    lb = _make_landscape(risks=[_make_risk("r1", risk_level="low")])
    lc = _make_landscape(risks=[_make_risk("r2")])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p), ("c", lc, p)])

    r1_shared = next(sr for sr in result.shared_risks if sr.risk_id == "r1")
    assert r1_shared.per_landscape == {"a": "high", "b": "low", "c": None}


# --- Framework coverage ---


def test_framework_coverage():
    la = _make_landscape(risks=[], framework_coverage={"NIST": 3, "IBM": 2})
    lb = _make_landscape(risks=[], framework_coverage={"IBM": 1, "OWASP": 4})
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p)])
    assert result.framework_coverage["a"] == {"NIST": 3, "IBM": 2}
    assert result.framework_coverage["b"] == {"IBM": 1, "OWASP": 4}


# --- Risk level distribution ---


def test_risk_level_distribution():
    la = _make_landscape(risks=[
        _make_risk("r1", risk_level="high"),
        _make_risk("r2", risk_level="high"),
        _make_risk("r3", risk_level=None),
    ])
    lb = _make_landscape(risks=[
        _make_risk("r1", risk_level="very_high"),
    ])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p)])
    assert result.risk_level_distribution["a"]["high"] == 2
    assert result.risk_level_distribution["a"]["unassessed"] == 1
    assert result.risk_level_distribution["b"]["very_high"] == 1


# --- Coverage gaps ---


def test_coverage_gaps_per_landscape():
    gap = CoverageGap(
        policy_concept="Novel Policy",
        concept_definition="Something new",
        gap_type="novel",
        confidence=0.8,
        nearest_risks=[],
        reasoning="No match found",
    )
    la = _make_landscape(risks=[], coverage_gaps=[gap])
    lb = _make_landscape(risks=[], coverage_gaps=[])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p)])
    assert len(result.coverage_gaps["a"]) == 1
    assert result.coverage_gaps["a"][0].policy_concept == "Novel Policy"
    assert len(result.coverage_gaps["b"]) == 0


# --- Causal chain stats ---


def test_causal_chain_stats():
    la = _make_landscape(risks=[
        _make_risk("r1", sources=3, consequences=2, impacts=1, controls=4),
        _make_risk("r2", sources=1, consequences=0, impacts=2, controls=0),
    ])
    lb = _make_landscape(risks=[
        _make_risk("r1", sources=0, consequences=1, impacts=0, controls=2),
    ])
    p = _make_profile()

    result = build_comparison([("a", la, p), ("b", lb, p)])
    assert result.causal_chain_stats["a"].sources == 4
    assert result.causal_chain_stats["a"].consequences == 2
    assert result.causal_chain_stats["a"].impacts == 3
    assert result.causal_chain_stats["a"].controls == 4
    assert result.causal_chain_stats["b"].sources == 0
    assert result.causal_chain_stats["b"].controls == 2


# --- Timestamp ---


def test_comparison_has_timestamp():
    la = _make_landscape(risks=[])
    p = _make_profile()
    result = build_comparison([("a", la, p)])
    assert result.timestamp != ""


# --- Edge case: single landscape ---


def test_single_landscape_no_shared():
    la = _make_landscape(risks=[_make_risk("r1")])
    p = _make_profile()
    result = build_comparison([("a", la, p)])
    assert result.shared_risks == []
    assert len(result.unique_risks["a"]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_compare.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'risk_landscaper.compare'`

- [ ] **Step 3: Implement compare.py**

Create `src/risk_landscaper/compare.py`:

```python
from collections import Counter
from datetime import datetime, timezone

from risk_landscaper.models import (
    Comparison,
    CausalChainStats,
    LandscapeSummary,
    PolicyProfile,
    RiskLandscape,
    RiskRef,
    SharedRisk,
)


def build_comparison(
    inputs: list[tuple[str, RiskLandscape, PolicyProfile]],
) -> Comparison:
    landscapes = []
    risk_sets: dict[str, dict[str, dict]] = {}

    for name, landscape, profile in inputs:
        org_name = None
        if landscape.policy_source and landscape.policy_source.organization:
            org_name = landscape.policy_source.organization
        elif profile.organization:
            org_name = profile.organization.name

        landscapes.append(LandscapeSummary(
            name=name,
            organization=org_name,
            domain=landscape.selected_domains,
            risk_count=len(landscape.risks),
            policy_count=len(profile.policies),
            timestamp=landscape.timestamp,
        ))

        risk_sets[name] = {
            r.risk_id: {
                "risk_name": r.risk_name,
                "risk_framework": r.risk_framework,
                "risk_level": r.risk_level,
            }
            for r in landscape.risks
        }

    all_names = [name for name, _, _ in inputs]
    all_risk_ids: set[str] = set()
    for rs in risk_sets.values():
        all_risk_ids.update(rs.keys())

    id_counts = Counter(
        rid for rs in risk_sets.values() for rid in rs
    )

    shared_ids = {rid for rid, count in id_counts.items() if count >= 2}
    unique_ids_per = {
        name: {rid for rid in rs if id_counts[rid] == 1}
        for name, rs in risk_sets.items()
    }

    shared_risks = []
    for rid in sorted(shared_ids):
        first_info = next(rs[rid] for rs in risk_sets.values() if rid in rs)
        per_landscape = {
            name: risk_sets[name][rid]["risk_level"] if rid in risk_sets[name] else None
            for name in all_names
        }
        shared_risks.append(SharedRisk(
            risk_id=rid,
            risk_name=first_info["risk_name"],
            risk_framework=first_info["risk_framework"],
            per_landscape=per_landscape,
        ))

    unique_risks = {}
    for name in all_names:
        refs = []
        for rid in sorted(unique_ids_per.get(name, set())):
            info = risk_sets[name][rid]
            refs.append(RiskRef(
                risk_id=rid,
                risk_name=info["risk_name"],
                risk_framework=info["risk_framework"],
                risk_level=info["risk_level"],
            ))
        unique_risks[name] = refs

    framework_coverage = {}
    risk_level_distribution = {}
    coverage_gaps = {}
    causal_chain_stats = {}

    for name, landscape, _profile in inputs:
        framework_coverage[name] = dict(landscape.framework_coverage)

        level_counts: dict[str, int] = {}
        for r in landscape.risks:
            level = r.risk_level or "unassessed"
            level_counts[level] = level_counts.get(level, 0) + 1
        risk_level_distribution[name] = level_counts

        coverage_gaps[name] = list(landscape.coverage_gaps)

        stats = CausalChainStats(
            sources=sum(len(r.risk_sources) for r in landscape.risks),
            consequences=sum(len(r.consequences) for r in landscape.risks),
            impacts=sum(len(r.impacts) for r in landscape.risks),
            controls=sum(len(r.controls) for r in landscape.risks),
        )
        causal_chain_stats[name] = stats

    return Comparison(
        timestamp=datetime.now(timezone.utc).isoformat(),
        landscapes=landscapes,
        shared_risks=shared_risks,
        unique_risks=unique_risks,
        framework_coverage=framework_coverage,
        risk_level_distribution=risk_level_distribution,
        coverage_gaps=coverage_gaps,
        causal_chain_stats=causal_chain_stats,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_compare.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/risk_landscaper/compare.py tests/test_compare.py
git commit -m "feat: add compare.py with build_comparison logic"
```

---

### Task 3: Add compare CLI command

**Files:**
- Modify: `src/risk_landscaper/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write tests for the compare command**

Add to `tests/test_cli.py`:

```python
import yaml
from risk_landscaper.models import RiskLandscape, RiskCard, PolicyProfile, Organization, Policy


def _write_run_dir(tmp_path, name, landscape, profile):
    """Create a run output directory with landscape YAML and profile JSON."""
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / "risk-landscape.yaml").write_text(
        yaml.dump(landscape.model_dump(), default_flow_style=False, sort_keys=False)
    )
    (run_dir / "policy-profile.json").write_text(
        json.dumps(profile.model_dump(), indent=2)
    )
    return run_dir


def test_compare_two_runs(tmp_path):
    la = RiskLandscape(
        run_slug="a", timestamp="2026-01-01",
        risks=[RiskCard(risk_id="r1", risk_name="R1", risk_level="high")],
        framework_coverage={"NIST": 1},
    )
    pa = PolicyProfile(
        organization=Organization(name="Alpha"),
        policies=[Policy(policy_concept="P1", concept_definition="D1")],
    )
    lb = RiskLandscape(
        run_slug="b", timestamp="2026-01-02",
        risks=[
            RiskCard(risk_id="r1", risk_name="R1", risk_level="low"),
            RiskCard(risk_id="r2", risk_name="R2"),
        ],
        framework_coverage={"NIST": 1, "IBM": 1},
    )
    pb = PolicyProfile(
        organization=Organization(name="Beta"),
        policies=[
            Policy(policy_concept="P1", concept_definition="D1"),
            Policy(policy_concept="P2", concept_definition="D2"),
        ],
    )

    dir_a = _write_run_dir(tmp_path, "run-a", la, pa)
    dir_b = _write_run_dir(tmp_path, "run-b", lb, pb)
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["compare", str(dir_a), str(dir_b), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output

    assert (out_dir / "comparison.yaml").exists()
    assert (out_dir / "comparison-report.html").exists()

    data = yaml.safe_load((out_dir / "comparison.yaml").read_text())
    assert len(data["landscapes"]) == 2
    assert len(data["shared_risks"]) == 1
    assert data["shared_risks"][0]["risk_id"] == "r1"


def test_compare_missing_directory(tmp_path):
    la = RiskLandscape(run_slug="a", risks=[])
    pa = PolicyProfile(policies=[])
    dir_a = _write_run_dir(tmp_path, "run-a", la, pa)

    result = runner.invoke(app, ["compare", str(dir_a), "/nonexistent/dir", "-o", "/tmp/out"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_compare_single_directory_rejected(tmp_path):
    la = RiskLandscape(run_slug="a", risks=[])
    pa = PolicyProfile(policies=[])
    dir_a = _write_run_dir(tmp_path, "run-a", la, pa)
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["compare", str(dir_a), "-o", str(out_dir)])
    assert result.exit_code != 0
    assert "at least 2" in result.output.lower() or "two" in result.output.lower()


def test_compare_missing_landscape_yaml(tmp_path):
    run_dir = tmp_path / "bad-run"
    run_dir.mkdir()
    (run_dir / "policy-profile.json").write_text("{}")
    out_dir = tmp_path / "out"

    dummy = tmp_path / "dummy"
    dummy.mkdir()
    la = RiskLandscape(run_slug="d", risks=[])
    pa = PolicyProfile(policies=[])
    _write_run_dir(tmp_path, "good-run", la, pa)

    result = runner.invoke(app, ["compare", str(run_dir), str(tmp_path / "good-run"), "-o", str(out_dir)])
    assert result.exit_code != 0
    assert "risk-landscape.yaml" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v -k "compare"`
Expected: FAIL — `compare` command not found

- [ ] **Step 3: Implement the compare CLI command**

Add to `src/risk_landscaper/cli.py`, after the `export` command:

```python
@app.command()
def compare(
    run_dirs: list[Path] = typer.Argument(..., help="Run output directories to compare (each must contain risk-landscape.yaml and policy-profile.json)"),
    output: Path = typer.Option(..., "--output", "-o", help="Output directory for comparison report"),
):
    """Compare two or more risk landscape runs."""
    if len(run_dirs) < 2:
        typer.echo("Error: compare requires at least 2 run directories", err=True)
        raise typer.Exit(1)

    for d in run_dirs:
        if not d.exists():
            typer.echo(f"Error: {d} does not exist", err=True)
            raise typer.Exit(1)

    inputs = []
    for d in run_dirs:
        landscape_path = d / "risk-landscape.yaml"
        profile_path = d / "policy-profile.json"

        if not landscape_path.exists():
            typer.echo(f"Error: {landscape_path} not found", err=True)
            raise typer.Exit(1)
        if not profile_path.exists():
            typer.echo(f"Error: {profile_path} not found", err=True)
            raise typer.Exit(1)

        from risk_landscaper.models import RiskLandscape, PolicyProfile
        landscape = RiskLandscape(**yaml.safe_load(landscape_path.read_text()))
        profile = PolicyProfile(**json.loads(profile_path.read_text()))
        inputs.append((d.name, landscape, profile))

    from risk_landscaper.compare import build_comparison
    comparison = build_comparison(inputs)

    output.mkdir(parents=True, exist_ok=True)

    comparison_path = output / "comparison.yaml"
    comparison_path.write_text(yaml.dump(
        comparison.model_dump(), default_flow_style=False, sort_keys=False,
    ))
    typer.echo(f"Comparison written to {comparison_path}")

    from risk_landscaper.reports import build_comparison_report
    build_comparison_report(comparison.model_dump(), output / "comparison-report.html")
    typer.echo(f"Comparison report written to {output / 'comparison-report.html'}")

    typer.echo(f"Compared {len(inputs)} landscapes: {len(comparison.shared_risks)} shared risks, "
               + ", ".join(f"{len(v)} unique to {k}" for k, v in comparison.unique_risks.items()))
```

- [ ] **Step 4: Add stub report function to reports.py**

Add to `src/risk_landscaper/reports.py`:

```python
def build_comparison_report(data: dict, output_path: Path) -> Path:
    return _render("comparison_report_template.html", data, output_path)
```

- [ ] **Step 5: Create a minimal placeholder HTML template**

Create `src/risk_landscaper/templates/comparison_report_template.html` with a minimal working template (the full template is built in Task 4):

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Comparison Report</title>
</head>
<body>
  <h1>Comparison Report</h1>
  <pre>__REPORT_DATA__</pre>
</body>
</html>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v -k "compare"`
Expected: All 4 compare tests PASS

- [ ] **Step 7: Run full CLI test suite**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/risk_landscaper/cli.py src/risk_landscaper/reports.py src/risk_landscaper/templates/comparison_report_template.html tests/test_cli.py
git commit -m "feat: add compare CLI command"
```

---

### Task 4: Build the comparison HTML report template

**Files:**
- Modify: `src/risk_landscaper/templates/comparison_report_template.html`

This task replaces the placeholder template from Task 3 with a full Tailwind + Alpine.js report. No new tests — the CLI tests from Task 3 already verify the template renders. Manual browser verification at the end.

- [ ] **Step 1: Write the full comparison report template**

Replace `src/risk_landscaper/templates/comparison_report_template.html` with the full template. Follow the existing report pattern from `risk_landscape_report_template.html`:
- `<script>` block at bottom that parses `__REPORT_DATA__` into an Alpine.js `reportApp()` function
- Tailwind CSS via CDN, Alpine.js via CDN
- Same tooltip/prov CSS styles as existing reports
- `x-cloak` on body

Template sections (all reading from the `__REPORT_DATA__` JSON):

**Header**: Dark header bar with "Comparison Report" title, landscape names, timestamp.

**Overview cards**: Grid of cards, one per landscape — org name, domain badges, risk count, policy count.

**Risk overlap summary**: Three stat cards — shared count, and per-landscape unique count. For 2 landscapes this is a clear "A has X unique, B has Y unique, Z shared" layout.

**Shared risks table**: Table with columns: risk name, framework, then one column per landscape showing risk level as a color-coded badge (very_high=red, high=orange, medium=yellow, low=green, unassessed=gray). Sorted by risk name. Use `x-for` over `data.shared_risks`.

**Unique risks per landscape**: One collapsible section per landscape (Alpine.js `x-show`). Each lists the unique risks with name, framework, and risk level badge.

**Framework coverage**: Table with rows = union of all framework names, columns = one per landscape showing the count. Highlight cells where one landscape has coverage and another doesn't (e.g., bold for non-zero vs gray for zero).

**Risk level distribution**: Per-landscape horizontal bars or count grid showing how many risks fall into each severity bucket.

**Causal chain depth**: Simple table — rows: sources, consequences, impacts, controls. Columns: one per landscape.

**Coverage gaps**: Per-landscape collapsible section listing gaps (if any). Show policy_concept, gap_type, reasoning.

Color scheme for risk levels used across the report:
- `very_high`: `bg-red-100 text-red-800`
- `high`: `bg-orange-100 text-orange-800`
- `medium`: `bg-yellow-100 text-yellow-800`
- `low`: `bg-green-100 text-green-800`
- `very_low`: `bg-emerald-100 text-emerald-800`
- `unassessed` / null: `bg-gray-100 text-gray-500`

- [ ] **Step 2: Test with real data**

Run the compare command against two existing pre-baked runs to verify the template renders correctly:

```bash
uv run risk-landscaper compare runs/dhs-gov runs/meridian-bank -o /tmp/compare-test
open /tmp/compare-test/comparison-report.html
```

Verify in browser:
- Header shows both org names
- Overview cards show correct risk/policy counts
- Shared risks table displays with per-org risk levels
- Unique risks sections expand/collapse
- Framework coverage table shows side-by-side counts
- Risk level distribution renders
- Causal chain stats render
- No JS console errors

- [ ] **Step 3: Test with three landscapes**

```bash
uv run risk-landscaper compare runs/dhs-gov runs/meridian-bank runs/healthcare -o /tmp/compare-test-3
open /tmp/compare-test-3/comparison-report.html
```

Verify the template handles 3+ columns correctly (table headers, overview cards grid).

- [ ] **Step 4: Commit**

```bash
git add src/risk_landscaper/templates/comparison_report_template.html
git commit -m "feat: add full comparison HTML report template"
```

---

### Task 5: Integrate compare into battery script

**Files:**
- Modify: `run_all_policies.py`

- [ ] **Step 1: Add compare step after parallel runs**

In `run_all_policies.py`, after the `print(f"\nDone. ...")` line (line 131), before `sys.exit`, add logic to run compare:

```python
    succeeded_dirs = [
        runs_dir / name
        for name, files in runs
        if name not in failed
    ]
    if len(succeeded_dirs) >= 2:
        compare_out = runs_dir / "_comparison"
        compare_cmd = [
            "uv", "run", "risk-landscaper", "compare",
            *[str(d) for d in succeeded_dirs],
            "-o", str(compare_out),
        ]
        print(f"\nRunning comparison across {len(succeeded_dirs)} landscapes...")
        compare_result = subprocess.run(compare_cmd, capture_output=True, text=True)
        if compare_result.returncode == 0:
            print(f"  Comparison report: {compare_out / 'comparison-report.html'}")
        else:
            print(f"  Comparison failed:")
            for line in compare_result.stderr.strip().splitlines()[-3:]:
                print(f"    {line}")
    elif len(succeeded_dirs) < 2:
        print("\nSkipping comparison (fewer than 2 successful runs)")
```

- [ ] **Step 2: Verify with a dry-run check**

The battery script requires a running LLM endpoint to produce new runs, so we can't run it in tests. Instead, verify the code is correct by checking that the existing pre-baked `runs/` directory works with compare:

```bash
uv run risk-landscaper compare runs/dhs-gov runs/meridian-bank runs/healthcare -o /tmp/battery-compare-test
```

Expected: exits 0, produces comparison.yaml and comparison-report.html.

- [ ] **Step 3: Commit**

```bash
git add run_all_policies.py
git commit -m "feat: run compare after battery completion"
```

---

### Task 6: Update CLAUDE.md and changelog

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md directory structure**

In the Directory Structure section, add `compare.py` to the file listing under `src/risk_landscaper/`:

```
  compare.py             # Structural comparison of 2+ risk landscapes
```

And add `comparison_report_template.html` mention in the templates section.

- [ ] **Step 2: Update CLAUDE.md code conventions**

In the Pipeline Pattern section, add a note about the compare command:

```
- Compare command: `risk-landscaper compare` takes 2+ run output directories, computes risk overlap / framework deltas / severity distribution via `compare.py`, produces comparison YAML + HTML report. No LLM calls. Battery script (`run_all_policies.py`) auto-runs compare after all individual runs complete.
```

- [ ] **Step 3: Update changelog**

Add an entry to the changelog documenting the new compare command.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "docs: document compare command in CLAUDE.md and changelog"
```
