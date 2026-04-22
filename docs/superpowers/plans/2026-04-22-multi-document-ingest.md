# Multi-Document Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support ingesting multiple documents for a single organization/policy set, merging the resulting PolicyProfiles into one before downstream pipeline stages.

**Architecture:** Run `ingest()` independently per document, then merge the resulting `PolicyProfile` objects using name-keyed deduplication. CLI accepts variadic positional `policy_files`. New `merge.py` module contains all merge logic (pure data operations, no LLM). Downstream stages (detect_domain through assess) receive the merged profile unchanged.

**Tech Stack:** Python 3.11+, Pydantic, Typer, pytest

**Spec:** `docs/multi-document-ingest.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `src/risk_landscaper/models.py` | Modify | Add `source_documents` field to `Policy` and `PolicyProfile` |
| `src/risk_landscaper/merge.py` | Create | All merge logic: `_union_lists`, `_merge_by_key`, per-type merge fns, `merge_profiles` |
| `src/risk_landscaper/cli.py` | Modify | Accept `list[Path]`, per-doc ingest loop, merge call, updated reporting |
| `tests/test_models.py` | Modify | Tests for `source_documents` field |
| `tests/test_merge.py` | Create | Tests for all merge functions |
| `tests/test_cli.py` | Modify | Multi-file CLI tests |
| `CHANGELOG.md` | Modify | Document multi-document ingest feature |
| `README.md` | Modify | Update usage examples and input format docs for multi-file |

---

### Task 1: Add `source_documents` field to models

**Files:**
- Modify: `src/risk_landscaper/models.py:70-91`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for source_documents on Policy**

Add to `tests/test_models.py`:

```python
def test_policy_source_documents_default():
    p = Policy(policy_concept="Fraud", concept_definition="About fraud")
    assert p.source_documents == []


