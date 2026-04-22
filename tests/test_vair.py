from risk_landscaper.vair import (
    match_risk_sources,
    match_consequences,
    match_impacts,
    match_impacted_areas,
    match_all,
    match_trustworthy_characteristics,
)


def test_match_risk_sources_attack():
    matches = match_risk_sources("adversarial inputs designed to evade the model")
    ids = {m.id for m in matches}
    assert "AdversarialAttack" in ids
    assert "ModelEvasion" in ids
    assert all(m.parent == "attack" for m in matches)


def test_match_risk_sources_data():
    matches = match_risk_sources("biased training data leading to skewed outputs")
    ids = {m.id for m in matches}
    assert "BiasedTrainingData" in ids


def test_match_risk_sources_organisational():
    matches = match_risk_sources("lack of transparency in the AI system's decision making")
    ids = {m.id for m in matches}
    assert "LackOfTransparency" in ids
    assert matches[0].parent == "organisational"


def test_match_risk_sources_performance():
    matches = match_risk_sources("low accuracy in predictions for edge cases")
    ids = {m.id for m in matches}
    assert "LowAccuracy" in ids
    assert matches[0].parent == "performance"


def test_match_risk_sources_empty():
    assert match_risk_sources("completely unrelated text about cooking") == []


def test_match_consequences_bias():
    matches = match_consequences("the model produces biased and discriminatory outputs")
    ids = {m.id for m in matches}
    assert "Bias" in ids


def test_match_consequences_hallucination():
    matches = match_consequences("model hallucination leads to degraded accuracy")
    ids = {m.id for m in matches}
    assert "DegradedAccuracy" in ids


def test_match_consequences_manipulation():
    matches = match_consequences("subliminal manipulation of user behaviour")
    ids = {m.id for m in matches}
    assert "MaterialDistortionOfBehaviour" in ids


def test_match_consequences_impaired_decision():
    matches = match_consequences("misinformation leading to poor decision making")
    ids = {m.id for m in matches}
    assert "ImpairedDecisionMaking" in ids


def test_match_consequences_empty():
    assert match_consequences("the weather is nice today") == []


def test_match_impacts_discrimination():
    matches = match_impacts("discriminatory treatment of minority groups")
    ids = {m.id for m in matches}
    assert "DiscriminatoryTreatment" in ids


def test_match_impacts_overreliance():
    matches = match_impacts("users develop overreliance on automated decisions")
    ids = {m.id for m in matches}
    assert "Overreliance" in ids


def test_match_impacts_wellbeing():
    matches = match_impacts("psychological harm and emotional distress from AI interactions")
    ids = {m.id for m in matches}
    assert "PsychologicalHarm" in ids


def test_match_impacts_death():
    matches = match_impacts("fatal errors in autonomous driving decisions")
    ids = {m.id for m in matches}
    assert "Death" in ids


def test_match_impacts_empty():
    assert match_impacts("routine data processing pipeline") == []


def test_match_impacted_areas_safety():
    matches = match_impacted_areas("safety-critical applications in healthcare")
    ids = {m.id for m in matches}
    assert "Safety" in ids
    assert "Health" in ids


def test_match_impacted_areas_rights():
    matches = match_impacted_areas("impacts on fundamental rights and freedom of expression")
    ids = {m.id for m in matches}
    assert "Right" in ids
    assert "Freedom" in ids


def test_match_impacted_areas_empty():
    assert match_impacted_areas("abstract mathematical concept") == []


def test_match_all_combines():
    text = "biased training data causes discriminatory harm to health"
    result = match_all(text)
    assert len(result["risk_sources"]) > 0
    assert len(result["impacts"]) > 0
    assert len(result["impacted_areas"]) > 0


def test_match_all_empty():
    result = match_all("")
    assert all(len(v) == 0 for v in result.values())


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


def test_trustworthy_privacy_from_keywords():
    vair = match_all("personal data exposure and privacy breach")
    chars = match_trustworthy_characteristics("personal data exposure and privacy breach", vair)
    assert "privacy" in chars


def test_trustworthy_reliability_from_keywords():
    vair = match_all("system produces inconsistent and unreliable results")
    chars = match_trustworthy_characteristics("system produces inconsistent and unreliable results", vair)
    assert "reliability" in chars


def test_trustworthy_resilience_from_keywords():
    vair = match_all("system lacks failure recovery and resilience")
    chars = match_trustworthy_characteristics("system lacks failure recovery and resilience", vair)
    assert "resilience" in chars


def test_trustworthy_transparency_from_keywords():
    vair = match_all("opaque model with no explainability")
    chars = match_trustworthy_characteristics("opaque model with no explainability", vair)
    assert "transparency" in chars


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
