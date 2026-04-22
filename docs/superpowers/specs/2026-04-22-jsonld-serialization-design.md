# JSON-LD Serialization for RiskLandscape

**Date:** 2026-04-22
**Status:** Design
**Scope:** RiskLandscape + RiskCards (PolicyProfile serialization deferred)

---

## Goal

Emit the RiskLandscape as valid JSON-LD using AIRO, VAIR, DPV, and Nexus ontology IRIs, making the output composable with Nexus triples and the AIROO advisory data foundation. Turtle output as an optional secondary format via `rdflib`.

### Priority consumers

1. **AIROO advisory data foundation** — the advisory model's `Risk` entity references RiskCards by `risk_id`. JSON-LD with Nexus IRIs makes them joinable in a triplestore.
2. **Interop demonstrations** — papers, presentations showing AIRO-aligned output.
3. **AIRO-aware tools** — SPARQL-queryable risk documentation.

---

## Approach

Pure JSON-LD context mapping with no required dependencies. A hand-crafted `@context` dict maps Pydantic field names to ontology IRIs. Turtle output via optional `rdflib` dependency.

---

## Namespaces

```
airo:    https://w3id.org/airo#
vair:    https://w3id.org/vair#
nexus:   https://ibm.github.io/ai-atlas-nexus/ontology/
dpv:     https://w3id.org/dpv#
rl:      https://trustyai.io/risk-landscaper/
```

The `rl:` namespace covers fields with no published ontology equivalent: `materialization_conditions`, `cross_mappings`, `related_policies`, `coverage_gaps`, `evaluations`, `evaluatesRiskConcept`.

---

## Field Mapping

### RiskCard

| Pydantic field | JSON-LD target | Notes |
|---|---|---|
| `risk_id` | `@id` (as `nexus:{risk_id}`) | Join key with Nexus/AIROO |
| (type) | `@type: airo:Risk` | |
| `risk_name` | `rdfs:label` | |
| `risk_description` | `rdfs:comment` | |
| `risk_concern` | `rl:riskConcern` | No AIRO equivalent |
| `risk_framework` | `rl:riskFramework` | |
| `cross_mappings` | `rl:crossMapping` | |
| `risk_type` | `rl:riskType` | |
| `descriptors` | `rl:descriptor` | |
| `risk_sources` | `airo:isRiskSourceFor` (`@reverse`) | Risk owns sources, AIRO models the inverse |
| `consequences` | `airo:hasConsequence` | |
| `impacts` | `airo:hasImpact` | |
| `trustworthy_characteristics` | `rl:trustworthyCharacteristic` | Lewis et al characteristics |
| `aims_activities` | `rl:aimsActivity` | Lewis et al AIMS mapping |
| `controls` | `airo:modifiesRiskConcept` (`@reverse`) | Controls target risk concepts |
| `materialization_conditions` | `rl:materializationConditions` | |
| `incidents` | `dpv:Incident` | DPV risk extension |
| `evaluations` | `rl:evaluation` | |
| `risk_level` | `rl:riskLevel` | |
| `related_policies` | `rl:relatedPolicy` | |

### RiskSource

| Field | JSON-LD target |
|---|---|
| (type) | `airo:RiskSource` |
| `description` | `rdfs:comment` |
| `source_type` | `@type` override to VAIR subclass IRI |
| `likelihood` | `airo:hasLikelihood` |
| `exploits_vulnerability` | `rl:exploitsVulnerability` |

### RiskConsequence

| Field | JSON-LD target |
|---|---|
| (type) | `airo:Consequence` |
| `description` | `rdfs:comment` |
| `likelihood` | `airo:hasLikelihood` |
| `severity` | `airo:hasSeverity` |

### RiskImpact

| Field | JSON-LD target |
|---|---|
| (type) | `airo:Impact` |
| `description` | `rdfs:comment` |
| `severity` | `airo:hasSeverity` |
| `area` | `airo:hasImpactOnArea` |
| `affected_stakeholders` | `airo:hasImpactOnStakeholder` |
| `harm_type` | VAIR subclass IRI (best-effort) |

### RiskControl

| Field | JSON-LD target |
|---|---|
| (type) | `airo:RiskControl` |
| `description` | `rdfs:comment` |
| `control_type` | Determines property: `detect` -> `airo:detectsRiskConcept`, `evaluate` -> `rl:evaluatesRiskConcept`, `mitigate` -> `airo:mitigatesRiskConcept`, `eliminate` -> `airo:eliminatesRiskConcept` |
| `targets` | `rl:controlTargets` |

### RiskIncidentRef

| Field | JSON-LD target |
|---|---|
| (type) | `dpv:Incident` |
| `name` | `rdfs:label` |
| `description` | `rdfs:comment` |
| `source_uri` | `rdfs:seeAlso` |
| `status` | `rl:incidentStatus` |

### EvaluationRef

| Field | JSON-LD target |
|---|---|
| (type) | `rl:Evaluation` |
| `eval_id` | `@id` |
| `eval_type` | `rl:evalType` |
| `timestamp` | `rl:timestamp` |
| `summary` | `rdfs:comment` |
| `metrics` | `rl:metrics` |
| `source_uri` | `rdfs:seeAlso` |

### RiskLandscape envelope

| Field | JSON-LD target |
|---|---|
| (type) | `rl:RiskLandscape` |
| `@id` | `rl:{run_slug}` |
| `version` | `rl:version` |
| `risks` | `rl:hasRiskCard` |
| `provenance` | `rl:provenance` |
| `framework_coverage` | `rl:frameworkCoverage` |
| `coverage_gaps` | `rl:coverageGap` |

