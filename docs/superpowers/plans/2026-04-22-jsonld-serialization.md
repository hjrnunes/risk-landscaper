# JSON-LD Serialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Emit RiskLandscape as valid JSON-LD using AIRO/VAIR/DPV ontology IRIs, with optional Turtle output via rdflib.

**Architecture:** A single `serialize.py` module with a JSON-LD `@context` dict mapping Pydantic field names to ontology IRIs. No required dependencies for JSON-LD; `rdflib` as optional `[rdf]` extra for Turtle. CLI integration via `--format` flag on `run` and new `export` subcommand.

**Tech Stack:** Python 3.11+, Pydantic, Typer, rdflib (optional)

**Spec:** `docs/superpowers/specs/2026-04-22-jsonld-serialization-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `src/risk_landscaper/serialize.py` | **Create.** JSON-LD context, `landscape_to_jsonld()`, `landscape_to_turtle()`, VAIR IRI lookup |
| `tests/test_serialize.py` | **Create.** Unit tests for serialization |
| `src/risk_landscaper/cli.py` | **Modify.** Add `--format` flag to `run`, add `export` subcommand |
| `tests/test_cli.py` | **Modify.** Add tests for `export` subcommand and `--format` flag |
| `pyproject.toml` | **Modify.** Add `[rdf]` optional dependency |
| `CHANGELOG.md` | **Modify.** Document the new feature |

---

### Task 1: Core JSON-LD serialization — context and minimal RiskCard

**Files:**
- Create: `tests/test_serialize.py`
- Create: `src/risk_landscaper/serialize.py`

- [ ] **Step 1: Write failing test — empty landscape serializes with correct structure**

```python
# tests/test_serialize.py
from risk_landscaper.models import RiskLandscape
from risk_landscaper.serialize import landscape_to_jsonld


def test_empty_landscape_has_context_and_type():
    landscape = RiskLandscape(run_slug="test-run", timestamp="2026-04-22T10:00:00Z")
    result = landscape_to_jsonld(landscape)
    assert "@context" in result
    ctx = result["@context"]
    assert ctx["airo"] == "https://w3id.org/airo#"
    assert ctx["vair"] == "https://w3id.org/vair#"
    assert ctx["nexus"] == "https://ibm.github.io/ai-atlas-nexus/ontology/"
    assert ctx["dpv"] == "https://w3id.org/dpv#"
    assert ctx["rl"] == "https://trustyai.io/risk-landscaper/"
    assert result["@type"] == "rl:RiskLandscape"
    assert result["@id"] == "rl:test-run"
    assert result["rl:version"] == "0.2"
    assert result["rl:hasRiskCard"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_serialize.py::test_empty_landscape_has_context_and_type -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'risk_landscaper.serialize'`

- [ ] **Step 3: Write failing test — minimal RiskCard serializes with correct @id and @type**

```python
def test_minimal_risk_card():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(risk_id="bias-discrimination-output", risk_name="Bias/Discrimination in Output"),
        ],
    )
    result = landscape_to_jsonld(landscape)
    cards = result["rl:hasRiskCard"]
    assert len(cards) == 1
    card = cards[0]
    assert card["@id"] == "nexus:bias-discrimination-output"
    assert card["@type"] == "airo:Risk"
    assert card["rdfs:label"] == "Bias/Discrimination in Output"
```

Add import at top:

```python
from risk_landscaper.models import RiskLandscape, RiskCard
```

- [ ] **Step 4: Write failing test — None optional fields are omitted**

```python
def test_none_fields_omitted():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(risk_id="test-risk", risk_name="Test"),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    assert "rl:materializationConditions" not in card
    assert "rl:riskConcern" not in card
    assert "airo:hasConsequence" not in card
    assert "airo:hasImpact" not in card
```

- [ ] **Step 5: Implement serialize.py with context and basic serialization**

```python
# src/risk_landscaper/serialize.py
from __future__ import annotations

from risk_landscaper.models import RiskLandscape

