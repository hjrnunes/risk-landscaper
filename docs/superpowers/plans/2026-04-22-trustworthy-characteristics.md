# Trustworthy Characteristics Inference — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate `RiskCard.trustworthy_characteristics` with ISO/IEC 24028 characteristics inferred from VAIR type matches and keyword heuristics during `build_landscape`.

**Architecture:** Add a vendored enumeration of 11 trustworthy characteristics to `vair.py`, each with a mapping from VAIR type IDs and/or keyword patterns. A new `match_trustworthy_characteristics()` function takes the risk text and already-computed VAIR matches, returning matched characteristic names. Wired into `_vair_enrich()` in `build_landscape.py` and passed through to the `RiskCard` constructor.

**Tech Stack:** Python, Pydantic, pytest

---

### Task 1: Add trustworthy characteristic enumeration and matching to `vair.py`

**Files:**
- Modify: `src/risk_landscaper/vair.py`
- Test: `tests/test_vair.py`

- [ ] **Step 1: Write failing tests for VAIR-derived characteristic matching**

Add to `tests/test_vair.py`:

```python
from risk_landscaper.vair import match_trustworthy_characteristics, match_all


def test_trustworthy_fairness_from_vair():
    vair = match_all("biased and discriminatory outputs")
    chars = match_trustworthy_characteristics("biased and discriminatory outputs", vair)
    assert "fairness" in chars


def test_trustworthy_cybersecurity_from_vair():
    vair = match_all("cyberattack exploiting system vulnerability")
    chars = match_trustworthy_characteristics("cyberattack exploiting system vulnerability", vair)
    assert "cybersecurity" in chars


def test_trustworthy_accuracy_from_vair():
    vair = match_all("low accuracy and degraded predictions")
    chars = match_trustworthy_characteristics("low accuracy and degraded predictions", vair)
    assert "accuracy" in chars


def test_trustworthy_robustness_from_vair():
    vair = match_all("decreased robustness under perturbation")
    chars = match_trustworthy_characteristics("decreased robustness under perturbation", vair)
    assert "robustness" in chars


def test_trustworthy_transparency_from_vair():
    vair = match_all("lack of transparency in decision making")
    chars = match_trustworthy_characteristics("lack of transparency in decision making", vair)
    assert "transparency" in chars


def test_trustworthy_safety_from_vair():
    vair = match_all("fatal errors in safety-critical healthcare system")
    chars = match_trustworthy_characteristics("fatal errors in safety-critical healthcare system", vair)
    assert "safety" in chars


def test_trustworthy_accountability_from_vair():
    vair = match_all("overreliance on automated decisions with impaired decision making")
    chars = match_trustworthy_characteristics("overreliance on automated decisions with impaired decision making", vair)
    assert "accountability" in chars


def test_trustworthy_controllability_from_vair():
    vair = match_all("insufficient human oversight measure")
    chars = match_trustworthy_characteristics("insufficient human oversight measure", vair)
    assert "controllability" in chars
```

- [ ] **Step 2: Write failing tests for keyword-based characteristic matching**

Add to `tests/test_vair.py`:

```python
def test_trustworthy_privacy_from_keywords():
    vair = match_all("personal data exposure and privacy breach")
    chars = match_trustworthy_characteristics("personal data exposure and privacy breach", vair)
    assert "privacy" in chars


def test_trustworthy_reliability_from_keywords():
    vair = match_all("system produces inconsistent and unreliable results")
    chars = match_trustworthy_characteristics("system produces inconsistent and unreliable results", vair)
    assert "reliability" in chars


def test_trustworthy_resilience_from_keywords():
    vair = match_all("system cannot recover from failures gracefully")
    chars = match_trustworthy_characteristics("system cannot recover from failures gracefully", vair)
    assert "resilience" in chars


def test_trustworthy_transparency_from_keywords():
    vair = match_all("opaque model with no explainability")
    chars = match_trustworthy_characteristics("opaque model with no explainability", vair)
    assert "transparency" in chars
```

- [ ] **Step 3: Write failing tests for edge cases**

Add to `tests/test_vair.py`:

```python
def test_trustworthy_empty_text():
    vair = match_all("")
    chars = match_trustworthy_characteristics("", vair)
    assert chars == []


def test_trustworthy_no_matches():
    vair = match_all("routine data processing pipeline")
    chars = match_trustworthy_characteristics("routine data processing pipeline", vair)
    assert chars == []


def test_trustworthy_multiple_characteristics():
    text = "biased model with low security and lack of transparency"
    vair = match_all(text)
    chars = match_trustworthy_characteristics(text, vair)
    assert "fairness" in chars
    assert "cybersecurity" in chars
    assert "transparency" in chars


def test_trustworthy_returns_sorted():
    text = "unsafe biased insecure system with privacy violations"
    vair = match_all(text)
    chars = match_trustworthy_characteristics(text, vair)
    assert chars == sorted(chars)
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `uv run pytest tests/test_vair.py -v -k trustworthy`
Expected: FAIL — `ImportError: cannot import name 'match_trustworthy_characteristics'`

- [ ] **Step 5: Implement trustworthy characteristic matching in `vair.py`**

Add to `src/risk_landscaper/vair.py` after the `IMPACTED_AREAS` list:

```python
@dataclass(frozen=True)
class TrustworthyCharacteristic:
    name: str
    iso24028_clause: str | None
    aiact_article: str | None
    vair_type_ids: list[str]
    keywords: list[str]