Envelope metadata fields (`model`, `timestamp`, `run_slug`, `selected_domains`, `policy_source`, `knowledge_base`, `policy_mappings`, `weak_matches`) are included under `rl:` namespace. They are operational metadata, not ontology-aligned.

---

## VAIR Type Resolution

VAIR type IDs from `vair.py` map directly to `vair:{id}` IRIs:

```
AdversarialAttack  -> vair:AdversarialAttack
BiasedTrainingData -> vair:BiasedTrainingData
Bias               -> vair:Bias
Death              -> vair:Death
...
```

Parent category mapping for `source_type`:

```
attack         -> vair:Attack
data           -> vair:DataRiskSource
organisational -> vair:OrganisationalRiskSource
performance    -> vair:PerformanceRiskSource
system         -> vair:SystemRiskSource
```

Values not matching any VAIR type remain as string literals.

---

## Module Structure

### `src/risk_landscaper/serialize.py`

```python
def landscape_to_jsonld(landscape: RiskLandscape) -> dict
```

Returns a plain Python dict that is valid JSON-LD. No dependencies. Callers use `json.dumps()` to write.

```python
def landscape_to_turtle(landscape: RiskLandscape) -> str
```

Requires `rdflib` (optional `[rdf]` extra). Calls `landscape_to_jsonld()` internally, parses with rdflib's JSON-LD plugin, serializes to Turtle. Raises `ImportError` with a helpful message if not installed.

### Output shape

```json
{
  "@context": {
    "airo": "https://w3id.org/airo#",
    "vair": "https://w3id.org/vair#",
    "nexus": "https://ibm.github.io/ai-atlas-nexus/ontology/",
    "dpv": "https://w3id.org/dpv#",
    "rl": "https://trustyai.io/risk-landscaper/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "risks": {"@id": "rl:hasRiskCard", "@container": "@set"},
    "risk_sources": {"@id": "airo:isRiskSourceFor", "@reverse": true},
    "consequences": {"@id": "airo:hasConsequence"},
    "impacts": {"@id": "airo:hasImpact"},
    "controls": {"@id": "airo:modifiesRiskConcept", "@reverse": true},
    ...
  },
  "@id": "rl:run-2026-04-22T10-00-00",
  "@type": "rl:RiskLandscape",
  "rl:version": "0.2",
  "risks": [
    {
      "@id": "nexus:bias-discrimination-output",
      "@type": "airo:Risk",
      "rdfs:label": "Bias/Discrimination in Output",
      "risk_sources": [
        {
          "@type": ["airo:RiskSource", "vair:BiasedTrainingData"],
          "rdfs:comment": "Training data contains demographic imbalances",
          "airo:hasLikelihood": "likely"
        }
      ],
      "consequences": [ ... ],
      "controls": [ ... ]
    }
  ]
}
```

---

## CLI Integration

### `--format` flag on `run`

```
risk-landscaper run policy.json -o output/ --format jsonld
risk-landscaper run policy.json -o output/ --format turtle
```

Accepts: `yaml` (default), `jsonld`, `turtle`. The JSON-LD/Turtle file is written alongside the existing YAML — additive, not a replacement.

Output files when `--format jsonld`:
- `output/risk-landscape.yaml` (always)
- `output/risk-landscape.jsonld` (additional)

### `export` subcommand

```
risk-landscaper export risk-landscape.yaml --format jsonld -o output/
risk-landscaper export risk-landscape.yaml --format turtle -o output/
```

Loads existing YAML, deserializes to `RiskLandscape`, serializes to the target format. Default format: `jsonld`.

---

## Dependencies

- **JSON-LD:** No new dependencies. Pure dict construction.
- **Turtle:** `rdflib` as optional extra (`[rdf]`). Pattern matches existing `[docs]` extra for markitdown.

```toml
[project.optional-dependencies]
rdf = ["rdflib>=7.0"]
```

---

## Testing

### `tests/test_serialize.py` (~12-15 tests)

**JSON-LD structure:**
- Context contains all required namespace prefixes
- RiskCard `@id` uses `nexus:` prefix with `risk_id`
- RiskCard `@type` is `airo:Risk`
- Causal chain properties map to correct AIRO IRIs

**VAIR resolution:**
- Each parent category maps to correct VAIR IRI
- Specific VAIR types from enrichment resolve to `vair:{id}`
- Unknown values produce string literals

**Edge cases:**
- Empty RiskLandscape (no risks) serializes cleanly
- Minimal RiskCard (only required fields) produces valid JSON-LD
- `None` optional fields are omitted, not serialized as `null`

**Control type mapping:**
- `detect` -> `airo:detectsRiskConcept`
- `evaluate` -> `rl:evaluatesRiskConcept`
- `mitigate` -> `airo:mitigatesRiskConcept`
- `eliminate` -> `airo:eliminatesRiskConcept`

**Turtle (conditional):**
- `pytest.importorskip("rdflib")`
- Verify output parses without error
- Verify expected triples present (subject with `airo:Risk` type, `airo:hasConsequence` predicate)

**CLI:**
- `export` subcommand: load fixture YAML, export to JSON-LD, verify file written and parseable
- `--format` flag: verify additional file appears in output directory

---

## Omitted fields

The `provenance` field on `RiskSource`, `RiskConsequence`, `RiskImpact`, and `RiskControl` (values: `nexus`, `vair`, `heuristic`, `llm`) is internal pipeline metadata — omitted from JSON-LD output. Similarly, `related_actions` (backward-compat alias) is omitted.

---

## Non-goals

- PolicyProfile serialization (deferred — separate follow-up)
- OWL validation of output against AIRO ontology
- SHACL shape conformance checking
- Blank node minimization or RDF canonicalization
- Resolving AIRO properties not in published OWL (`isRiskSourceFor` direction may need `@reverse` or a custom property — we use `@reverse` on the context and document the choice)
