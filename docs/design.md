# Risk Landscaper Design — AIRO Risk Card Alignment

This document captures the design for evolving the risk landscaper into an AIRO-aligned AI risk documentation tool.

## Vision

The risk landscaper produces structured risk artifacts that multiple consumers can use. The red-team pipeline is one consumer, not the primary driver. The tool supports risk-use case capturing, tying in governance, regulation, and data interop with model cards, guardrails metadata, etc.

## Standards Stack

The causal chain follows an established standards hierarchy:

1. **ISO 31000/31073** — conceptual model: RiskSource -> (exploits Vulnerability) -> Risk Event -> Consequence -> Impact
2. **AIRO** (Golpayegani, Pandit, Lewis) — OWL formalisation with four classes under `airo:RiskConcept`:
   - `RiskSource --isRiskSourceFor--> Risk --hasConsequence--> Consequence --hasImpact--> Impact`
   - `hasLikelihood` on any RiskConcept, `hasSeverity` on Consequence/Impact
   - Controls via `modifiesRiskConcept` with sub-properties: detects, eliminates, mitigates
3. **DPV risk extension** (W3C DPVCG) — base vocabulary AIRO imports; adds RiskSource, Threat, Vulnerability, Incident, risk matrices
4. **VAIR** (Vocabulary of AI Risks) — AI-specific subtypes for chain nodes (data/model/attack source types, bias/discrimination consequences, wellbeing/rights impacts)
5. **PROV-O** (W3C Provenance Ontology) — `prov:Entity`, `prov:Activity`, `prov:Agent` with `wasAttributedTo`, `wasGeneratedBy`, `wasAssociatedWith` relationships. Used in JSON-LD serialization to track which subsystem (Nexus, VAIR, heuristics, LLM) produced each causal chain element.

## Output Architecture

```
output/
  policy-profile.json     <- system envelope (PolicyProfile)
  risk-landscape.yaml     <- risk analysis (RiskLandscape with RiskCards)
  run-report.json         <- execution metadata
```

Together, `policy-profile.json` + `risk-landscape.yaml` constitute a complete Risk Card.

## Data Model (v0.2)

### Envelope Types

**Organization** — the entity disclosing trustworthy characteristics. Replaces Stakeholder for the `organization` field. Distinguished from Stakeholders (agents toward whom characteristics are exhibited).

```
Organization
  name, description
  governance_roles: list[str]     # governing_body, top_management, ai_team
  management_system: str          # ISO/IEC 42001, internal, etc.
  certifications: list[str]
  delegates: list[str]            # actsOnBehalfOf
```

**Stakeholder** — with AIRO involvement modeling and Lewis linkage:

```
Stakeholder
  name, roles, description
  involvement: intended | unintended
  activity: active | passive
  awareness: informed | uninformed
  output_control: challenge | correct | cannot_opt_out
  relationship: internal | external
  interests: list[str]            # trustworthy characteristics they care about
```

**Policy** — with governance function (Lewis et al ISO/IEC 38500):

```
Policy
  policy_concept, concept_definition
  governance_function: direct | evaluate | monitor
  boundary_examples, acceptable_uses, risk_controls, human_involvement
  affects_stakeholders, applies_to_systems
  decomposition: PolicyDecomposition (agent/activity/entity)
```

**AiSystem** — with model card interop and Lewis asset modeling:

```
AiSystem
  name, description, purpose, risk_level
  modality: str                   # software, embedded, service
  techniques: list[str]           # deep_learning, statistical_model, etc.
  automation_level: str           # full, partial, human_in_loop
  serves_stakeholders: list[str]
  assets: list[str]
```

### Causal Chain Types

```
RiskSource
  description, source_type (VAIR), likelihood, exploits_vulnerability

RiskConsequence
  description, likelihood, severity

RiskImpact
  description, severity
  area: str           # AIRO AreaOfImpact: health, safety, fundamental_rights, etc.
  affected_stakeholders: list[str]
  harm_type: str      # Shelby+: representational, allocative, quality_of_service, etc.

RiskControl
  description
  control_type: detect | evaluate | mitigate | eliminate
  targets: str        # chain level: source, risk, consequence, impact
```

