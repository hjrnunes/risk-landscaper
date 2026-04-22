# Multi-Document Ingest Design

Support ingesting multiple documents for a single organization/policy set. A governance framework often spans several documents — a main policy, supplementary guidelines, FAQ/clarification docs, annexes — and the landscaper should synthesize them into one `PolicyProfile`.

## Approach: Per-Document Ingest + Merge

Run `ingest()` independently on each document, then merge the resulting `PolicyProfile` objects. This reuses the existing chunking/dedup infrastructure and naturally handles mixed formats (PDF policy + markdown FAQ + HTML annex).

```
                   ┌─────────────┐
  policy.pdf  ───> │  ingest()   │──> PolicyProfile A
                   └─────────────┘
                                        │
  faq.md      ───> ┌─────────────┐      ▼
                   │  ingest()   │──> PolicyProfile B ──> merge_profiles([A,B,C])
                   └─────────────┘                              │
  annex.docx  ───> ┌─────────────┐                              ▼
                   │  ingest()   │──> PolicyProfile C      PolicyProfile (merged)
                   └─────────────┘                              │
                                                                ▼
                                                    detect_domain -> map_risks -> ...
```

### Why not concatenate-then-ingest?

- Context overflow: combined docs may exceed model window even with chunking
- Mixed formats: can't concatenate a PDF and a JSON
- Provenance: harder to track which document contributed which policy
- The chunked ingest path already does per-chunk extraction + merge — this extends the same pattern to per-document

## CLI Interface

Accept multiple positional files:

```bash
# Single file (unchanged)
risk-landscaper run policy.pdf -o output/

# Multiple files
risk-landscaper run policy.pdf faq.md annex.docx -o output/

# Glob
risk-landscaper run docs/*.md -o output/
```

```python
@app.command()
def run(
    policy_files: list[Path] = typer.Argument(..., help="Policy document(s)"),
    ...
)
```

Typer supports `list[Path]` as a variadic positional argument. Single-file usage is backward compatible.

## Merge Strategy

New function `merge_profiles(profiles: list[PolicyProfile], sources: list[str]) -> PolicyProfile`.

### Organization

Pick the richest: prefer the `Organization` with the most non-None fields. If names differ, log a warning and use the first. Merge list fields (governance_roles, certifications, delegates) via union.

### Policies

Merge key: `policy_concept` (exact match, same as chunked dedup).

When the same concept appears in multiple documents:
- **Definition**: keep the longer/richer one
- **Enrichment fields** (boundary_examples, acceptable_uses, risk_controls): union — each document may contribute different examples
- **Scalar fields** (governance_function, human_involvement): prefer the first non-None value
- **Decomposition**: prefer the first non-None

New policies (concept not seen before) are appended.

### Stakeholders

Merge key: `name` (case-insensitive).

- Union `roles` and `interests`
- For AIRO involvement fields (involvement, activity, awareness, output_control, relationship): prefer first non-None. If conflicting values appear across documents, log warning and keep first.

### AI Systems

Merge key: `name` (case-insensitive).

- Union `purpose`, `techniques`, `serves_stakeholders`, `assets`
- Scalar fields (modality, automation_level, risk_level): prefer first non-None

### Regulations

Merge key: `name` (case-insensitive).

- Prefer non-None `jurisdiction`, `reference`

### Domain / Purpose

- `domain`: if all docs agree, use that; if they differ, keep the most specific (longest) or defer to `detect_domain`
- `purpose`: union all purpose strings

## Provenance Tracking

Add `source_documents: list[str]` to `Policy`:

```python
class Policy(BaseModel):
    ...
    source_documents: list[str] = []
```

Each policy gets tagged with the filename(s) it was extracted from. When policies merge, the source_documents lists are unioned. Backward-compatible (defaults to `[]`).

Also add to `PolicyProfile`:

```python
class PolicyProfile(BaseModel):
    ...
    source_documents: list[str] = []
```

This records the full set of input documents for the run.

## Merge Implementation

Located in `stages/ingest.py` alongside existing chunked merge logic.

```python
def merge_profiles(
    profiles: list[PolicyProfile],
    sources: list[str],
) -> PolicyProfile:
    """Merge multiple per-document PolicyProfiles into one."""
```

### Merge helpers

Generic merge pattern for named entities:

```python
def _merge_by_name(
    items: list[T],
    merge_fn: Callable[[T, T], T],
) -> list[T]:
    """Merge a list of named entities, combining duplicates by name."""
```

Per-type merge functions:

```python
def _merge_stakeholders(a: Stakeholder, b: Stakeholder) -> Stakeholder: ...
def _merge_ai_systems(a: AiSystem, b: AiSystem) -> AiSystem: ...
def _merge_regulations(a: RegulatoryReference, b: RegulatoryReference) -> RegulatoryReference: ...
def _merge_organizations(a: Organization, b: Organization) -> Organization: ...
def _merge_policies(a: Policy, b: Policy) -> Policy: ...
```

## Reporting

### RunReport events

```python
{"stage": "ingest", "event": "multi_document_ingest", "document_count": 3, "documents": ["policy.pdf", "faq.md", "annex.docx"]}
{"stage": "ingest", "event": "document_ingested", "document": "policy.pdf", "policies_extracted": 12}
{"stage": "ingest", "event": "profiles_merged", "total_policies": 18, "deduplicated": 3}
```

### Ingest report metadata

`meta["source_documents"]` replaces `meta["source_document"]` (list instead of string). The ingest report template should display all source documents.

## Pipeline Changes

### CLI (`cli.py`)

1. Change `policy_file: Path` to `policy_files: list[Path]`
2. Validate all files exist
3. If single file: existing path (unchanged behavior)
4. If multiple files: loop `_load_input()` + `ingest()` per file, then `merge_profiles()`
5. `report.policy_set` becomes comma-joined filenames

### Downstream stages

No changes. The merged `PolicyProfile` feeds into `detect_domain` → `map_risks` → ... exactly as before.

## Edge Cases

- **All documents are pre-parsed JSON**: merge the `PolicyProfile` objects directly (no ingest needed)
- **Mix of pre-parsed and raw**: ingest the raw ones, then merge all profiles together
- **Conflicting organizations**: warn, use first. The user can override with `--organization-override`
- **Empty documents**: skip with warning, don't contribute to merged profile
- **Single file**: identical behavior to current — no merge step needed

## Test Plan

1. **Unit: merge_profiles** — merge 2-3 profiles with overlapping policies, stakeholders, systems
2. **Unit: _merge_policies** — same concept with different enrichments → union boundary_examples
3. **Unit: _merge_stakeholders** — same name, different roles → union
4. **Unit: provenance** — source_documents populated correctly after merge
5. **Integration: CLI multi-file** — pass 2 markdown files, verify merged output
6. **Battery: mixed formats** — PDF + markdown for same org
7. **Regression: single file** — existing behavior unchanged
