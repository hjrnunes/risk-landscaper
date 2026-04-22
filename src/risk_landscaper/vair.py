"""VAIR (Vocabulary of AI Risks) keyword matching.

Static extraction of VAIR v1.0 types with keyword-based matching against
risk description/concern text. No LLM calls, no ontology parsing.

Source: VAIR v1.0 ontology — https://w3id.org/vair
Authors: Golpayegani, Pandit, Lewis (ADAPT Centre, Trinity College Dublin)
Paper: "To Be High-Risk, or Not To Be" (FAccT 2023)
License: CC-BY-4.0

The type enumerations and hierarchy below were manually extracted from the
VAIR OWL ontology (vair.ttl). Keywords are project-specific heuristics,
not part of the ontology itself. When updating, diff against the canonical
ontology at https://w3id.org/vair .
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VairType:
    id: str
    label: str
    parent: str
    keywords: list[str]


# --- RiskSource hierarchy ---
# Parent categories map to the coarse source_type used elsewhere

RISK_SOURCES: list[VairType] = [
    # Attack subtypes
    VairType("AdversarialAttack", "Adversarial Attack", "attack",
             ["adversarial", "perturbation", "adversarial example", "adversarial input"]),
    VairType("Cyberattack", "Cyberattack", "attack",
             ["cyberattack", "cyber attack", "intrusion", "breach"]),
    VairType("DataPoisoning", "Data Poisoning", "attack",
             ["data poisoning", "poison", "manipulate training", "taint"]),
    VairType("ModelEvasion", "Model Evasion", "attack",
             ["evasion", "evade", "bypass detection", "circumvent"]),
    VairType("ModelInversion", "Model Inversion", "attack",
             ["model inversion", "inversion attack", "reconstruct training", "extract data from model"]),

    # Data subtypes
    VairType("BiasedTrainingData", "Biased Training Data", "data",
             ["biased training", "biased data", "training bias", "unbalanced data"]),
    VairType("ErroneousTrainingData", "Erroneous Training Data", "data",
             ["erroneous training", "incorrect training data", "noisy training", "mislabel"]),
    VairType("IncompleteTrainingData", "Incomplete Training Data", "data",
             ["incomplete training", "missing training data", "insufficient training data"]),
    VairType("UnrepresentativeTrainingData", "Unrepresentative Training Data", "data",
             ["unrepresentative", "non-representative", "skewed sample", "selection bias"]),
    VairType("IrrelevantTrainingData", "Irrelevant Training Data", "data",
             ["irrelevant training", "out of scope data"]),
    VairType("ErroneousInputData", "Erroneous Input Data", "data",
             ["erroneous input", "incorrect input", "malformed input", "noisy input"]),
    VairType("ErrorInDataCollection", "Error in Data Collection", "data",
             ["data collection error", "collection bias", "sampling error"]),
    VairType("ErrorInDataPrepration", "Error in Data Preparation", "data",
             ["data preparation", "preprocessing error", "data cleaning error", "feature engineering error"]),
    VairType("WrongDataSetDesignChoice", "Wrong Dataset Design Choice", "data",
             ["wrong dataset", "dataset design", "inappropriate dataset"]),
    VairType("UnavailabilityOfDataSet", "Unavailability of Dataset", "data",
             ["unavailable data", "data unavailability", "missing dataset", "data loss"]),

    # Organisational subtypes
    VairType("InsufficientHumanOversightMeasure", "Insufficient Human Oversight Measure", "organisational",
             ["insufficient oversight", "lack of oversight", "inadequate oversight", "no human oversight"]),
    VairType("InsufficientInstruction", "Insufficient Instruction", "organisational",
             ["insufficient instruction", "inadequate documentation", "unclear guidance", "lack of instruction"]),
    VairType("LackOfTransparency", "Lack of Transparency", "organisational",
             ["lack of transparency", "opaque", "black box", "unexplainable", "not transparent"]),
    VairType("StaffIncompetence", "Staff Incompetence", "organisational",
             ["staff incompetence", "inadequate training", "unqualified", "insufficient expertise"]),

    # Performance subtypes
    VairType("LowAccuracy", "Low Accuracy", "performance",
             ["low accuracy", "inaccurate", "inaccuracy", "poor accuracy", "incorrect prediction",
              "incorrect recommendation", "wrong decision"]),
    VairType("LowRobustness", "Low Robustness", "performance",
             ["low robustness", "fragile", "brittle", "not robust", "sensitive to perturbation"]),
    VairType("LowSecurity", "Low Security", "performance",
             ["low security", "insecure", "security gap", "vulnerability", "weak security"]),

    # System subtypes
    VairType("SystemVulnerability", "System Vulnerability", "system",
             ["system vulnerability", "infrastructure vulnerability", "software vulnerability"]),
]

# --- Consequence types ---

CONSEQUENCES: list[VairType] = [
    VairType("Bias", "Bias", "consequence",
             ["bias", "biased", "prejudice", "stereotyp", "discriminat", "unfair"]),
    VairType("DecreasedRobustness", "Decreased Robustness", "consequence",
             ["decreased robustness", "robustness degradation", "less robust", "instability"]),
    VairType("DecreasedSecurity", "Decreased Security", "consequence",
             ["decreased security", "security degradation", "compromised security", "security breach"]),
    VairType("DegradedAccuracy", "Degraded Accuracy", "consequence",
             ["degraded accuracy", "accuracy loss", "accuracy degradation", "less accurate", "hallucin"]),
    VairType("ExploitationOfVulnerability", "Exploitation of Vulnerability", "consequence",
             ["exploit", "vulnerability exploitation", "take advantage of"]),
    VairType("ImpairedDecisionMaking", "Impaired Decision Making", "consequence",
             ["impaired decision", "poor decision", "wrong decision", "decision-making error",
              "misinformation", "misleading"]),
    VairType("MaterialDistortionOfBehaviour", "Material Distortion of Behaviour", "consequence",
             ["distortion of behaviour", "behavioral distortion", "manipulat", "behavior modification",
              "subliminal", "deceptive"]),
]

# --- Impact types ---

IMPACTS: list[VairType] = [
    VairType("DiscriminatoryTreatment", "Discriminatory Treatment", "impact",
             ["discriminatory treatment", "discriminat", "unequal treatment", "unfair outcome"]),
    VairType("DetrimentalTreatment", "Detrimental Treatment", "impact",
             ["detrimental treatment", "adverse treatment", "negative treatment"]),
    VairType("UnfavourableTreatment", "Unfavourable Treatment", "impact",
             ["unfavourable treatment", "unfavorable", "disadvantage"]),
    VairType("Harm", "Harm", "impact",
             ["harm", "damage", "injury", "adverse effect", "negative impact"]),
    VairType("Overreliance", "Overreliance", "impact",
             ["overreliance", "over-reliance", "over reliance", "automation bias",
              "excessive trust", "blind trust"]),
    # WellbeingImpact subtypes
    VairType("Death", "Death", "wellbeing_impact",
             ["death", "fatal", "lethal", "loss of life", "mortality"]),
    VairType("PhysicalInjury", "Physical Injury", "wellbeing_impact",
             ["physical injury", "bodily harm", "physical harm", "physical damage"]),
    VairType("PsychologicalHarm", "Psychological Harm", "wellbeing_impact",
             ["psychological harm", "mental harm", "emotional harm", "psychological damage",
              "trauma", "distress", "anxiety"]),
    VairType("DistortionInHumanBehaviour", "Distortion in Human Behaviour", "wellbeing_impact",
             ["distortion in human", "behavioral change", "behaviour change",
              "altered behavior", "dependency"]),
]

# --- Impacted Area types ---

IMPACTED_AREAS: list[VairType] = [
    VairType("Freedom", "Freedom", "impacted_area",
             ["freedom", "liberty", "autonomy", "free expression", "free speech"]),
    VairType("Health", "Health", "impacted_area",
             ["health", "wellbeing", "well-being", "medical", "clinical"]),
    VairType("Principle", "Principle", "impacted_area",
             ["ethical principle", "moral", "fairness principle", "transparency principle"]),
    VairType("Right", "Right", "impacted_area",
             ["right", "human right", "fundamental right", "civil right", "privacy right"]),
    VairType("Safety", "Safety", "impacted_area",
             ["safety", "safe", "hazard", "dangerous", "critical infrastructure"]),
]


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
        ["accura", "inaccura"],
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
        ["fair", "equitab", "non-discriminat"],
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
        ["reliab", "dependab"],
    ),
    TrustworthyCharacteristic(
        "resilience", "implicit", "Art.15(4)",
        [],
        ["resilien", "recovery", "fault-tolerant", "fault tolerant"],
    ),
]


def match_trustworthy_characteristics(
    text: str,
    vair_matches: dict[str, list[VairType]],
) -> list[str]:
    """Return sorted characteristic names matched by VAIR type IDs or keyword fallback."""
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


def _match_types(text: str, types: list[VairType]) -> list[VairType]:
    lower = text.lower()
    return [t for t in types if any(kw in lower for kw in t.keywords)]


def match_risk_sources(text: str) -> list[VairType]:
    return _match_types(text, RISK_SOURCES)


def match_consequences(text: str) -> list[VairType]:
    return _match_types(text, CONSEQUENCES)


def match_impacts(text: str) -> list[VairType]:
    return _match_types(text, IMPACTS)


def match_impacted_areas(text: str) -> list[VairType]:
    return _match_types(text, IMPACTED_AREAS)


def match_all(text: str) -> dict[str, list[VairType]]:
    return {
        "risk_sources": match_risk_sources(text),
        "consequences": match_consequences(text),
        "impacts": match_impacts(text),
        "impacted_areas": match_impacted_areas(text),
    }