### Evidence and Governance Types

```
RiskIncidentRef
  name, description, source_uri
  status: ongoing | concluded | mitigated | halted | near_miss

EvaluationRef
  eval_id, eval_type (lm-eval, garak, manual, monitoring)
  timestamp, summary, metrics: dict, source_uri

GovernanceProvenance
  produced_by, governance_function
  aims_activities: list[str]      # which AIMS activities this satisfies
  reviewed_by: list[str]
  review_status: draft | reviewed | approved
```

### RiskCard

Replaces RiskDetail. Carries the full AIRO causal chain, typed controls, evidence, governance metadata, and policy links. `RiskDetail` is a backward-compat alias.

```
RiskCard
  # Identity
  risk_id, risk_name, risk_description, risk_concern
  risk_framework, cross_mappings
  risk_type                       # input, output, training-data, inference, non-technical, agentic
  descriptors                     # "amplified by generative AI", etc.

  # Causal chain
  risk_sources: list[RiskSource]
  consequences: list[RiskConsequence]
  impacts: list[RiskImpact]

  # Governance
  trustworthy_characteristics     # ISO/IEC 24028: safety, security, privacy, fairness, etc.
  aims_activities                 # Lewis et al AIMS mapping: aimsA6, aimsA13, etc.

  # Controls
  controls: list[RiskControl]

  # Materialization
  materialization_conditions: str

  # Evidence
  incidents: list[RiskIncidentRef]
  evaluations: list[EvaluationRef]

  # Assessment
  risk_level: str                 # very_low...very_high

  # Links
  related_policies: list[str]
  related_actions: list[str]      # backward compat
```

### RiskLandscape (v0.2)

`risks: list[RiskCard]` replaces `list[RiskDetail]`. Adds `provenance: GovernanceProvenance`. All other fields unchanged.

## Sourcing Strategy for Chain Data

Three layers, progressively richer. All three are implemented.

1. **Nexus lookup (free)** — `related_actions` -> controls, incidents -> incidents, `risk_type` -> card field, `descriptor` -> descriptors. Baseline RiskSource created from risk description + inferred source_type. Control type (`detect | evaluate | mitigate | eliminate`) and targets (`source | risk | consequence`) inferred from action description keywords.
2. **VAIR vocabulary matching (cheap)** — keyword matching from VAIR v1.0 ontology. Sources (22 types), consequences (7 types), impacts (9 types), impacted areas (5 types). Free-layer enrichment in `build_landscape`, no LLM calls.
3. **LLM-assisted synthesis (expensive)** — `enrich_chains` stage for primary-relevance risks. Given risk description + concern + policy context, reasons about risk sources, consequences, impacts, materialization conditions. Skippable with `--skip-chain-enrichment`.

A card is valid with just identity + policy links. The chain enriches it progressively.

## Entity Enrichment (Ingest Pass 4)

A dedicated LLM pass enriches entities extracted during context extraction (pass 1) with AIRO-grounded attributes:

- **Stakeholders** — involvement (intended/unintended), activity (active/passive), awareness (informed/uninformed), output_control (challenge/correct/cannot_opt_out), relationship (internal/external), interests
- **AI systems** — modality (text-to-text, multimodal, etc.), techniques (deep learning, RAG, etc.), automation_level (fully automated, human-in-the-loop, advisory)
- **Organization** — governance_roles, management_system, certifications, delegates
- **Regulatory references** — jurisdiction, reference

The LLM receives the original document text plus the list of already-identified entities, and returns structured attributes for each. Empty-string responses are normalized to `None`. Entities missing from the LLM response retain their original values.

**Limitation**: Nexus pre-parsed inputs bypass ingest entirely, so entity enrichment is not available for those inputs. The Nexus adapter creates entities from structured data, but AIRO involvement fields remain unpopulated since there is no natural-language document to extract from.

## Governance Alignment

### Three Governance Layers

1. **Lewis et al** — ontological foundation: Activity/Entity/Agent, governance relationships, AIMS mappings
2. **UGA** (IBM) — governance workflow: intent -> questionnaire -> risk -> model selection -> guardrails
3. **GAF-Guard** (IBM) — agentic runtime: distributes UGA workflow across agents with tool access

