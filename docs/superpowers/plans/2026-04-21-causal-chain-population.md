# Causal Chain Population Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate the empty causal chain fields on RiskCards (risk_sources, consequences, impacts, incidents) using free structural enrichment from Nexus data plus LLM-assisted synthesis for primary-relevance risks.

**Architecture:** Two-phase enrichment. Phase 1 runs inside `build_landscape` with no LLM calls — incident linking, source_type inference from risk_type, control_type inference from action keywords. Phase 2 is a new `enrich_chains` pipeline stage that calls the LLM per primary-relevance risk to synthesize full causal chains. Phase 2 is optional (`--skip-chain-enrichment`).

**Tech Stack:** Pydantic, Instructor, Jinja2, ThreadPoolExecutor, pytest

**Spec:** `docs/superpowers/specs/2026-04-21-causal-chain-population-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `src/risk_landscaper/stages/build_landscape.py` | Modify — add `_infer_control_type`, `_infer_control_targets`, `_infer_source_type`, `_incidents_to_refs`; accept `risk_incidents` param |
| `src/risk_landscaper/stages/enrich_chains.py` | Create — LLM causal chain synthesis stage |
| `src/risk_landscaper/templates/prompts/enrich_chains_system.j2` | Create — system prompt for chain synthesis |
| `src/risk_landscaper/templates/prompts/enrich_chains_user.j2` | Create — user prompt for chain synthesis |
| `src/risk_landscaper/cli.py` | Modify — fetch incidents, compute primary risk set, call enrich_chains, add `--skip-chain-enrichment` flag |
| `tests/test_build_landscape.py` | Modify — tests for incident linking, source_type, control_type |
| `tests/test_enrich_chains.py` | Create — tests for enrich_chains stage |
| `CHANGELOG.md` | Modify — update |
| `docs/work-tracker.md` | Modify — mark items done |

---

### Task 1: Control Type Inference

Add keyword-based `control_type` and `targets` inference to `build_landscape.py`. Currently `_actions_to_controls` creates `RiskControl(description=desc)` with no type — we'll infer the type from action text.

**Files:**
- Modify: `src/risk_landscaper/stages/build_landscape.py`
- Test: `tests/test_build_landscape.py`

- [ ] **Step 1: Write failing tests for control type inference**

Add to `tests/test_build_landscape.py`:

```python
from risk_landscaper.stages.build_landscape import _infer_control_type, _infer_control_targets


def test_infer_control_type_detect():
    assert _infer_control_type("Monitor output for harmful content") == "detect"
    assert _infer_control_type("Audit model decisions regularly") == "detect"


def test_infer_control_type_evaluate():
    assert _infer_control_type("Evaluate model fairness with benchmarks") == "evaluate"
    assert _infer_control_type("Assess bias across demographic groups") == "evaluate"


def test_infer_control_type_mitigate():
    assert _infer_control_type("Filter offensive content from responses") == "mitigate"
    assert _infer_control_type("Reduce exposure to sensitive data") == "mitigate"


def test_infer_control_type_eliminate():
    assert _infer_control_type("Prevent unauthorized access to the model") == "eliminate"
    assert _infer_control_type("Block generation of harmful instructions") == "eliminate"


def test_infer_control_type_none():
    assert _infer_control_type("Apply best practices for AI safety") is None
    assert _infer_control_type("") is None


def test_infer_control_targets_source():
    assert _infer_control_targets("Validate training data quality") == "source"
    assert _infer_control_targets("Sanitize input prompts") == "source"


def test_infer_control_targets_consequence():
    assert _infer_control_targets("Filter output for bias") == "consequence"
    assert _infer_control_targets("Review results before publishing") == "consequence"


