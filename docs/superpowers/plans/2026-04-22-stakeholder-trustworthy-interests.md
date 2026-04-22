# Stakeholder Trustworthy Interests Normalization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `trustworthy_interests` to `Stakeholder`, populated by normalizing free-text `interests` against canonical trustworthy characteristics after entity enrichment.

**Architecture:** After the LLM returns entity enrichment (ingest pass 4), a post-processing step runs `match_trustworthy_characteristics()` on each stakeholder's joined `interests` text. The matched canonical names become `trustworthy_interests: list[str]`. No LLM prompt changes — the normalization is purely keyword-based, reusing the existing VAIR infrastructure.

**Tech Stack:** Python, Pydantic, pytest

---

### Task 1: Add `trustworthy_interests` field to `Stakeholder` model

**Files:**
- Modify: `src/risk_landscaper/models.py:28-37`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_models.py` after the existing `test_stakeholder_involvement_fields` test (around line 177):

```python
def test_stakeholder_trustworthy_interests():
    s = Stakeholder(
        name="Patient", roles=["airo:AISubject"],
        interests=["safety", "privacy"],
        trustworthy_interests=["privacy", "safety"],
    )
    assert s.trustworthy_interests == ["privacy", "safety"]


def test_stakeholder_trustworthy_interests_defaults_empty():
    s = Stakeholder(name="User", roles=["airo:AIUser"])
    assert s.trustworthy_interests == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v -k trustworthy_interests`
Expected: FAIL — `unexpected keyword argument 'trustworthy_interests'`

- [ ] **Step 3: Add field to Stakeholder model**

In `src/risk_landscaper/models.py`, add `trustworthy_interests` to the `Stakeholder` class after the `interests` field (line 37):

```python
class Stakeholder(BaseModel):
    name: str
    roles: list[str] = []
    description: str | None = None
    involvement: Literal["intended", "unintended"] | None = None
    activity: Literal["active", "passive"] | None = None
    awareness: Literal["informed", "uninformed"] | None = None
    output_control: Literal["challenge", "correct", "cannot_opt_out"] | None = None
    relationship: Literal["internal", "external"] | None = None
    interests: list[str] = []
    trustworthy_interests: list[str] = []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v -k trustworthy_interests`
Expected: PASS

- [ ] **Step 5: Run full model test suite for regressions**

Run: `uv run pytest tests/test_models.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/risk_landscaper/models.py tests/test_models.py
git commit -m "feat: add trustworthy_interests field to Stakeholder model

Canonical trustworthy characteristic names derived from free-text
interests, to be populated after entity enrichment."
```

---

### Task 2: Normalize interests to trustworthy characteristics in `enrich_entities()`

**Files:**
- Modify: `src/risk_landscaper/stages/ingest.py:365-465`
- Test: `tests/test_ingest.py`

- [ ] **Step 1: Write failing test for normalization in entity enrichment**

Add to `tests/test_ingest.py` after the existing `test_enrich_entities_full` test (around line 597):

```python
def test_enrich_entities_populates_trustworthy_interests(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(),
        stakeholders=[
            _SlimStakeholderDetail(
                name="staff",
                involvement="intended",
                activity="active",
                awareness="informed",
                output_control="correct",
                relationship="internal",
                interests=["efficiency", "accuracy"],
            ),
            _SlimStakeholderDetail(
                name="customers",
                involvement="unintended",
                activity="passive",
                awareness="uninformed",
                output_control="cannot_opt_out",
                relationship="external",
                interests=["privacy", "fair treatment"],
            ),
        ],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.interests == ["efficiency", "accuracy"]
    assert "accuracy" in staff.trustworthy_interests

    customers = next(s for s in result.stakeholders if s.name == "customers")
    assert customers.interests == ["privacy", "fair treatment"]
    assert "privacy" in customers.trustworthy_interests
    assert "fairness" in customers.trustworthy_interests


def test_enrich_entities_trustworthy_interests_empty_when_no_match(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(),
        stakeholders=[
            _SlimStakeholderDetail(
                name="staff",
                involvement="intended",
                activity="active",
                awareness="informed",
                output_control="correct",
                relationship="internal",
                interests=["efficiency", "cost reduction"],
            ),
        ],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.interests == ["efficiency", "cost reduction"]
    assert staff.trustworthy_interests == []


def test_enrich_entities_trustworthy_interests_empty_when_no_interests(mock_client, mock_config):
    profile = _make_profile()
    mock_client.chat.completions.create.return_value = _SlimEntityEnrichment(
        organization=_SlimOrgDetail(),
        stakeholders=[
            _SlimStakeholderDetail(
                name="staff",
                involvement="intended",
                activity="active",
                awareness="informed",
                output_control="correct",
                relationship="internal",
                interests=[],
            ),
        ],
    )

    result = enrich_entities(SAMPLE_MARKDOWN, profile, mock_client, mock_config)

    staff = next(s for s in result.stakeholders if s.name == "staff")
    assert staff.interests == []
    assert staff.trustworthy_interests == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ingest.py -v -k trustworthy_interests`
Expected: FAIL — `assert "accuracy" in []`

- [ ] **Step 3: Add normalization to `enrich_entities()`**

In `src/risk_landscaper/stages/ingest.py`:

**Add import** at the top of the file (after the existing imports from `risk_landscaper`):

```python
from risk_landscaper.vair import match_trustworthy_characteristics
```

**Update the stakeholder enrichment loop** (lines 398-415). Replace the existing `enriched_stakeholders` loop with:

```python
    stakeholder_map = {s.name: s for s in result.stakeholders}
    enriched_stakeholders: list[Stakeholder] = []
    for s in profile.stakeholders:
        detail = stakeholder_map.get(s.name)
        if detail:
            interests = detail.interests or []
            trustworthy_interests = (
                match_trustworthy_characteristics(" ".join(interests), {})
                if interests else []
            )
            enriched_stakeholders.append(Stakeholder(
                name=s.name,
                roles=s.roles,
                description=s.description,
                involvement=detail.involvement or None,
                activity=detail.activity or None,
                awareness=detail.awareness or None,
                output_control=detail.output_control or None,
                relationship=detail.relationship or None,
                interests=interests,
                trustworthy_interests=trustworthy_interests,
            ))
        else:
            enriched_stakeholders.append(s)
```

The key change: after extracting `interests`, call `match_trustworthy_characteristics(" ".join(interests), {})` with the interests joined into a single text string and an empty VAIR matches dict (no VAIR types to cross-reference — just keyword matching). The result is stored as `trustworthy_interests`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ingest.py -v -k trustworthy_interests`
Expected: All 3 tests PASS

- [ ] **Step 5: Run full ingest test suite for regressions**

Run: `uv run pytest tests/test_ingest.py -v`
Expected: All existing + new tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/risk_landscaper/stages/ingest.py tests/test_ingest.py
git commit -m "feat: normalize stakeholder interests to trustworthy characteristics

After entity enrichment, match free-text interests against canonical
ISO/IEC 24028 characteristics using keyword heuristics from vair.py."
```

---

### Task 3: Update changelog and run full test suite

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add changelog entry**

Add under `## [Unreleased]` → `### Added`, after the trustworthy characteristics inference entry:

```markdown
- **Stakeholder trustworthy interests** — `Stakeholder.trustworthy_interests` field populated after entity enrichment by normalizing free-text `interests` against canonical ISO/IEC 24028 characteristics. Enables directional join with `RiskCard.trustworthy_characteristics` to show which stakeholders' interests are threatened by each risk. 3 new tests.
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add stakeholder trustworthy interests changelog entry"
```