The RiskLandscape is the governance artifact, not a governance system. It must be rich enough for automated consumers, machine-readable, provenance-aware, and evaluable.

### AIMS Activity Mapping

| AIMS Activity | Our Stack |
|---|---|
| A2: Stakeholder identification | `PolicyProfile.stakeholders` with AIRO involvement |
| A4: AI policy establishment | `PolicyProfile.policies` |
| A6: Risk assessment | `RiskLandscape` + `RiskCard` (core output) |
| A8: Controls implementation | `RiskCard.controls` |
| A9: Performance evaluation | `RiskCard.evaluations` (EvaluationRef) |

### Policy governance_function -> Tool Selection

| governance_function | Red-team pipeline | Guardrails | GAF-Guard |
|---|---|---|---|
| `direct` | Adversarial prompts testing boundaries | Rule definition | Pre-deployment risk gate |
| `evaluate` | lm-eval tasks with pass/fail criteria | Threshold config | Assessment questionnaire |
| `monitor` | Drift detection probes | Alert trigger | Post-deployment monitoring |

## PROV-O Provenance

The JSON-LD serialization uses W3C PROV-O to make data lineage explicit. Every causal chain element that carries an internal `provenance` tag gets two triples:

- `prov:wasAttributedTo` — which agent produced the data
- `prov:wasGeneratedBy` — which pipeline activity produced the data

### Agents

| Internal tag | PROV-O Agent IRI | Description |
|---|---|---|
| `nexus` | `rl:NexusKnowledgeGraph` | AI Atlas Nexus knowledge graph |
| `vair` | `rl:VAIRMatcher` | VAIR v1.0 vocabulary keyword matcher |
| `heuristic` | `rl:HeuristicEngine` | Rule-based inference (source type, control type) |
| `llm` | `rl:LLMAgent` | LLM-assisted synthesis |

### Activities

| Activity IRI | Pipeline stage | Produces |
|---|---|---|
| `rl:BuildLandscape` | `build_landscape` | Nexus, VAIR, and heuristic elements |
| `rl:EnrichChains` | `enrich_chains` | LLM-synthesized causal chains |

### Landscape-level provenance

The `RiskLandscape` is typed as `prov:Entity`. When `GovernanceProvenance` is present, it serializes as a `prov:Activity` node under `prov:wasGeneratedBy`, with `prov:wasAssociatedWith` pointing to the producing tool and `prov:endedAtTime` carrying the run timestamp.

The internal Pydantic models are unchanged — the PROV-O mapping lives entirely in `serialize.py`.

## Interoperability

### RiskCard as Interop Hub

The RiskCard is richer than all its projection targets. Data flows outward from it.

**Projection 1: RiskCard -> Model Card `considerations`**

| RiskCard field | Model Card target |
|---|---|
| risk_name + risk_concern | ethical_considerations[].name |
| controls[].description | ethical_considerations[].mitigation_strategy |
| impacts[].affected_stakeholders | considerations.users[] |
| materialization_conditions | use_cases[] or out_of_scope_uses[] |
| coverage gaps | considerations.limitations[] |

The better path: a `RiskLandscapeReference` in the model card schema (like the D4D `DatasetReference` pattern).

**Projection 2: RiskCard -> lm-eval task generation**

| RiskCard field | lm-eval config field |
|---|---|
| risk_type | task type selection |
| materialization_conditions | doc_to_text prompt template |
| impacts[].harm_type | metric_list selection |
| related_policies | evaluation criteria (pass/fail) |
| incidents[].description | few-shot examples / seeds |

**Projection 3: lm-eval results -> EvaluationRef**

Results flow back to the RiskCard that motivated the test. `eval_id` is the join key.

## Backward Compatibility

- `RiskDetail = RiskCard` alias
- `related_actions` preserved on RiskCard
- `_coerce_organization` migrates legacy Stakeholder-shaped dicts to Organization
- `_migrate_governed_systems` handles old `governed_systems` field name
- All new fields default to `None`/`[]` so existing serialized data parses without changes
- Refiner downstream reads risk-landscape.yaml and ignores unknown fields via Pydantic defaults