def test_infer_control_targets_default_risk():
    assert _infer_control_targets("Apply guardrails to the model") == "risk"
    assert _infer_control_targets("") == "risk"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_landscape.py::test_infer_control_type_detect -v`
Expected: FAIL with `ImportError: cannot import name '_infer_control_type'`

- [ ] **Step 3: Implement control type and targets inference**

In `src/risk_landscaper/stages/build_landscape.py`, add before `_actions_to_controls`:

```python
_CONTROL_TYPE_KEYWORDS: dict[str, list[str]] = {
    "detect": ["detect", "monitor", "audit", "alert", "log", "track", "scan"],
    "evaluate": ["evaluate", "assess", "benchmark", "test", "measure", "review"],
    "mitigate": ["mitigate", "reduce", "limit", "filter", "moderate", "constrain"],
    "eliminate": ["eliminate", "prevent", "prohibit", "block", "remove", "disable"],
}

_TARGET_KEYWORDS: dict[str, list[str]] = {
    "source": ["source", "data", "input", "training", "dataset"],
    "consequence": ["output", "result", "response", "generation"],
}


def _infer_control_type(description: str) -> str | None:
    lower = description.lower()
    for control_type, keywords in _CONTROL_TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return control_type
    return None


def _infer_control_targets(description: str) -> str:
    lower = description.lower()
    for target, keywords in _TARGET_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return target
    return "risk"