JSONLD_CONTEXT = {
    "airo": "https://w3id.org/airo#",
    "vair": "https://w3id.org/vair#",
    "nexus": "https://ibm.github.io/ai-atlas-nexus/ontology/",
    "dpv": "https://w3id.org/dpv#",
    "rl": "https://trustyai.io/risk-landscaper/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}


def _serialize_risk_card(card) -> dict:
    node: dict = {
        "@id": f"nexus:{card.risk_id}",
        "@type": "airo:Risk",
        "rdfs:label": card.risk_name,
    }
    if card.risk_description:
        node["rdfs:comment"] = card.risk_description
    if card.risk_concern:
        node["rl:riskConcern"] = card.risk_concern
    if card.risk_framework:
        node["rl:riskFramework"] = card.risk_framework
    if card.cross_mappings:
        node["rl:crossMapping"] = card.cross_mappings
    if card.risk_type:
        node["rl:riskType"] = card.risk_type
    if card.descriptors:
        node["rl:descriptor"] = card.descriptors
    if card.trustworthy_characteristics:
        node["rl:trustworthyCharacteristic"] = card.trustworthy_characteristics
    if card.aims_activities:
        node["rl:aimsActivity"] = card.aims_activities
    if card.materialization_conditions:
        node["rl:materializationConditions"] = card.materialization_conditions
    if card.risk_level:
        node["rl:riskLevel"] = card.risk_level
    if card.related_policies:
        node["rl:relatedPolicy"] = card.related_policies
    return node


def landscape_to_jsonld(landscape: RiskLandscape) -> dict:
    doc: dict = {
        "@context": dict(JSONLD_CONTEXT),
        "@id": f"rl:{landscape.run_slug}" if landscape.run_slug else "rl:unnamed",
        "@type": "rl:RiskLandscape",
        "rl:version": landscape.version,
        "rl:hasRiskCard": [_serialize_risk_card(card) for card in landscape.risks],
    }
    return doc
```

- [ ] **Step 6: Run all three tests to verify they pass**

Run: `uv run pytest tests/test_serialize.py -v`
Expected: 3 PASSED

- [ ] **Step 7: Commit**

```bash
git add src/risk_landscaper/serialize.py tests/test_serialize.py
git commit -m "Add JSON-LD serialization: context, minimal RiskCard, empty landscape"
```

---

### Task 2: Causal chain serialization (sources, consequences, impacts)

**Files:**
- Modify: `tests/test_serialize.py`
- Modify: `src/risk_landscaper/serialize.py`

- [ ] **Step 1: Write failing test — risk sources serialize with AIRO types**

```python
from risk_landscaper.models import RiskSource

def test_risk_sources_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                risk_sources=[
                    RiskSource(description="Biased training data", source_type="data", likelihood="likely"),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    sources = card["airo:isRiskSourceFor"]
    assert len(sources) == 1
    src = sources[0]
    assert src["@type"] == ["airo:RiskSource", "vair:DataRiskSource"]
    assert src["rdfs:comment"] == "Biased training data"
    assert src["airo:hasLikelihood"] == "likely"
```

- [ ] **Step 2: Write failing test — consequences serialize with AIRO properties**

```python
from risk_landscaper.models import RiskConsequence

def test_consequences_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                consequences=[
                    RiskConsequence(description="Discriminatory outputs", likelihood="possible", severity="high"),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    cons = card["airo:hasConsequence"]
    assert len(cons) == 1
    assert cons[0]["@type"] == "airo:Consequence"
    assert cons[0]["rdfs:comment"] == "Discriminatory outputs"
    assert cons[0]["airo:hasLikelihood"] == "possible"
    assert cons[0]["airo:hasSeverity"] == "high"
```

- [ ] **Step 3: Write failing test — impacts serialize with stakeholders and area**

```python
from risk_landscaper.models import RiskImpact

def test_impacts_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                impacts=[
                    RiskImpact(
                        description="Users denied services",
                        severity="high",
                        area="Right",
                        affected_stakeholders=["end users", "applicants"],
                        harm_type="DiscriminatoryTreatment",
                    ),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    impacts = card["airo:hasImpact"]
    assert len(impacts) == 1
    imp = impacts[0]
    assert imp["@type"] == ["airo:Impact", "vair:DiscriminatoryTreatment"]
    assert imp["airo:hasSeverity"] == "high"
    assert imp["airo:hasImpactOnArea"] == "vair:Right"
    assert imp["airo:hasImpactOnStakeholder"] == ["end users", "applicants"]
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_serialize.py::test_risk_sources_serialize tests/test_serialize.py::test_consequences_serialize tests/test_serialize.py::test_impacts_serialize -v`
Expected: 3 FAILED

- [ ] **Step 5: Implement causal chain serialization**

Add the VAIR parent category map and serialization helpers to `serialize.py`:

```python
from risk_landscaper.vair import RISK_SOURCES, CONSEQUENCES, IMPACTS, IMPACTED_AREAS

SOURCE_TYPE_TO_VAIR = {
    "attack": "vair:Attack",
    "data": "vair:DataRiskSource",
    "organisational": "vair:OrganisationalRiskSource",
    "performance": "vair:PerformanceRiskSource",
    "system": "vair:SystemRiskSource",
}

_VAIR_IDS = {t.id for t in RISK_SOURCES + CONSEQUENCES + IMPACTS + IMPACTED_AREAS}
_IMPACTED_AREA_IDS = {t.id for t in IMPACTED_AREAS}


def _vair_iri(value: str) -> str | None:
    if value in _VAIR_IDS:
        return f"vair:{value}"
    return None


def _serialize_risk_source(src) -> dict:
    types: list[str] = ["airo:RiskSource"]
    if src.source_type:
        vair = SOURCE_TYPE_TO_VAIR.get(src.source_type) or _vair_iri(src.source_type)
        if vair:
            types.append(vair)
    node: dict = {"@type": types if len(types) > 1 else types[0], "rdfs:comment": src.description}
    if src.likelihood:
        node["airo:hasLikelihood"] = src.likelihood
    if src.exploits_vulnerability:
        node["rl:exploitsVulnerability"] = src.exploits_vulnerability
    return node


def _serialize_consequence(cons) -> dict:
    node: dict = {"@type": "airo:Consequence", "rdfs:comment": cons.description}
    if cons.likelihood:
        node["airo:hasLikelihood"] = cons.likelihood
    if cons.severity:
        node["airo:hasSeverity"] = cons.severity
    return node


def _serialize_impact(imp) -> dict:
    types: list[str] = ["airo:Impact"]
    if imp.harm_type:
        vair = _vair_iri(imp.harm_type)
        if vair:
            types.append(vair)
    node: dict = {"@type": types if len(types) > 1 else types[0], "rdfs:comment": imp.description}
    if imp.severity:
        node["airo:hasSeverity"] = imp.severity
    if imp.area:
        area_iri = _vair_iri(imp.area)
        node["airo:hasImpactOnArea"] = area_iri if area_iri else imp.area
    if imp.affected_stakeholders:
        node["airo:hasImpactOnStakeholder"] = imp.affected_stakeholders
    return node
```

Then update `_serialize_risk_card` to include the chain:

```python
    if card.risk_sources:
        node["airo:isRiskSourceFor"] = [_serialize_risk_source(s) for s in card.risk_sources]
    if card.consequences:
        node["airo:hasConsequence"] = [_serialize_consequence(c) for c in card.consequences]
    if card.impacts:
        node["airo:hasImpact"] = [_serialize_impact(i) for i in card.impacts]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_serialize.py -v`
Expected: 6 PASSED

- [ ] **Step 7: Commit**

```bash
git add src/risk_landscaper/serialize.py tests/test_serialize.py
git commit -m "Add causal chain serialization: sources, consequences, impacts with VAIR IRIs"
```

---

### Task 3: Controls, incidents, evaluations serialization

**Files:**
- Modify: `tests/test_serialize.py`
- Modify: `src/risk_landscaper/serialize.py`

- [ ] **Step 1: Write failing test — control type maps to AIRO property**

```python
from risk_landscaper.models import RiskControl

def test_control_type_mapping():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                controls=[
                    RiskControl(description="Monitor for bias", control_type="detect"),
                    RiskControl(description="Run benchmarks", control_type="evaluate"),
                    RiskControl(description="Apply guardrails", control_type="mitigate"),
                    RiskControl(description="Remove feature", control_type="eliminate"),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    controls = card["airo:modifiesRiskConcept"]
    assert len(controls) == 4
    assert controls[0]["rl:controlFunction"] == "airo:detectsRiskConcept"
    assert controls[1]["rl:controlFunction"] == "rl:evaluatesRiskConcept"
    assert controls[2]["rl:controlFunction"] == "airo:mitigatesRiskConcept"
    assert controls[3]["rl:controlFunction"] == "airo:eliminatesRiskConcept"
    assert all(c["@type"] == "airo:RiskControl" for c in controls)
```

- [ ] **Step 2: Write failing test — incidents serialize as DPV type**

```python
from risk_landscaper.models import RiskIncidentRef

def test_incidents_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                incidents=[
                    RiskIncidentRef(
                        name="COMPAS Recidivism",
                        description="Racial bias in sentencing",
                        source_uri="https://example.com/compas",
                        status="concluded",
                    ),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    incidents = card["dpv:Incident"]
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc["@type"] == "dpv:Incident"
    assert inc["rdfs:label"] == "COMPAS Recidivism"
    assert inc["rdfs:comment"] == "Racial bias in sentencing"
    assert inc["rdfs:seeAlso"] == "https://example.com/compas"
    assert inc["rl:incidentStatus"] == "concluded"
```

- [ ] **Step 3: Write failing test — evaluations serialize**

```python
from risk_landscaper.models import EvaluationRef

def test_evaluations_serialize():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                evaluations=[
                    EvaluationRef(
                        eval_id="eval-001",
                        eval_type="lm-eval",
                        summary="TruthfulQA pass rate",
                        metrics={"pass_rate": 0.95},
                        source_uri="https://example.com/eval",
                    ),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    card = result["rl:hasRiskCard"][0]
    evals = card["rl:evaluation"]
    assert len(evals) == 1
    ev = evals[0]
    assert ev["@type"] == "rl:Evaluation"
    assert ev["@id"] == "eval-001"
    assert ev["rl:evalType"] == "lm-eval"
    assert ev["rdfs:comment"] == "TruthfulQA pass rate"
    assert ev["rl:metrics"] == {"pass_rate": 0.95}
    assert ev["rdfs:seeAlso"] == "https://example.com/eval"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_serialize.py::test_control_type_mapping tests/test_serialize.py::test_incidents_serialize tests/test_serialize.py::test_evaluations_serialize -v`
Expected: 3 FAILED

- [ ] **Step 5: Implement controls, incidents, evaluations serialization**

Add to `serialize.py`:

```python
CONTROL_TYPE_TO_IRI = {
    "detect": "airo:detectsRiskConcept",
    "evaluate": "rl:evaluatesRiskConcept",
    "mitigate": "airo:mitigatesRiskConcept",
    "eliminate": "airo:eliminatesRiskConcept",
}


def _serialize_control(ctrl) -> dict:
    node: dict = {"@type": "airo:RiskControl", "rdfs:comment": ctrl.description}
    if ctrl.control_type:
        iri = CONTROL_TYPE_TO_IRI.get(ctrl.control_type)
        if iri:
            node["rl:controlFunction"] = iri
    if ctrl.targets:
        node["rl:controlTargets"] = ctrl.targets
    return node


def _serialize_incident(inc) -> dict:
    node: dict = {"@type": "dpv:Incident", "rdfs:label": inc.name}
    if inc.description:
        node["rdfs:comment"] = inc.description
    if inc.source_uri:
        node["rdfs:seeAlso"] = inc.source_uri
    if inc.status:
        node["rl:incidentStatus"] = inc.status
    return node


def _serialize_evaluation(ev) -> dict:
    node: dict = {"@type": "rl:Evaluation", "@id": ev.eval_id}
    if ev.eval_type:
        node["rl:evalType"] = ev.eval_type
    if ev.summary:
        node["rdfs:comment"] = ev.summary
    if ev.metrics:
        node["rl:metrics"] = ev.metrics
    if ev.source_uri:
        node["rdfs:seeAlso"] = ev.source_uri
    if ev.timestamp:
        node["rl:timestamp"] = ev.timestamp
    return node
```

Add to `_serialize_risk_card`:

```python
    if card.controls:
        node["airo:modifiesRiskConcept"] = [_serialize_control(c) for c in card.controls]
    if card.incidents:
        node["dpv:Incident"] = [_serialize_incident(i) for i in card.incidents]
    if card.evaluations:
        node["rl:evaluation"] = [_serialize_evaluation(e) for e in card.evaluations]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_serialize.py -v`
Expected: 9 PASSED

- [ ] **Step 7: Commit**

```bash
git add src/risk_landscaper/serialize.py tests/test_serialize.py
git commit -m "Add controls, incidents, evaluations serialization with AIRO/DPV types"
```

---

### Task 4: VAIR type resolution tests

**Files:**
- Modify: `tests/test_serialize.py`
- Modify: `src/risk_landscaper/serialize.py` (if needed)

- [ ] **Step 1: Write failing test — each parent source_type category maps correctly**

```python
from risk_landscaper.serialize import SOURCE_TYPE_TO_VAIR

def test_all_source_type_parents_mapped():
    expected = {
        "attack": "vair:Attack",
        "data": "vair:DataRiskSource",
        "organisational": "vair:OrganisationalRiskSource",
        "performance": "vair:PerformanceRiskSource",
        "system": "vair:SystemRiskSource",
    }
    assert SOURCE_TYPE_TO_VAIR == expected
```

- [ ] **Step 2: Write failing test — specific VAIR type IDs resolve to IRIs**

```python
from risk_landscaper.serialize import _vair_iri

def test_vair_iri_specific_types():
    assert _vair_iri("AdversarialAttack") == "vair:AdversarialAttack"
    assert _vair_iri("BiasedTrainingData") == "vair:BiasedTrainingData"
    assert _vair_iri("Bias") == "vair:Bias"
    assert _vair_iri("Death") == "vair:Death"
    assert _vair_iri("Freedom") == "vair:Freedom"
```

- [ ] **Step 3: Write test — unknown values return None**

```python
def test_vair_iri_unknown_returns_none():
    assert _vair_iri("SomethingInvented") is None
    assert _vair_iri("") is None
```

- [ ] **Step 4: Write test — impact harm_type as unknown string stays literal**

```python
def test_impact_unknown_harm_type_no_vair_iri():
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test",
                impacts=[
                    RiskImpact(description="Custom harm", harm_type="CustomHarmType"),
                ],
            ),
        ],
    )
    result = landscape_to_jsonld(landscape)
    imp = result["rl:hasRiskCard"][0]["airo:hasImpact"][0]
    assert imp["@type"] == "airo:Impact"
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/test_serialize.py -v`
Expected: 13 PASSED

- [ ] **Step 6: Commit**

```bash
git add tests/test_serialize.py
git commit -m "Add VAIR type resolution tests"
```

---

### Task 5: Landscape envelope metadata and provenance

**Files:**
- Modify: `tests/test_serialize.py`
- Modify: `src/risk_landscaper/serialize.py`

- [ ] **Step 1: Write failing test — envelope metadata serializes**

```python
from risk_landscaper.models import GovernanceProvenance, PolicySourceRef, KnowledgeBaseRef

def test_envelope_metadata():
    landscape = RiskLandscape(
        run_slug="test-run",
        timestamp="2026-04-22T10:00:00Z",
        model="granite-3.2-8b",
        selected_domains=["banking"],
        framework_coverage={"owasp-llm": 5, "nist-ai-rmf": 3},
        policy_source=PolicySourceRef(organization="Acme Corp", domain="banking", policy_count=10),
        knowledge_base=KnowledgeBaseRef(nexus_risk_count=600),
    )
    result = landscape_to_jsonld(landscape)
    assert result["rl:timestamp"] == "2026-04-22T10:00:00Z"
    assert result["rl:model"] == "granite-3.2-8b"
    assert result["rl:selectedDomains"] == ["banking"]
    assert result["rl:frameworkCoverage"] == {"owasp-llm": 5, "nist-ai-rmf": 3}
```

- [ ] **Step 2: Write failing test — provenance serializes**

```python
def test_provenance_serializes():
    landscape = RiskLandscape(
        run_slug="test-run",
        provenance=GovernanceProvenance(
            produced_by="risk-landscaper",
            governance_function="evaluate",
            aims_activities=["aimsA6", "aimsA8"],
            review_status="draft",
        ),
    )
    result = landscape_to_jsonld(landscape)
    prov = result["rl:provenance"]
    assert prov["rl:producedBy"] == "risk-landscaper"
    assert prov["rl:governanceFunction"] == "evaluate"
    assert prov["rl:aimsActivity"] == ["aimsA6", "aimsA8"]
    assert prov["rl:reviewStatus"] == "draft"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_serialize.py::test_envelope_metadata tests/test_serialize.py::test_provenance_serializes -v`
Expected: 2 FAILED

- [ ] **Step 4: Implement envelope metadata and provenance serialization**

Add to `landscape_to_jsonld` in `serialize.py`, after the `rl:hasRiskCard` line:

```python
    if landscape.timestamp:
        doc["rl:timestamp"] = landscape.timestamp
    if landscape.model:
        doc["rl:model"] = landscape.model
    if landscape.selected_domains:
        doc["rl:selectedDomains"] = landscape.selected_domains
    if landscape.framework_coverage:
        doc["rl:frameworkCoverage"] = landscape.framework_coverage
    if landscape.policy_source:
        doc["rl:policySource"] = {
            k: v for k, v in landscape.policy_source.model_dump().items() if v
        }
    if landscape.knowledge_base:
        kb = landscape.knowledge_base.model_dump()
        doc["rl:knowledgeBase"] = {k: v for k, v in kb.items() if v}
    if landscape.provenance:
        doc["rl:provenance"] = _serialize_provenance(landscape.provenance)
```

Add provenance helper:

```python
def _serialize_provenance(prov) -> dict:
    node: dict = {}
    if prov.produced_by:
        node["rl:producedBy"] = prov.produced_by
    if prov.governance_function:
        node["rl:governanceFunction"] = prov.governance_function
    if prov.aims_activities:
        node["rl:aimsActivity"] = prov.aims_activities
    if prov.reviewed_by:
        node["rl:reviewedBy"] = prov.reviewed_by
    if prov.review_status:
        node["rl:reviewStatus"] = prov.review_status
    return node
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/test_serialize.py -v`
Expected: 15 PASSED

- [ ] **Step 6: Commit**

```bash
git add src/risk_landscaper/serialize.py tests/test_serialize.py
git commit -m "Add envelope metadata and governance provenance serialization"
```

---

### Task 6: Turtle output via rdflib

**Files:**
- Modify: `tests/test_serialize.py`
- Modify: `src/risk_landscaper/serialize.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `[rdf]` optional dependency to pyproject.toml**

Add to `[project.optional-dependencies]`:

```toml
rdf = ["rdflib>=7.0"]
```

- [ ] **Step 2: Write test — turtle output parses and contains expected triples (skip if no rdflib)**

```python
def test_turtle_output(tmp_path):
    rdflib = pytest.importorskip("rdflib")
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[
            RiskCard(
                risk_id="test-risk", risk_name="Test Risk",
                consequences=[
                    RiskConsequence(description="Bad outcome", severity="high"),
                ],
            ),
        ],
    )
    from risk_landscaper.serialize import landscape_to_turtle
    ttl = landscape_to_turtle(landscape)
    assert isinstance(ttl, str)
    assert len(ttl) > 0
    g = rdflib.Graph()
    g.parse(data=ttl, format="turtle")
    assert len(g) > 0
    airo_ns = rdflib.Namespace("https://w3id.org/airo#")
    risk_type_triples = list(g.triples((None, rdflib.RDF.type, airo_ns.Risk)))
    assert len(risk_type_triples) == 1
```

Add `import pytest` at the top of the test file.

- [ ] **Step 3: Write test — ImportError with helpful message when rdflib not available**

```python
from unittest.mock import patch
import builtins

def test_turtle_without_rdflib_raises():
    original_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "rdflib":
            raise ImportError("No module named 'rdflib'")
        return original_import(name, *args, **kwargs)

    landscape = RiskLandscape(run_slug="test-run")
    from risk_landscaper.serialize import landscape_to_turtle

    with patch("builtins.__import__", side_effect=mock_import):
        with pytest.raises(ImportError, match="rdflib"):
            landscape_to_turtle(landscape)
```

- [ ] **Step 4: Implement `landscape_to_turtle`**

Add to `serialize.py`:

```python
def landscape_to_turtle(landscape: RiskLandscape) -> str:
    try:
        import rdflib
    except ImportError:
        raise ImportError(
            "Turtle serialization requires rdflib. "
            "Install it with: pip install 'risk-landscaper[rdf]'"
        )
    doc = landscape_to_jsonld(landscape)
    g = rdflib.Graph()
    g.parse(data=json.dumps(doc), format="json-ld")
    return g.serialize(format="turtle")
```

Add `import json` at top of `serialize.py`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_serialize.py -v`
Expected: all PASSED (turtle tests may skip if rdflib not installed)

- [ ] **Step 6: Install rdflib and run turtle tests**

Run: `uv add --optional rdf "rdflib>=7.0" && uv run pytest tests/test_serialize.py::test_turtle_output -v`
Expected: PASSED

- [ ] **Step 7: Commit**

```bash
git add src/risk_landscaper/serialize.py tests/test_serialize.py pyproject.toml
git commit -m "Add Turtle output via optional rdflib dependency"
```

---

### Task 7: CLI `export` subcommand

**Files:**
- Modify: `src/risk_landscaper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test — export subcommand writes JSON-LD file**

```python
# Add to tests/test_cli.py
import yaml

def test_export_jsonld(tmp_path):
    from risk_landscaper.models import RiskLandscape, RiskCard
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[RiskCard(risk_id="test-risk", risk_name="Test Risk")],
    )
    yaml_file = tmp_path / "risk-landscape.yaml"
    yaml_file.write_text(yaml.dump(landscape.model_dump(), default_flow_style=False))

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["export", str(yaml_file), "--format", "jsonld", "--output", str(out_dir)])
    assert result.exit_code == 0
    jsonld_path = out_dir / "risk-landscape.jsonld"
    assert jsonld_path.exists()
    data = json.loads(jsonld_path.read_text())
    assert "@context" in data
    assert data["rl:hasRiskCard"][0]["@id"] == "nexus:test-risk"
```

- [ ] **Step 2: Write failing test — export defaults to jsonld format**

```python
def test_export_default_format(tmp_path):
    from risk_landscaper.models import RiskLandscape
    landscape = RiskLandscape(run_slug="test-run")
    yaml_file = tmp_path / "risk-landscape.yaml"
    yaml_file.write_text(yaml.dump(landscape.model_dump(), default_flow_style=False))

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["export", str(yaml_file), "--output", str(out_dir)])
    assert result.exit_code == 0
    assert (out_dir / "risk-landscape.jsonld").exists()
```

- [ ] **Step 3: Write failing test — export nonexistent file**

```python
def test_export_missing_file():
    result = runner.invoke(app, ["export", "/nonexistent/file.yaml", "--output", "/tmp/out"])
    assert result.exit_code != 0
    assert "does not exist" in result.output
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::test_export_jsonld tests/test_cli.py::test_export_default_format tests/test_cli.py::test_export_missing_file -v`
Expected: 3 FAILED — `No such command 'export'`

- [ ] **Step 5: Implement `export` subcommand**

Add to `cli.py`:

```python
@app.command()
def export(
    input_file: Path = typer.Argument(..., help="Risk landscape YAML file to convert"),
    output: Path = typer.Option(..., "--output", "-o", help="Output directory"),
    fmt: str = typer.Option("jsonld", "--format", "-f", help="Output format: jsonld or turtle"),
):
    """Export a risk landscape to JSON-LD or Turtle format."""
    if not input_file.exists():
        typer.echo(f"Error: {input_file} does not exist", err=True)
        raise typer.Exit(1)

    from risk_landscaper.models import RiskLandscape
    from risk_landscaper.serialize import landscape_to_jsonld

    raw = yaml.safe_load(input_file.read_text())
    landscape = RiskLandscape(**raw)

    output.mkdir(parents=True, exist_ok=True)

    if fmt == "turtle":
        from risk_landscaper.serialize import landscape_to_turtle
        ttl = landscape_to_turtle(landscape)
        out_path = output / "risk-landscape.ttl"
        out_path.write_text(ttl)
        typer.echo(f"Turtle written to {out_path}")
    else:
        doc = landscape_to_jsonld(landscape)
        out_path = output / "risk-landscape.jsonld"
        out_path.write_text(json.dumps(doc, indent=2))
        typer.echo(f"JSON-LD written to {out_path}")
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all PASSED

- [ ] **Step 7: Commit**

```bash
git add src/risk_landscaper/cli.py tests/test_cli.py
git commit -m "Add export subcommand for JSON-LD and Turtle output"
```

---

### Task 8: `--format` flag on `run` command

**Files:**
- Modify: `src/risk_landscaper/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing test — `--format jsonld` produces additional file**

This test mocks the pipeline to avoid needing a real LLM/Nexus. It verifies that when `--format jsonld` is passed, the run command writes a `.jsonld` file.

```python
def test_run_format_jsonld_flag(tmp_path):
    """Verify --format jsonld is accepted as a valid CLI option."""
    result = runner.invoke(app, [
        "run", "/nonexistent/policy.json",
        "--output", str(tmp_path / "out"),
        "--base-url", "http://localhost:8000/v1",
        "--model", "test",
        "--nexus-base-dir", "/tmp/nexus",
        "--format", "jsonld",
    ])
    # Will fail because policy file doesn't exist, but --format should be accepted
    assert "no such option" not in result.output.lower()
    assert "does not exist" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_run_format_jsonld_flag -v`
Expected: FAIL — `No such option: --format`

- [ ] **Step 3: Add `--format` parameter to `run` command**

Add the parameter to the `run` function signature in `cli.py`:

```python
    output_format: str = typer.Option("yaml", "--format", "-f", help="Additional output format: yaml (default), jsonld, turtle"),
```

Add after the landscape YAML is written (after line 277 in current cli.py):

```python
    if output_format in ("jsonld", "turtle"):
        from risk_landscaper.serialize import landscape_to_jsonld
        doc = landscape_to_jsonld(landscape)
        jsonld_path = output / "risk-landscape.jsonld"
        jsonld_path.write_text(json.dumps(doc, indent=2))
        typer.echo(f"JSON-LD written to {jsonld_path}")
        if output_format == "turtle":
            from risk_landscaper.serialize import landscape_to_turtle
            ttl = landscape_to_turtle(landscape)
            ttl_path = output / "risk-landscape.ttl"
            ttl_path.write_text(ttl)
            typer.echo(f"Turtle written to {ttl_path}")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: all PASSED

- [ ] **Step 5: Commit**

```bash
git add src/risk_landscaper/cli.py tests/test_cli.py
git commit -m "Add --format flag to run command for JSON-LD/Turtle output"
```

---

### Task 9: Run full test suite and update docs

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -v`
Expected: all tests PASSED, no regressions

- [ ] **Step 2: Update CHANGELOG.md**

Add entry under a new `## [Unreleased]` section (or the current section if one exists):

```markdown
### Added

- **JSON-LD serialization** — `landscape_to_jsonld()` emits RiskLandscape as valid JSON-LD using AIRO, VAIR, DPV, and Nexus ontology IRIs. Composable with AIROO advisory data foundation triples via shared `nexus:` identifiers.
- **Turtle output** — `landscape_to_turtle()` converts to Turtle format via optional `rdflib` dependency (`pip install 'risk-landscaper[rdf]'`).
- **`export` subcommand** — `risk-landscaper export risk-landscape.yaml --format jsonld` converts existing output files post-hoc.
- **`--format` flag on `run`** — `--format jsonld` or `--format turtle` writes additional serialization alongside YAML output.
```

- [ ] **Step 3: Update work-tracker.md**

Mark the JSON-LD serialization item as done in `docs/work-tracker.md` and add it to the Done section if not already tracked.

- [ ] **Step 4: Commit**

```bash
git add CHANGELOG.md docs/work-tracker.md
git commit -m "Update changelog and work tracker for JSON-LD serialization"
```