def test_policy_source_documents_set():
    p = Policy(
        policy_concept="Fraud", concept_definition="About fraud",
        source_documents=["policy.pdf", "faq.md"],
    )
    assert p.source_documents == ["policy.pdf", "faq.md"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py::test_policy_source_documents_default tests/test_models.py::test_policy_source_documents_set -v`
Expected: FAIL — `source_documents` field does not exist

- [ ] **Step 3: Add source_documents to Policy**

In `src/risk_landscaper/models.py`, add after the `decomposition` field on `Policy` (line 80):

```python
    source_documents: list[str] = []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py::test_policy_source_documents_default tests/test_models.py::test_policy_source_documents_set -v`
Expected: PASS

- [ ] **Step 5: Write failing tests for source_documents on PolicyProfile**

Add to `tests/test_models.py`:

```python
def test_policy_profile_source_documents_default():
    profile = PolicyProfile(policies=[])
    assert profile.source_documents == []


def test_policy_profile_source_documents_set():
    profile = PolicyProfile(
        policies=[],
        source_documents=["policy.pdf", "annex.docx"],
    )
    assert profile.source_documents == ["policy.pdf", "annex.docx"]


def test_policy_profile_round_trip_with_source_documents():
    profile = PolicyProfile(
        organization=Organization(name="Acme"),
        policies=[
            Policy(
                policy_concept="Fraud", concept_definition="About fraud",
                source_documents=["doc1.md"],
            ),
        ],
        source_documents=["doc1.md", "doc2.pdf"],
    )
    data = profile.model_dump()
    restored = PolicyProfile(**data)
    assert restored.source_documents == ["doc1.md", "doc2.pdf"]
    assert restored.policies[0].source_documents == ["doc1.md"]
```

- [ ] **Step 6: Add source_documents to PolicyProfile**

In `src/risk_landscaper/models.py`, add after `policies` field on `PolicyProfile` (line 91):

```python
    source_documents: list[str] = []
```

- [ ] **Step 7: Run all model tests**

Run: `uv run pytest tests/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add src/risk_landscaper/models.py tests/test_models.py
git commit -m "feat: add source_documents field to Policy and PolicyProfile

Backward-compatible list[str] field (defaults to []) for tracking
which input documents contributed each policy and the overall profile.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Merge primitives — helpers and per-type merge functions

**Files:**
- Create: `src/risk_landscaper/merge.py`
- Create: `tests/test_merge.py`

- [ ] **Step 1: Write failing tests for `_union_lists`**

Create `tests/test_merge.py`:

```python
from risk_landscaper.merge import _union_lists


def test_union_lists_no_overlap():
    assert _union_lists(["a", "b"], ["c", "d"]) == ["a", "b", "c", "d"]


def test_union_lists_with_overlap():
    assert _union_lists(["a", "b", "c"], ["b", "c", "d"]) == ["a", "b", "c", "d"]


def test_union_lists_preserves_order():
    assert _union_lists(["c", "a"], ["b", "a"]) == ["c", "a", "b"]


def test_union_lists_empty():
    assert _union_lists([], ["a"]) == ["a"]
    assert _union_lists(["a"], []) == ["a"]
    assert _union_lists([], []) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_merge.py -v -k "union_lists"`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement `_union_lists`**

Create `src/risk_landscaper/merge.py`:

```python
import logging
from typing import Callable, TypeVar

from risk_landscaper.models import (
    AiSystem,
    BoundaryExample,
    Organization,
    Policy,
    PolicyProfile,
    RegulatoryReference,
    Stakeholder,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _union_lists(a: list[str], b: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in a + b:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_merge.py -v -k "union_lists"`
Expected: PASS

- [ ] **Step 5: Write failing tests for `_merge_by_key`**

Add to `tests/test_merge.py`:

```python
from risk_landscaper.merge import _merge_by_key


def test_merge_by_key_no_duplicates():
    items = [{"name": "a", "v": 1}, {"name": "b", "v": 2}]
    result = _merge_by_key(
        items,
        key_fn=lambda x: x["name"],
        merge_fn=lambda a, b: {**a, "v": a["v"] + b["v"]},
    )
    assert result == [{"name": "a", "v": 1}, {"name": "b", "v": 2}]


def test_merge_by_key_with_duplicates():
    items = [{"name": "a", "v": 1}, {"name": "a", "v": 2}, {"name": "b", "v": 3}]
    result = _merge_by_key(
        items,
        key_fn=lambda x: x["name"],
        merge_fn=lambda a, b: {**a, "v": a["v"] + b["v"]},
    )
    assert len(result) == 2
    assert result[0] == {"name": "a", "v": 3}
    assert result[1] == {"name": "b", "v": 3}


def test_merge_by_key_preserves_first_occurrence_order():
    items = [{"name": "c"}, {"name": "a"}, {"name": "c"}]
    result = _merge_by_key(
        items,
        key_fn=lambda x: x["name"],
        merge_fn=lambda a, b: a,
    )
    assert [r["name"] for r in result] == ["c", "a"]
```

- [ ] **Step 6: Implement `_merge_by_key`**

Add to `src/risk_landscaper/merge.py`:

```python
def _merge_by_key(
    items: list[T],
    key_fn: Callable[[T], str],
    merge_fn: Callable[[T, T], T],
) -> list[T]:
    seen: dict[str, T] = {}
    order: list[str] = []
    for item in items:
        k = key_fn(item)
        if k in seen:
            seen[k] = merge_fn(seen[k], item)
        else:
            seen[k] = item
            order.append(k)
    return [seen[k] for k in order]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_merge.py -v -k "merge_by_key"`
Expected: PASS

- [ ] **Step 8: Write failing tests for entity merge functions**

Add to `tests/test_merge.py`:

```python
from risk_landscaper.models import (
    Organization, Stakeholder, AiSystem, RegulatoryReference,
)
from risk_landscaper.merge import (
    _merge_organizations,
    _merge_stakeholders,
    _merge_ai_systems,
    _merge_regulations,
)


def test_merge_organizations_union_lists():
    a = Organization(name="Acme", governance_roles=["CTO"], certifications=["SOC2"])
    b = Organization(name="Acme", governance_roles=["CTO", "Board"], certifications=["ISO27001"])
    result = _merge_organizations(a, b)
    assert result.name == "Acme"
    assert result.governance_roles == ["CTO", "Board"]
    assert result.certifications == ["SOC2", "ISO27001"]


def test_merge_organizations_prefer_first_scalars():
    a = Organization(name="Acme", management_system="ISO 42001")
    b = Organization(name="Acme", management_system="Internal", description="Corp")
    result = _merge_organizations(a, b)
    assert result.management_system == "ISO 42001"
    assert result.description == "Corp"


def test_merge_stakeholders_union_roles_and_interests():
    a = Stakeholder(name="staff", roles=["airo:AIUser"], interests=["efficiency"])
    b = Stakeholder(name="Staff", roles=["operator"], interests=["safety", "efficiency"])
    result = _merge_stakeholders(a, b)
    assert result.name == "staff"
    assert result.roles == ["airo:AIUser", "operator"]
    assert result.interests == ["efficiency", "safety"]


def test_merge_stakeholders_prefer_first_airo_fields():
    a = Stakeholder(name="patient", involvement="intended", activity=None)
    b = Stakeholder(name="patient", involvement="unintended", activity="passive")
    result = _merge_stakeholders(a, b)
    assert result.involvement == "intended"
    assert result.activity == "passive"


def test_merge_ai_systems_union_lists():
    a = AiSystem(name="Bot", purpose=["support"], techniques=["RAG"])
    b = AiSystem(name="Bot", purpose=["triage"], techniques=["RAG", "transformer"])
    result = _merge_ai_systems(a, b)
    assert result.purpose == ["support", "triage"]
    assert result.techniques == ["RAG", "transformer"]


def test_merge_ai_systems_prefer_first_scalars():
    a = AiSystem(name="Bot", modality="text-to-text")
    b = AiSystem(name="Bot", modality="multimodal", automation_level="full")
    result = _merge_ai_systems(a, b)
    assert result.modality == "text-to-text"
    assert result.automation_level == "full"


def test_merge_regulations_prefer_non_none():
    a = RegulatoryReference(name="GDPR", jurisdiction=None)
    b = RegulatoryReference(name="GDPR", jurisdiction="EU", reference="Art 22")
    result = _merge_regulations(a, b)
    assert result.jurisdiction == "EU"
    assert result.reference == "Art 22"
```

- [ ] **Step 9: Implement entity merge functions**

Add to `src/risk_landscaper/merge.py`:

```python
def _merge_organizations(a: Organization, b: Organization) -> Organization:
    return Organization(
        name=a.name,
        description=a.description or b.description,
        governance_roles=_union_lists(a.governance_roles, b.governance_roles),
        management_system=a.management_system or b.management_system,
        certifications=_union_lists(a.certifications, b.certifications),
        delegates=_union_lists(a.delegates, b.delegates),
    )


def _merge_stakeholders(a: Stakeholder, b: Stakeholder) -> Stakeholder:
    return Stakeholder(
        name=a.name,
        roles=_union_lists(a.roles, b.roles),
        description=a.description or b.description,
        involvement=a.involvement or b.involvement,
        activity=a.activity or b.activity,
        awareness=a.awareness or b.awareness,
        output_control=a.output_control or b.output_control,
        relationship=a.relationship or b.relationship,
        interests=_union_lists(a.interests, b.interests),
    )


def _merge_ai_systems(a: AiSystem, b: AiSystem) -> AiSystem:
    return AiSystem(
        name=a.name,
        description=a.description or b.description,
        purpose=_union_lists(a.purpose, b.purpose),
        risk_level=a.risk_level or b.risk_level,
        modality=a.modality or b.modality,
        techniques=_union_lists(a.techniques, b.techniques),
        automation_level=a.automation_level or b.automation_level,
        serves_stakeholders=_union_lists(a.serves_stakeholders, b.serves_stakeholders),
        assets=_union_lists(a.assets, b.assets),
    )


def _merge_regulations(a: RegulatoryReference, b: RegulatoryReference) -> RegulatoryReference:
    return RegulatoryReference(
        name=a.name,
        jurisdiction=a.jurisdiction or b.jurisdiction,
        reference=a.reference or b.reference,
    )
```

- [ ] **Step 10: Run all merge tests so far**

Run: `uv run pytest tests/test_merge.py -v`
Expected: ALL PASS

- [ ] **Step 11: Commit**

```bash
git add src/risk_landscaper/merge.py tests/test_merge.py
git commit -m "feat: add merge primitives for multi-document profile merging

_union_lists, _merge_by_key generic helpers plus per-type merge
functions for Organization, Stakeholder, AiSystem, RegulatoryReference.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Policy merge and `merge_profiles` orchestrator

**Files:**
- Modify: `src/risk_landscaper/merge.py`
- Modify: `tests/test_merge.py`

- [ ] **Step 1: Write failing tests for `_merge_policies`**

Add to `tests/test_merge.py`:

```python
from risk_landscaper.models import Policy, BoundaryExample, PolicyDecomposition
from risk_landscaper.merge import _merge_policies


def test_merge_policies_union_boundary_examples():
    a = Policy(
        policy_concept="Fraud", concept_definition="Short def",
        boundary_examples=[BoundaryExample(prohibited="help fraud", acceptable="detect fraud")],
        acceptable_uses=["education"],
        source_documents=["doc1.md"],
    )
    b = Policy(
        policy_concept="Fraud", concept_definition="A longer and richer definition of fraud policy",
        boundary_examples=[
            BoundaryExample(prohibited="help fraud", acceptable="detect fraud"),
            BoundaryExample(prohibited="launder money", acceptable="flag suspicious"),
        ],
        acceptable_uses=["training"],
        source_documents=["doc2.md"],
    )
    result = _merge_policies(a, b)
    assert result.policy_concept == "Fraud"
    assert result.concept_definition == b.concept_definition  # longer wins
    assert len(result.boundary_examples) == 2  # deduplicated
    assert result.acceptable_uses == ["education", "training"]
    assert result.source_documents == ["doc1.md", "doc2.md"]


def test_merge_policies_prefer_first_scalars():
    a = Policy(
        policy_concept="AML", concept_definition="About AML",
        governance_function="direct", human_involvement="officer review",
    )
    b = Policy(
        policy_concept="AML", concept_definition="About AML",
        governance_function="evaluate", human_involvement="auto",
        decomposition=PolicyDecomposition(agent="bot", activity="scan", entity="txn"),
    )
    result = _merge_policies(a, b)
    assert result.governance_function == "direct"
    assert result.human_involvement == "officer review"
    assert result.decomposition is not None
    assert result.decomposition.agent == "bot"


def test_merge_policies_union_risk_controls():
    a = Policy(policy_concept="P", concept_definition="D", risk_controls=["human review"])
    b = Policy(policy_concept="P", concept_definition="D", risk_controls=["human review", "audit log"])
    result = _merge_policies(a, b)
    assert result.risk_controls == ["human review", "audit log"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_merge.py -v -k "merge_policies"`
Expected: FAIL — `_merge_policies` not defined

- [ ] **Step 3: Implement `_merge_policies`**

Add to `src/risk_landscaper/merge.py`:

```python
def _merge_policies(a: Policy, b: Policy) -> Policy:
    definition = a.concept_definition if len(a.concept_definition) >= len(b.concept_definition) else b.concept_definition

    seen_boundaries: set[tuple[str, str]] = {
        (be.prohibited, be.acceptable) for be in a.boundary_examples
    }
    merged_boundaries = list(a.boundary_examples)
    for be in b.boundary_examples:
        key = (be.prohibited, be.acceptable)
        if key not in seen_boundaries:
            merged_boundaries.append(be)
            seen_boundaries.add(key)

    return Policy(
        policy_concept=a.policy_concept,
        concept_definition=definition,
        governance_function=a.governance_function or b.governance_function,
        boundary_examples=merged_boundaries,
        acceptable_uses=_union_lists(a.acceptable_uses, b.acceptable_uses),
        risk_controls=_union_lists(a.risk_controls, b.risk_controls),
        human_involvement=a.human_involvement or b.human_involvement,
        affects_stakeholders=_union_lists(a.affects_stakeholders, b.affects_stakeholders),
        applies_to_systems=_union_lists(a.applies_to_systems, b.applies_to_systems),
        decomposition=a.decomposition or b.decomposition,
        source_documents=_union_lists(a.source_documents, b.source_documents),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_merge.py -v -k "merge_policies"`
Expected: PASS

- [ ] **Step 5: Write failing tests for `merge_profiles`**

Add to `tests/test_merge.py`:

```python
from risk_landscaper.models import PolicyProfile
from risk_landscaper.merge import merge_profiles


def test_merge_profiles_single():
    profile = PolicyProfile(
        organization=Organization(name="Acme"),
        domain="finance",
        policies=[Policy(policy_concept="Fraud", concept_definition="About fraud")],
    )
    result = merge_profiles([profile], ["doc1.md"])
    assert result.organization.name == "Acme"
    assert len(result.policies) == 1
    assert result.source_documents == ["doc1.md"]
    assert result.policies[0].source_documents == ["doc1.md"]


def test_merge_profiles_two_documents():
    a = PolicyProfile(
        organization=Organization(name="Acme"),
        domain="finance",
        purpose=["trading"],
        stakeholders=[Stakeholder(name="trader", roles=["airo:AIUser"])],
        ai_systems=[AiSystem(name="Bot", modality="text-to-text")],
        regulations=[RegulatoryReference(name="SEC")],
        policies=[
            Policy(policy_concept="Fraud", concept_definition="About fraud",
                   source_documents=["policy.md"]),
            Policy(policy_concept="AML", concept_definition="About AML",
                   source_documents=["policy.md"]),
        ],
    )
    b = PolicyProfile(
        organization=Organization(name="Acme", governance_roles=["CTO"]),
        domain="finance",
        purpose=["compliance"],
        stakeholders=[
            Stakeholder(name="trader", roles=["operator"]),
            Stakeholder(name="auditor", roles=["reviewer"]),
        ],
        ai_systems=[AiSystem(name="Bot", techniques=["RAG"])],
        regulations=[RegulatoryReference(name="SEC", jurisdiction="US")],
        policies=[
            Policy(policy_concept="Fraud", concept_definition="Detailed fraud prevention policy",
                   acceptable_uses=["detection training"],
                   source_documents=["faq.md"]),
            Policy(policy_concept="KYC", concept_definition="Know your customer",
                   source_documents=["faq.md"]),
        ],
    )
    result = merge_profiles([a, b], ["policy.md", "faq.md"])
    assert result.source_documents == ["policy.md", "faq.md"]
    assert result.organization.name == "Acme"
    assert result.organization.governance_roles == ["CTO"]
    assert result.purpose == ["trading", "compliance"]

    # Stakeholders merged by name (case-insensitive)
    assert len(result.stakeholders) == 2
    trader = next(s for s in result.stakeholders if s.name.lower() == "trader")
    assert "airo:AIUser" in trader.roles
    assert "operator" in trader.roles

    # AI systems merged
    bot = next(s for s in result.ai_systems if s.name == "Bot")
    assert bot.modality == "text-to-text"
    assert bot.techniques == ["RAG"]

    # Regulations merged
    sec = next(r for r in result.regulations if r.name == "SEC")
    assert sec.jurisdiction == "US"

    # Policies: Fraud merged (3 total: Fraud, AML, KYC)
    assert len(result.policies) == 3
    fraud = next(p for p in result.policies if p.policy_concept == "Fraud")
    assert fraud.concept_definition == "Detailed fraud prevention policy"  # longer
    assert fraud.acceptable_uses == ["detection training"]
    assert set(fraud.source_documents) == {"policy.md", "faq.md"}


def test_merge_profiles_empty():
    result = merge_profiles([], [])
    assert result.policies == []
    assert result.source_documents == []


def test_merge_profiles_different_orgs_uses_first():
    a = PolicyProfile(organization=Organization(name="Alpha"), policies=[])
    b = PolicyProfile(organization=Organization(name="Beta"), policies=[])
    result = merge_profiles([a, b], ["a.md", "b.md"])
    assert result.organization.name == "Alpha"


def test_merge_profiles_domain_keeps_longest():
    a = PolicyProfile(domain="finance", policies=[])
    b = PolicyProfile(domain="financial services", policies=[])
    result = merge_profiles([a, b], ["a.md", "b.md"])
    assert result.domain == "financial services"


def test_merge_profiles_case_insensitive_entity_merge():
    a = PolicyProfile(
        stakeholders=[Stakeholder(name="Staff", roles=["user"])],
        policies=[],
    )
    b = PolicyProfile(
        stakeholders=[Stakeholder(name="staff", roles=["operator"])],
        policies=[],
    )
    result = merge_profiles([a, b], ["a.md", "b.md"])
    assert len(result.stakeholders) == 1
    assert result.stakeholders[0].name == "Staff"  # first wins
    assert set(result.stakeholders[0].roles) == {"user", "operator"}
```

- [ ] **Step 6: Implement `merge_profiles`**

Add to `src/risk_landscaper/merge.py`:

```python
def merge_profiles(
    profiles: list[PolicyProfile],
    sources: list[str],
) -> PolicyProfile:
    if not profiles:
        return PolicyProfile(source_documents=sources)

    if len(profiles) == 1:
        p = profiles[0]
        policies = [
            pol.model_copy(update={"source_documents": _union_lists(pol.source_documents, sources[:1])})
            if not pol.source_documents else pol
            for pol in p.policies
        ]
        return p.model_copy(update={
            "policies": policies,
            "source_documents": sources,
        })

    # Merge organizations
    orgs = [p.organization for p in profiles if p.organization]
    org = None
    if orgs:
        org = orgs[0]
        for o in orgs[1:]:
            if o.name.lower() != org.name.lower():
                logger.warning(
                    "Different organization names across documents: %r vs %r — using first",
                    org.name, o.name,
                )
            org = _merge_organizations(org, o)

    # Merge domain — keep longest (most specific)
    domains = [p.domain for p in profiles if p.domain]
    domain = max(domains, key=len) if domains else None

    # Merge purpose
    all_purposes: list[str] = []
    for p in profiles:
        all_purposes.extend(p.purpose)
    purpose = _union_lists(all_purposes, [])

    # Merge entities (case-insensitive)
    all_stakeholders = [s for p in profiles for s in p.stakeholders]
    stakeholders = _merge_by_key(all_stakeholders, lambda s: s.name.lower(), _merge_stakeholders)

    all_systems = [s for p in profiles for s in p.ai_systems]
    ai_systems = _merge_by_key(all_systems, lambda s: s.name.lower(), _merge_ai_systems)

    all_regs = [r for p in profiles for r in p.regulations]
    regulations = _merge_by_key(all_regs, lambda r: r.name.lower(), _merge_regulations)

    # Merge policies (exact match on policy_concept)
    all_policies = [pol for p in profiles for pol in p.policies]
    policies = _merge_by_key(all_policies, lambda p: p.policy_concept, _merge_policies)

    return PolicyProfile(
        organization=org,
        domain=domain,
        purpose=purpose,
        ai_systems=ai_systems,
        stakeholders=stakeholders,
        regulations=regulations,
        policies=policies,
        source_documents=sources,
    )
```

- [ ] **Step 7: Run all merge tests**

Run: `uv run pytest tests/test_merge.py -v`
Expected: ALL PASS

- [ ] **Step 8: Run full test suite to check for regressions**

Run: `uv run pytest -v`
Expected: ALL PASS (the new `source_documents` field defaults to `[]` so existing tests are unaffected)

- [ ] **Step 9: Commit**

```bash
git add src/risk_landscaper/merge.py tests/test_merge.py
git commit -m "feat: add merge_profiles for multi-document ingest

Policy merge with concept-keyed dedup, boundary example union, and
longer-definition preference. Entity merge case-insensitive by name.
Provenance tracked via source_documents.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Update CLI for multi-file support

**Files:**
- Modify: `src/risk_landscaper/cli.py:80-168`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for multi-file CLI validation**

Add to `tests/test_cli.py`:

```python
def test_run_multiple_missing_files():
    result = runner.invoke(app, [
        "run", "/nonexistent/a.md", "/nonexistent/b.md",
        "--output", "/tmp/out",
        "--base-url", "http://localhost:8000/v1",
        "--model", "test",
        "--nexus-base-dir", "/tmp/nexus",
    ])
    assert result.exit_code != 0
    assert "does not exist" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_run_multiple_missing_files -v`
Expected: FAIL — Typer rejects multiple positional args because `policy_file` is singular `Path`

- [ ] **Step 3: Update CLI to accept multiple files**

In `src/risk_landscaper/cli.py`, make the following changes:

Change the `run` command signature — replace the `policy_file` parameter with `policy_files`:

```python
@app.command()
def run(
    policy_files: list[Path] = typer.Argument(..., help="Policy document(s) (.md/.txt/.json/.pdf/.docx/.html)"),
```

Replace the single-file validation block with multi-file validation:

```python
    for pf in policy_files:
        if not pf.exists():
            typer.echo(f"Error: {pf} does not exist", err=True)
            raise typer.Exit(1)
```

Update the `report` creation to use joined filenames:

```python
    policy_set_name = ", ".join(pf.name for pf in policy_files)
    report = RunReport(
        model=config.model,
        policy_set=policy_set_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
```

Replace the single-file ingest block (Stage 1) with the multi-file loop:

```python
    # --- Stage 1: Ingest ---
    from risk_landscaper.stages.ingest import ingest as run_ingest

    profiles_to_merge: list[PolicyProfile] = []
    source_names: list[str] = []

    for pf in policy_files:
        text, detected_format, pre_parsed = _load_input(pf)
        fmt = input_format or detected_format
        source_names.append(pf.name)

        t_stage = time.monotonic()
        if pre_parsed is not None:
            profiles_to_merge.append(pre_parsed)
            typer.echo(f"Loaded pre-parsed profile from {pf.name}: {len(pre_parsed.policies)} policies")
            _stage_event("ingest", "document_ingested", t_stage, document=pf.name, skipped=True)
        else:
            typer.echo(f"Ingesting {pf.name} (format: {fmt})...")
            p = run_ingest(
                text, fmt, client, config,
                skip_enrichment=skip_enrichment,
                skip_entity_enrichment=skip_entity_enrichment,
                report=report,
            )
            _stage_event("ingest", "document_ingested", t_stage,
                         document=pf.name, policies_extracted=len(p.policies))
            profiles_to_merge.append(p)
            typer.echo(f"  Organization: {p.organization.name if p.organization else ''}")
            typer.echo(f"  Domain: {p.domain}")
            typer.echo(f"  Policies: {len(p.policies)}")

    if len(profiles_to_merge) > 1:
        from risk_landscaper.merge import merge_profiles
        t_stage = time.monotonic()
        profile = merge_profiles(profiles_to_merge, source_names)
        _stage_event("ingest", "profiles_merged", t_stage,
                     document_count=len(profiles_to_merge),
                     total_policies=len(profile.policies))
        typer.echo(f"Merged {len(profiles_to_merge)} documents: {len(profile.policies)} policies")
    elif profiles_to_merge:
        profile = profiles_to_merge[0]
        profile = profile.model_copy(update={"source_documents": source_names})
    else:
        typer.echo("Error: no documents to process", err=True)
        raise typer.Exit(1)

    report.stages_completed.append("ingest")
```

Update the ingest report metadata block:

```python
    profile_path = output / "policy-profile.json"
    profile_path.write_text(json.dumps(profile.model_dump(), indent=2))

    from risk_landscaper.reports import build_ingest_report
    meta = {
        "model": config.model,
        "policy_set": policy_set_name,
        "timestamp": report.timestamp,
        "source_documents": source_names,
        "input_format": fmt,
    }
    build_ingest_report(profile, report, output / "ingest-report.html", meta)
    typer.echo(f"Ingest report written to {output / 'ingest-report.html'}")
```

Update the `run_slug` in build_landscape to use the first file's stem:

```python
        run_slug=policy_files[0].stem,
```

- [ ] **Step 4: Run the multi-file validation test**

Run: `uv run pytest tests/test_cli.py::test_run_multiple_missing_files -v`
Expected: PASS

- [ ] **Step 5: Write test for single-file backward compatibility**

Add to `tests/test_cli.py`:

```python
def test_run_single_file_still_works():
    """Single positional file should still be accepted."""
    result = runner.invoke(app, [
        "run", "/nonexistent/policy.json",
        "--output", "/tmp/out",
        "--base-url", "http://localhost:8000/v1",
        "--model", "test",
        "--nexus-base-dir", "/tmp/nexus",
    ])
    assert result.exit_code != 0
    assert "does not exist" in result.output
```

- [ ] **Step 6: Run single-file test**

Run: `uv run pytest tests/test_cli.py::test_run_single_file_still_works -v`
Expected: PASS

- [ ] **Step 7: Run all CLI tests to check regressions**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ALL PASS

- [ ] **Step 8: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 9: Commit**

```bash
git add src/risk_landscaper/cli.py tests/test_cli.py
git commit -m "feat: accept multiple input documents in CLI

policy_file -> policy_files (list[Path]). Per-document ingest loop
with merge_profiles when multiple docs provided. Single-file path
unchanged. Reports track source_documents list.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Update CHANGELOG, CLAUDE.md, and README.md

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `CLAUDE.md`
- Modify: `README.md`

- [ ] **Step 1: Add entry to CHANGELOG.md under [Unreleased]**

Add under the existing `### Added` section in `[Unreleased]`:

```markdown
- **Multi-document ingest** — `risk-landscaper run` accepts multiple input files. Each document is ingested independently, then `PolicyProfile` objects are merged: policies deduplicated by `policy_concept` (boundary examples and enrichments unioned), entities merged by name (case-insensitive). `source_documents` field on `Policy` and `PolicyProfile` tracks provenance. Mixed formats supported (e.g., PDF + markdown).
```

- [ ] **Step 2: Update CLAUDE.md Running section**

Update the example command in CLAUDE.md to show multi-file usage:

```bash
uv run risk-landscaper run policy.json -o output/ \
  --base-url $REFINER_BASE_URL --model $REFINER_MODEL \
  --nexus-base-dir $NEXUS_BASE_DIR

# Multiple documents for the same org:
uv run risk-landscaper run policy.pdf faq.md annex.docx -o output/ \
  --base-url $REFINER_BASE_URL --model $REFINER_MODEL \
  --nexus-base-dir $NEXUS_BASE_DIR
```

- [ ] **Step 3: Update CLAUDE.md Pipeline Pattern section**

Add bullet to the Pipeline Pattern section:

```markdown
- Multi-document ingest: multiple files ingested independently, PolicyProfiles merged via `merge.py` (name-keyed dedup, enrichment union). `source_documents` provenance on Policy and PolicyProfile.
```

- [ ] **Step 4: Update README.md intro paragraph**

In `README.md`, update the intro paragraph (line 5) to mention multiple documents:

Replace:
```
Takes policy documents (markdown, JSON, or AI Atlas Nexus payloads) and produces structured risk artifacts: a **PolicyProfile** (system envelope) and a **RiskLandscape** (risk analysis with RiskCards). Together these constitute a complete Risk Card.
```

With:
```
Takes one or more policy documents (markdown, JSON, PDF, DOCX, HTML, or AI Atlas Nexus payloads) and produces structured risk artifacts: a **PolicyProfile** (system envelope) and a **RiskLandscape** (risk analysis with RiskCards). Together these constitute a complete Risk Card. Multiple documents for the same organization are ingested independently and merged into a single profile.
```

- [ ] **Step 5: Update README.md Usage section**

Add a multi-document example after the full pipeline example (after line 61):

```bash
# Multiple documents for the same org (PDF + markdown + annex)
uv run risk-landscaper run policy.pdf faq.md annex.docx -o output/ \
  --base-url http://localhost:8000/v1 \
  --model gemma-4-26b-a4b-it \
  --nexus-base-dir /path/to/ai-atlas-nexus
```

- [ ] **Step 6: Update README.md Input Formats section**

Add a note about multi-document support at the end of the Input Formats section (after line 86):

```markdown

Multiple files can be passed as positional arguments. Each document is ingested independently (with its own format detection), then the resulting `PolicyProfile` objects are merged — policies deduplicated by concept, entities merged by name. This supports mixed-format inputs (e.g., a PDF policy document alongside a markdown FAQ).
```

- [ ] **Step 7: Commit**

```bash
git add CHANGELOG.md CLAUDE.md README.md
git commit -m "docs: document multi-document ingest in changelog, dev guide, and readme

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```