# ISO/IEC 24028 + EU AI Act Art. 9-15 trustworthy characteristics.
# Each characteristic is inferred from VAIR type matches (free) and/or
# keyword heuristics against risk description + concern text.
# Sources: ISO/IEC TR 24028:2020 clauses 6-12, EU AI Act Art. 9-15,
# W3C DPV risk extension (risk:AccuracyRisk, risk:RobustnessRisk, etc.)
TRUSTWORTHY_CHARACTERISTICS: list[TrustworthyCharacteristic] = [
    TrustworthyCharacteristic(
        "accuracy", "implicit", "Art.15(1)",
        ["DegradedAccuracy", "LowAccuracy"],
        ["inaccura"],
    ),
    TrustworthyCharacteristic(
        "robustness", "implicit", "Art.15(3)",
        ["DecreasedRobustness", "LowRobustness"],
        [],
    ),
    TrustworthyCharacteristic(
        "cybersecurity", "cl.9", "Art.15(4)",
        ["DecreasedSecurity", "LowSecurity", "Cyberattack", "SystemVulnerability"],
        [],
    ),
    TrustworthyCharacteristic(
        "transparency", "cl.6", "Art.13",
        ["LackOfTransparency"],
        ["explainab", "interpretab", "opaque", "black box", "unexplainab"],
    ),
    TrustworthyCharacteristic(
        "fairness", "cl.11", "Art.10",
        ["Bias", "DiscriminatoryTreatment", "UnfavourableTreatment"],
        [],
    ),
    TrustworthyCharacteristic(
        "privacy", "cl.10", "Art.10",
        [],
        ["privacy", "personal data", "data protection", "confidential"],
    ),
    TrustworthyCharacteristic(
        "safety", "cl.8", "Art.9",
        ["Safety", "Death", "PhysicalInjury"],
        ["hazard", "dangerous"],
    ),
    TrustworthyCharacteristic(
        "accountability", "cl.12", "Art.17",
        ["Overreliance", "ImpairedDecisionMaking"],
        ["accountab", "liable", "liability"],
    ),
    TrustworthyCharacteristic(
        "controllability", "cl.7", "Art.14",
        ["InsufficientHumanOversightMeasure"],
        ["human oversight", "human-in-the-loop", "human in the loop"],
    ),
    TrustworthyCharacteristic(
        "reliability", "implicit", "Art.15(1)",
        [],
        ["reliab", "consistent", "dependab"],
    ),
    TrustworthyCharacteristic(
        "resilience", "implicit", "Art.15(4)",
        [],
        ["resilien", "recover", "fault-tolerant", "fault tolerant"],
    ),
]


def match_trustworthy_characteristics(
    text: str,
    vair_matches: dict[str, list[VairType]],
) -> list[str]:
    matched_vair_ids: set[str] = set()
    for types in vair_matches.values():
        for t in types:
            matched_vair_ids.add(t.id)

    lower = text.lower()
    result: set[str] = set()
    for tc in TRUSTWORTHY_CHARACTERISTICS:
        if any(vid in matched_vair_ids for vid in tc.vair_type_ids):
            result.add(tc.name)
            continue
        if any(kw in lower for kw in tc.keywords):
            result.add(tc.name)

    return sorted(result)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_vair.py -v -k trustworthy`
Expected: All 16 trustworthy tests PASS

- [ ] **Step 7: Run full vair test suite for regressions**

Run: `uv run pytest tests/test_vair.py -v`
Expected: All existing + new tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/risk_landscaper/vair.py tests/test_vair.py
git commit -m "feat: add trustworthy characteristic enumeration and matching to vair.py

Vendor ISO/IEC 24028 + EU AI Act trustworthy characteristics with
VAIR-derived inference and keyword fallback heuristics."
```

---

### Task 2: Wire trustworthy characteristics into `build_landscape.py`

**Files:**
- Modify: `src/risk_landscaper/stages/build_landscape.py`
- Test: `tests/test_build_landscape.py`

- [ ] **Step 1: Write failing test for trustworthy characteristics on built cards**

Add to `tests/test_build_landscape.py`:

```python
def test_build_landscape_populates_trustworthy_characteristics():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Fairness Policy",
            matched_risks=[
                RiskMatch(risk_id="atlas-bias", risk_name="Bias",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "atlas-bias": {
            "id": "atlas-bias", "name": "Bias",
            "description": "Model exhibits systematic bias against protected groups",
            "concern": "Discriminatory outputs and unfair treatment of users",
            "risk_type": "output",
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert "fairness" in card.trustworthy_characteristics


def test_build_landscape_trustworthy_empty_for_generic_risk():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="General",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="R",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "r1": {"id": "r1", "name": "R", "description": "Generic risk entry"},
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert card.trustworthy_characteristics == []


def test_build_landscape_trustworthy_multiple():
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    mappings = [
        PolicyRiskMapping(
            policy_concept="Security",
            matched_risks=[
                RiskMatch(risk_id="r1", risk_name="R",
                          relevance="primary", justification="test"),
            ],
        ),
    ]
    risk_details_cache = {
        "r1": {
            "id": "r1", "name": "R",
            "description": "Cyberattack with lack of transparency and biased outcomes",
            "concern": "System vulnerability exploited leading to privacy breach",
        },
    }
    landscape = build_risk_landscape(
        mappings=mappings, risk_details_cache=risk_details_cache,
        model="test", run_slug="test", timestamp="t",
    )
    card = landscape.risks[0]
    assert "cybersecurity" in card.trustworthy_characteristics
    assert "transparency" in card.trustworthy_characteristics
    assert "fairness" in card.trustworthy_characteristics
    assert "privacy" in card.trustworthy_characteristics
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_landscape.py -v -k trustworthy`
Expected: FAIL — `assert "fairness" in []`

- [ ] **Step 3: Update `_vair_enrich()` and `build_risk_landscape()` to pass characteristics through**

In `src/risk_landscaper/stages/build_landscape.py`:

Add import at top:
```python
from risk_landscaper.vair import match_all as vair_match_all, match_trustworthy_characteristics
```

Update `_vair_enrich()` to return characteristics:
```python
def _vair_enrich(description: str, concern: str) -> dict:
    text = f"{description} {concern}"
    matches = vair_match_all(text)
    result: dict = {}
    if matches["risk_sources"]:
        best = matches["risk_sources"][0]
        result["source_type"] = best.parent
        result["source_subtypes"] = [m.id for m in matches["risk_sources"]]
    if matches["consequences"]:
        result["consequences"] = [
            RiskConsequence(description=m.label, provenance="vair")
            for m in matches["consequences"]
        ]
    if matches["impacts"]:
        area_matches = matches["impacted_areas"]
        area = area_matches[0].label.lower() if area_matches else None
        result["impacts"] = [
            RiskImpact(description=m.label, area=area, provenance="vair")
            for m in matches["impacts"]
        ]
    chars = match_trustworthy_characteristics(text, matches)
    if chars:
        result["trustworthy_characteristics"] = chars
    return result
```

Update the `RiskCard` constructor call in `build_risk_landscape()` (inside the loop, around line 228-244) — add:
```python
                trustworthy_characteristics=vair.get("trustworthy_characteristics", []),
```

The full constructor call becomes:
```python
            risks.append(RiskCard(
                risk_id=rm.risk_id,
                risk_name=details.get("name") or rm.risk_name or rm.risk_id,
                risk_description=description,
                risk_concern=concern,
                risk_framework=framework,
                cross_mappings=related_risks.get(rm.risk_id, []),
                risk_type=details.get("risk_type"),
                descriptors=descriptors,
                risk_sources=baseline_source,
                consequences=vair.get("consequences", []),
                impacts=vair.get("impacts", []),
                trustworthy_characteristics=vair.get("trustworthy_characteristics", []),
                controls=_actions_to_controls(actions),
                related_policies=_collect_related_policies(rm.risk_id, mappings),
                related_actions=actions,
                incidents=incidents,
            ))
```

- [ ] **Step 4: Run trustworthy tests to verify they pass**

Run: `uv run pytest tests/test_build_landscape.py -v -k trustworthy`
Expected: All 3 trustworthy tests PASS

- [ ] **Step 5: Run full build_landscape test suite for regressions**

Run: `uv run pytest tests/test_build_landscape.py -v`
Expected: All existing + new tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/risk_landscaper/stages/build_landscape.py tests/test_build_landscape.py
git commit -m "feat: populate trustworthy_characteristics on RiskCard during build_landscape

Wire match_trustworthy_characteristics() into _vair_enrich() so cards
get ISO/IEC 24028 characteristics from VAIR type inference + keywords."
```

---

### Task 3: Update changelog and run full test suite

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add changelog entry**

Add under `## [Unreleased]` → `### Added`:

```markdown
- **Trustworthy characteristics inference** — `RiskCard.trustworthy_characteristics` now populated during `build_landscape` from VAIR type matches and keyword heuristics. 11 ISO/IEC 24028 + EU AI Act characteristics: accuracy, robustness, cybersecurity, transparency, fairness, privacy, safety, accountability, controllability, reliability, resilience. Free-layer enrichment, no LLM calls. 19 new tests.
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS (existing 276 + 19 new = 295)

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add trustworthy characteristics changelog entry"
```
