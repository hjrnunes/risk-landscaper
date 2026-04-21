from risk_landscaper.vair import (
    match_risk_sources,
    match_consequences,
    match_impacts,
    match_impacted_areas,
    match_all,
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