```

Then update `_actions_to_controls`:

```python
def _actions_to_controls(action_descriptions: list[str]) -> list[RiskControl]:
    return [
        RiskControl(
            description=desc,
            control_type=_infer_control_type(desc),
            targets=_infer_control_targets(desc),
        )
        for desc in action_descriptions
        if desc
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_landscape.py -v -k "infer_control"` 
Expected: all 8 tests PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `uv run pytest tests/test_build_landscape.py -v`
Expected: all existing tests still PASS (the `_actions_to_controls` test now gets enriched controls, which is fine — it only checks `description` and `related_actions`)

- [ ] **Step 6: Commit**

```bash
git add src/risk_landscaper/stages/build_landscape.py tests/test_build_landscape.py
git commit -m "Add control type and targets inference from action keywords"
```

---

### Task 2: Source Type Inference

Add `risk_type` → VAIR `source_type` mapping and create a baseline `RiskSource` on every RiskCard during `build_landscape`.

**Files:**
- Modify: `src/risk_landscaper/stages/build_landscape.py`
- Test: `tests/test_build_landscape.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_build_landscape.py`:

```python
from risk_landscaper.stages.build_landscape import _infer_source_type


def test_infer_source_type_data():
    assert _infer_source_type("training-data") == "data"
    assert _infer_source_type("input") == "data"


def test_infer_source_type_model():
    assert _infer_source_type("output") == "model"
    assert _infer_source_type("inference") == "model"
    assert _infer_source_type("agentic") == "model"


def test_infer_source_type_organisational():
    assert _infer_source_type("non-technical") == "organisational"


def test_infer_source_type_none():
    assert _infer_source_type(None) is None
    assert _infer_source_type("unknown-type") is None


def test_build_landscape_populates_baseline_risk_source():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Bias Policy",
            matched_risks=[
                RiskMatch(risk_id="atlas-bias", risk_name="Bias",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-bias": {
            "id": "atlas-bias", "name": "Bias",
            "description": "Model exhibits systematic bias",
            "concern": "Discriminatory outputs affecting users",
            "risk_type": "output",
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert len(card.risk_sources) == 1
    assert card.risk_sources[0].source_type == "model"
    assert "bias" in card.risk_sources[0].description.lower() or "discriminat" in card.risk_sources[0].description.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_landscape.py::test_infer_source_type_data -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement source type inference**

In `src/risk_landscaper/stages/build_landscape.py`, add the import for `RiskSource` at the top:

```python
from risk_landscaper.models import (
    # ... existing imports ...
    RiskSource,
)
```

Add the mapping and function:

```python
_RISK_TYPE_TO_SOURCE_TYPE: dict[str, str] = {
    "training-data": "data",
    "input": "data",
    "output": "model",
    "inference": "model",
    "non-technical": "organisational",
    "agentic": "model",
}


def _infer_source_type(risk_type: str | None) -> str | None:
    if not risk_type:
        return None
    return _RISK_TYPE_TO_SOURCE_TYPE.get(risk_type)
```

Then in the `build_risk_landscape` function, inside the risk loop, after setting `descriptors`, add baseline risk_sources to the `RiskCard` constructor:

```python
source_type = _infer_source_type(details.get("risk_type"))
baseline_source = (
    [RiskSource(
        description=details.get("concern") or details.get("description") or "",
        source_type=source_type,
    )]
    if details.get("concern") or details.get("description")
    else []
)
```

Then pass `risk_sources=baseline_source` into the `RiskCard(...)` constructor.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_landscape.py -v -k "source_type or baseline_risk_source"`
Expected: all 4 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/test_build_landscape.py -v`
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/risk_landscaper/stages/build_landscape.py tests/test_build_landscape.py
git commit -m "Add source type inference from risk_type and baseline RiskSource"
```

---

### Task 3: Incident Linking

Fetch incidents from Nexus in `cli.py`, pass them through to `build_landscape`, map to `RiskIncidentRef` objects.

**Files:**
- Modify: `src/risk_landscaper/stages/build_landscape.py`
- Modify: `src/risk_landscaper/cli.py`
- Test: `tests/test_build_landscape.py`

- [ ] **Step 1: Write failing tests for incident-to-ref mapping**

Add to `tests/test_build_landscape.py`:

```python
from risk_landscaper.stages.build_landscape import _incidents_to_refs
from risk_landscaper.models import RiskIncidentRef


def test_incidents_to_refs_basic():
    raw = [
        {
            "name": "AI-based Biological Attacks",
            "description": "LLMs could help plan biological attacks",
            "source_uri": "https://example.com/incident",
            "hasStatus": "Concluded",
        },
    ]
    refs = _incidents_to_refs(raw)
    assert len(refs) == 1
    assert refs[0].name == "AI-based Biological Attacks"
    assert refs[0].description == "LLMs could help plan biological attacks"
    assert refs[0].source_uri == "https://example.com/incident"
    assert refs[0].status == "concluded"


def test_incidents_to_refs_missing_fields():
    raw = [{"name": "Minimal Incident"}]
    refs = _incidents_to_refs(raw)
    assert len(refs) == 1
    assert refs[0].name == "Minimal Incident"
    assert refs[0].description is None
    assert refs[0].source_uri is None
    assert refs[0].status is None


def test_incidents_to_refs_empty():
    assert _incidents_to_refs([]) == []
    assert _incidents_to_refs(None) == []


def test_build_landscape_with_incidents():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Safety",
            matched_risks=[
                RiskMatch(risk_id="atlas-dangerous-use", risk_name="Dangerous use",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-dangerous-use": {
            "id": "atlas-dangerous-use", "name": "Dangerous use",
            "description": "AI used for dangerous purposes",
        },
    }
    risk_incidents = {
        "atlas-dangerous-use": [
            {
                "name": "Bioweapon planning",
                "description": "LLM assisted in planning biological attack",
                "source_uri": "https://example.com",
                "hasStatus": "Ongoing",
            },
        ],
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        risk_incidents=risk_incidents,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert len(card.incidents) == 1
    assert card.incidents[0].name == "Bioweapon planning"
    assert card.incidents[0].status == "ongoing"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_landscape.py::test_incidents_to_refs_basic -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement incident linking in build_landscape**

In `src/risk_landscaper/stages/build_landscape.py`, add `RiskIncidentRef` to imports:

```python
from risk_landscaper.models import (
    # ... existing imports ...
    RiskIncidentRef,
)
```

Add the mapping function:

```python
_STATUS_MAP = {
    "Ongoing": "ongoing",
    "Concluded": "concluded",
    "Mitigated": "mitigated",
    "Halted": "halted",
    "NearMiss": "near_miss",
}


def _incidents_to_refs(raw_incidents: list[dict] | None) -> list[RiskIncidentRef]:
    if not raw_incidents:
        return []
    return [
        RiskIncidentRef(
            name=inc.get("name", ""),
            description=inc.get("description"),
            source_uri=inc.get("source_uri"),
            status=_STATUS_MAP.get(inc.get("hasStatus", ""), inc.get("hasStatus", "").lower() if inc.get("hasStatus") else None),
        )
        for inc in raw_incidents
    ]
```

Add `risk_incidents` parameter to `build_risk_landscape`:

```python
def build_risk_landscape(
    mappings: list[PolicyRiskMapping],
    risk_details_cache: dict[str, dict],
    related_risks: dict[str, list[dict]] | None = None,
    risk_actions: dict[str, list[str]] | None = None,
    risk_incidents: dict[str, list[dict]] | None = None,  # NEW
    # ... rest of params unchanged
) -> RiskLandscape:
    related_risks = related_risks or {}
    risk_actions = risk_actions or {}
    risk_incidents = risk_incidents or {}
```

In the risk loop, fetch incidents and pass to `RiskCard`:

```python
incidents = _incidents_to_refs(risk_incidents.get(rm.risk_id))
```

Add `incidents=incidents` to the `RiskCard(...)` constructor.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_landscape.py -v -k "incident"`
Expected: all 4 tests PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest tests/test_build_landscape.py -v`
Expected: all tests PASS (existing tests don't pass `risk_incidents`, so it defaults to `{}`)

- [ ] **Step 6: Wire incident fetching in cli.py**

In `src/risk_landscaper/cli.py`, in the `run` function, after `map_risks` returns and before `build_risk_landscape`, add:

```python
    # --- Fetch incidents for matched risks ---
    from ai_atlas_nexus import AIAtlasNexus
    nexus = AIAtlasNexus(base_dir=nexus_base_dir)
    risk_incidents: dict[str, list[dict]] = {}
    for rid in risk_details:
        incidents = nexus.get_related_risk_incidents(risk_id=rid)
        if incidents:
            risk_incidents[rid] = [
                {
                    "name": inc.name,
                    "description": inc.description,
                    "source_uri": getattr(inc, "source_uri", None),
                    "hasStatus": getattr(inc, "hasStatus", None),
                }
                for inc in incidents
            ]
    if risk_incidents:
        total_inc = sum(len(v) for v in risk_incidents.values())
        typer.echo(f"  {total_inc} incident(s) linked to {len(risk_incidents)} risk(s)")
```

Then pass `risk_incidents=risk_incidents` to `build_risk_landscape(...)`.

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/risk_landscaper/stages/build_landscape.py src/risk_landscaper/cli.py tests/test_build_landscape.py
git commit -m "Add incident linking from Nexus to RiskCards"
```

---

### Task 4: Prompt Templates for Chain Synthesis

Create the Jinja2 system and user prompts for the LLM causal chain synthesis stage.

**Files:**
- Create: `src/risk_landscaper/templates/prompts/enrich_chains_system.j2`
- Create: `src/risk_landscaper/templates/prompts/enrich_chains_user.j2`

- [ ] **Step 1: Create system prompt template**

Create `src/risk_landscaper/templates/prompts/enrich_chains_system.j2`:

```
You are an AI risk analyst producing structured causal chains for AI risk documentation following the AIRO ontology (ISO 31000).

For each risk, produce a causal chain: RiskSource → Risk → Consequence → Impact.

## Source Types (VAIR vocabulary)
- data: training data quality, data poisoning, data leakage, biased datasets
- model: architectural limitations, hallucination, mode collapse, emergent behaviors
- attack: adversarial inputs, prompt injection, evasion, model extraction
- organisational: governance gaps, inadequate oversight, deployment without safeguards
- performance: degradation, drift, out-of-distribution failure, latency issues

## Impact Areas (AIRO)
health, safety, fundamental_rights, non_discrimination, environment, democracy, rule_of_law

## Harm Types (Shelby+)
- representational: stereotyping, erasure, demeaning portrayals
- allocative: unfair resource/opportunity distribution
- quality_of_service: degraded service for specific groups
- interpersonal: harassment, manipulation, deception
- societal: erosion of trust, democratic harm, environmental harm
- legal: regulatory violations, liability exposure

## Likelihood/Severity Scale (ISO 31000)
very_low, low, medium, high, very_high

## Instructions
- Produce 1-3 risk sources, 1-3 consequences, and 1-2 impacts per risk
- Each source should identify a distinct causal factor
- Consequences are direct outcomes of the risk materializing
- Impacts describe harm to people or society, with affected stakeholders
- materialization_conditions: one sentence describing when/how this risk becomes real harm
- risk_level: overall assessed risk level considering likelihood and severity across the chain
- Be specific to the risk and policy context provided — avoid generic statements
```

- [ ] **Step 2: Create user prompt template**

Create `src/risk_landscaper/templates/prompts/enrich_chains_user.j2`:

```
Analyze this AI risk and produce its causal chain.

## Risk
Name: {{ risk_name }}
Description: {{ risk_description }}
{% if risk_concern %}Concern: {{ risk_concern }}{% endif %}
{% if risk_type %}Type: {{ risk_type }}{% endif %}
{% if source_type_hint %}Source type hint: {{ source_type_hint }}{% endif %}

## Related Policies
{% for p in policies %}
- {{ p.concept }}: {{ p.definition }}
{% endfor %}
{% if not policies %}
No specific policies provided.
{% endif %}
```

- [ ] **Step 3: Verify templates render**

Run:

```bash
uv run python -c "
from risk_landscaper.prompts import render_prompt
msgs = render_prompt('enrich_chains', {
    'risk_name': 'Bias',
    'risk_description': 'Model exhibits bias',
    'risk_concern': 'Discriminatory outputs',
    'risk_type': 'output',
    'source_type_hint': 'model',
    'policies': [{'concept': 'Fairness', 'definition': 'Equal treatment'}],
})
for m in msgs:
    print(f'--- {m[\"role\"]} ---')
    print(m['content'][:200])
"
```

Expected: prints system and user messages without errors

- [ ] **Step 4: Commit**

```bash
git add src/risk_landscaper/templates/prompts/enrich_chains_system.j2 src/risk_landscaper/templates/prompts/enrich_chains_user.j2
git commit -m "Add prompt templates for causal chain synthesis"
```

---

### Task 5: Enrich Chains Stage

New `stages/enrich_chains.py` — calls the LLM per primary-relevance risk to synthesize causal chains, then merges results onto existing RiskCards.

**Files:**
- Create: `src/risk_landscaper/stages/enrich_chains.py`
- Create: `tests/test_enrich_chains.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_enrich_chains.py`:

```python
import pytest
from unittest.mock import MagicMock, patch
from risk_landscaper.models import (
    RiskCard, RiskLandscape, RiskSource, PolicyRiskMapping, RiskMatch,
)
from risk_landscaper.llm import LLMConfig


@pytest.fixture
def sample_landscape():
    return RiskLandscape(
        model="test-model",
        timestamp="t",
        run_slug="test",
        risks=[
            RiskCard(
                risk_id="atlas-bias",
                risk_name="Bias",
                risk_description="Model exhibits systematic bias",
                risk_concern="Discriminatory outputs affecting users",
                risk_type="output",
                risk_sources=[RiskSource(description="Discriminatory outputs", source_type="model")],
                related_policies=["Fairness Policy"],
            ),
            RiskCard(
                risk_id="atlas-hallucination",
                risk_name="Hallucination",
                risk_description="Model generates false information",
                risk_concern="Incorrect outputs",
                risk_type="output",
                risk_sources=[RiskSource(description="Incorrect outputs", source_type="model")],
                related_policies=["Accuracy Policy"],
            ),
        ],
        policy_mappings=[
            PolicyRiskMapping(
                policy_concept="Fairness Policy",
                matched_risks=[
                    RiskMatch(risk_id="atlas-bias", risk_name="Bias",
                              relevance="primary", justification="test"),
                ],
            ),
            PolicyRiskMapping(
                policy_concept="Accuracy Policy",
                matched_risks=[
                    RiskMatch(risk_id="atlas-hallucination", risk_name="Hallucination",
                              relevance="supporting", justification="test"),
                ],
            ),
        ],
    )


def test_collect_primary_risk_ids(sample_landscape):
    from risk_landscaper.stages.enrich_chains import _collect_primary_risk_ids
    primary = _collect_primary_risk_ids(sample_landscape.policy_mappings)
    assert primary == {"atlas-bias"}


def test_collect_primary_risk_ids_empty():
    from risk_landscaper.stages.enrich_chains import _collect_primary_risk_ids
    assert _collect_primary_risk_ids([]) == set()


def test_build_policy_context(sample_landscape):
    from risk_landscaper.stages.enrich_chains import _build_policy_context
    policies = [
        MagicMock(policy_concept="Fairness Policy", concept_definition="Equal treatment for all users"),
    ]
    ctx = _build_policy_context("atlas-bias", sample_landscape.policy_mappings, policies)
    assert len(ctx) == 1
    assert ctx[0]["concept"] == "Fairness Policy"
    assert ctx[0]["definition"] == "Equal treatment for all users"


def test_enrich_chains_skips_non_primary(sample_landscape):
    from risk_landscaper.stages.enrich_chains import enrich_chains
    config = LLMConfig(base_url="http://localhost:8000/v1", model="test-model")
    client = MagicMock()

    enrich_chains(sample_landscape, [], client, config)

    # hallucination is "supporting", so only bias should trigger LLM call
    assert client.chat.completions.create.call_count == 1


def test_merge_chain_onto_card():
    from risk_landscaper.stages.enrich_chains import _merge_chain
    from risk_landscaper.stages.enrich_chains import (
        _CausalChain, _CausalChainSource, _CausalChainConsequence, _CausalChainImpact,
    )

    card = RiskCard(
        risk_id="r1", risk_name="R",
        risk_sources=[RiskSource(description="existing", source_type="model")],
    )
    chain = _CausalChain(
        risk_sources=[
            _CausalChainSource(description="Biased training data", source_type="data", likelihood="high"),
        ],
        consequences=[
            _CausalChainConsequence(description="Discriminatory outputs", likelihood="medium", severity="high"),
        ],
        impacts=[
            _CausalChainImpact(
                description="Users receive unfair treatment",
                severity="high", area="non_discrimination",
                affected_stakeholders=["end users"], harm_type="allocative",
            ),
        ],
        materialization_conditions="When model processes data about protected groups",
        risk_level="high",
    )
    _merge_chain(card, chain)

    assert len(card.risk_sources) == 1
    assert card.risk_sources[0].description == "Biased training data"
    assert card.risk_sources[0].source_type == "data"
    assert len(card.consequences) == 1
    assert len(card.impacts) == 1
    assert card.impacts[0].harm_type == "allocative"
    assert card.materialization_conditions == "When model processes data about protected groups"
    assert card.risk_level == "high"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_enrich_chains.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'risk_landscaper.stages.enrich_chains'`

- [ ] **Step 3: Implement enrich_chains stage**

Create `src/risk_landscaper/stages/enrich_chains.py`:

```python
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Literal

import instructor
from pydantic import BaseModel

from risk_landscaper import debug
from risk_landscaper.llm import LLMConfig
from risk_landscaper.models import (
    Policy,
    PolicyRiskMapping,
    RiskCard,
    RiskConsequence,
    RiskImpact,
    RiskLandscape,
    RiskSource,
)
from risk_landscaper.prompts import render_prompt

logger = logging.getLogger(__name__)

_LIKELIHOOD = Literal["very_low", "low", "medium", "high", "very_high"]
_SEVERITY = Literal["very_low", "low", "medium", "high", "very_high"]


class _CausalChainSource(BaseModel):
    description: str
    source_type: Literal["data", "model", "attack", "organisational", "performance"]
    likelihood: _LIKELIHOOD | None = None


class _CausalChainConsequence(BaseModel):
    description: str
    likelihood: _LIKELIHOOD | None = None
    severity: _SEVERITY | None = None


class _CausalChainImpact(BaseModel):
    description: str
    severity: _SEVERITY | None = None
    area: str | None = None
    affected_stakeholders: list[str] = []
    harm_type: Literal[
        "representational", "allocative", "quality_of_service",
        "interpersonal", "societal", "legal",
    ] | None = None


class _CausalChain(BaseModel):
    risk_sources: list[_CausalChainSource]
    consequences: list[_CausalChainConsequence]
    impacts: list[_CausalChainImpact]
    materialization_conditions: str
    risk_level: _LIKELIHOOD


def _collect_primary_risk_ids(mappings: list[PolicyRiskMapping]) -> set[str]:
    return {
        rm.risk_id
        for m in mappings
        for rm in m.matched_risks
        if rm.relevance == "primary"
    }


def _build_policy_context(
    risk_id: str,
    mappings: list[PolicyRiskMapping],
    policies: list[Policy],
) -> list[dict[str, str]]:
    related_concepts = {
        m.policy_concept
        for m in mappings
        if any(rm.risk_id == risk_id for rm in m.matched_risks)
    }
    policy_by_concept = {p.policy_concept: p for p in policies}
    return [
        {"concept": c, "definition": policy_by_concept[c].concept_definition}
        for c in sorted(related_concepts)
        if c in policy_by_concept
    ]


def _merge_chain(card: RiskCard, chain: _CausalChain) -> None:
    card.risk_sources = [
        RiskSource(
            description=s.description,
            source_type=s.source_type,
            likelihood=s.likelihood,
        )
        for s in chain.risk_sources
    ]
    card.consequences = [
        RiskConsequence(
            description=c.description,
            likelihood=c.likelihood,
            severity=c.severity,
        )
        for c in chain.consequences
    ]
    card.impacts = [
        RiskImpact(
            description=i.description,
            severity=i.severity,
            area=i.area,
            affected_stakeholders=i.affected_stakeholders,
            harm_type=i.harm_type,
        )
        for i in chain.impacts
    ]
    card.materialization_conditions = chain.materialization_conditions
    card.risk_level = chain.risk_level


def _enrich_single_risk(
    card: RiskCard,
    policy_context: list[dict[str, str]],
    client: instructor.Instructor,
    config: LLMConfig,
    report=None,
) -> None:
    source_type_hint = (
        card.risk_sources[0].source_type if card.risk_sources else None
    )
    messages = render_prompt("enrich_chains", {
        "risk_name": card.risk_name,
        "risk_description": card.risk_description or "",
        "risk_concern": card.risk_concern or "",
        "risk_type": card.risk_type or "",
        "source_type_hint": source_type_hint or "",
        "policies": policy_context,
    })
    chain = client.chat.completions.create(
        model=config.model,
        response_model=_CausalChain,
        messages=messages,
        temperature=config.temperature,
        max_retries=config.max_retries,
        max_tokens=config.max_tokens,
    )
    debug.log_call("enrich_chains", messages, chain, context={
        "risk_id": card.risk_id,
    })
    _merge_chain(card, chain)

    if report:
        report.events.append({
            "stage": "enrich_chains",
            "event": "chain_synthesized",
            "risk_id": card.risk_id,
            "sources": len(chain.risk_sources),
            "consequences": len(chain.consequences),
            "impacts": len(chain.impacts),
            "risk_level": chain.risk_level,
        })


def enrich_chains(
    landscape: RiskLandscape,
    policies: list[Policy],
    client: instructor.Instructor,
    config: LLMConfig,
    report=None,
) -> None:
    primary_ids = _collect_primary_risk_ids(landscape.policy_mappings)
    if not primary_ids:
        logger.info("enrich_chains: no primary-relevance risks, skipping")
        return

    cards_to_enrich = [c for c in landscape.risks if c.risk_id in primary_ids]
    logger.info(
        "enrich_chains: enriching %d/%d risks (primary relevance)",
        len(cards_to_enrich), len(landscape.risks),
    )

    def _process(card: RiskCard) -> None:
        policy_ctx = _build_policy_context(
            card.risk_id, landscape.policy_mappings, policies,
        )
        _enrich_single_risk(card, policy_ctx, client, config, report)

    max_workers = min(config.max_concurrent, len(cards_to_enrich))
    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            list(executor.map(_process, cards_to_enrich))
    else:
        for card in cards_to_enrich:
            _process(card)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_enrich_chains.py -v`
Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/risk_landscaper/stages/enrich_chains.py tests/test_enrich_chains.py
git commit -m "Add enrich_chains stage for LLM causal chain synthesis"
```

---

### Task 6: CLI Integration

Wire the new `enrich_chains` stage into the pipeline and add the `--skip-chain-enrichment` flag.

**Files:**
- Modify: `src/risk_landscaper/cli.py`

- [ ] **Step 1: Add CLI flag and stage call**

In `src/risk_landscaper/cli.py`, add the `--skip-chain-enrichment` parameter to the `run` function:

```python
    skip_chain_enrichment: bool = typer.Option(False, "--skip-chain-enrichment", help="Skip LLM causal chain enrichment"),
```

After the `build_risk_landscape` call and before writing the landscape output, add:

```python
    # --- Stage 5: Enrich causal chains ---
    if not skip_chain_enrichment:
        from risk_landscaper.stages.enrich_chains import enrich_chains
        primary_count = sum(
            1 for m in mappings for rm in m.matched_risks if rm.relevance == "primary"
        )
        typer.echo(f"Enriching causal chains for {primary_count} primary-relevance risks...")
        enrich_chains(landscape, profile.policies, client, config, report=report)
        report.stages_completed.append("enrich_chains")
        enriched = sum(1 for r in landscape.risks if r.consequences)
        typer.echo(f"  {enriched} risk(s) enriched with causal chains")
    else:
        typer.echo("Skipping causal chain enrichment (--skip-chain-enrichment)")
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/risk_landscaper/cli.py
git commit -m "Wire enrich_chains stage into CLI pipeline"
```

---

### Task 7: Documentation Updates

Update CHANGELOG.md and work-tracker.md to reflect completed work.

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/work-tracker.md`

- [ ] **Step 1: Update CHANGELOG.md**

Add under `## [0.2.0]`, in the `### Added` section:

```markdown
- **Causal chain population** — RiskCards now populated with `risk_sources`, `consequences`, `impacts`, and `incidents`.
  - Incident linking from AI Atlas Nexus knowledge graph (`get_related_risk_incidents`).
  - Source type inference from `risk_type` → VAIR vocabulary (`data`, `model`, `attack`, `organisational`, `performance`).
  - Control type and targets inference from action description keywords.
  - LLM-assisted causal chain synthesis for primary-relevance risks (new `enrich_chains` pipeline stage). Skippable with `--skip-chain-enrichment`.
```

- [ ] **Step 2: Update work-tracker.md**

In `docs/work-tracker.md`, move completed items from Remaining to Done:

Under `## Done`, add a new section:

```markdown
### Causal Chain Population

- [x] Source type inference from `risk_type` → VAIR-inspired `source_type`
- [x] Control type inference from action description keywords
- [x] Control targets inference (source/risk/consequence)
- [x] Incident linking via Nexus `get_related_risk_incidents()`
- [x] LLM-assisted causal chain synthesis (primary-relevance risks only)
- [x] Baseline RiskSource creation from risk description + inferred source_type
```

Under `## Remaining > Causal Chain Population`, update to show what's done:

```markdown
### Causal Chain Population

- [x] **VAIR vocabulary matching** — source type inference from `risk_type`. Full VAIR vocabulary matching deferred (no VAIR data in Nexus).
- [x] **LLM-assisted chain synthesis** — `enrich_chains` stage for primary-relevance risks.
- [x] **Incident linking** — `get_related_risk_incidents()` wired into `build_landscape`.
- [ ] **Evaluation linking** — wire `EvaluationRef` population from lm-eval results or other eval sources.
```

Under `## Remaining > Control Enrichment`, update:

```markdown
### Control Enrichment

- [x] **Control type inference** — keyword-based from action description text.
- [x] **Control targets** — inferred from action keywords (source/risk/consequence).
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md docs/work-tracker.md
git commit -m "Update changelog and work tracker for causal chain population"
```
