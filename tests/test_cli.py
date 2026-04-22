import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from risk_landscaper.cli import app, _load_input, _MARKITDOWN_EXTENSIONS


runner = CliRunner()


def test_run_missing_file():
    result = runner.invoke(app, ["run", "/nonexistent/policy.json", "--output", "/tmp/out", "--base-url", "http://localhost:8000/v1", "--model", "test"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_run_missing_base_url(tmp_path):
    policy_file = tmp_path / "test.json"
    policy_file.write_text(json.dumps([{"policy_concept": "Test", "concept_definition": "Def"}]))
    result = runner.invoke(app, ["run", str(policy_file), "--output", str(tmp_path / "out"), "--model", "test"])
    assert result.exit_code != 0
    assert "base-url" in result.output.lower() or "required" in result.output.lower()


def test_run_missing_model(tmp_path):
    policy_file = tmp_path / "test.json"
    policy_file.write_text(json.dumps([{"policy_concept": "Test", "concept_definition": "Def"}]))
    result = runner.invoke(app, ["run", str(policy_file), "--output", str(tmp_path / "out"), "--base-url", "http://localhost:8000/v1"])
    assert result.exit_code != 0
    assert "model" in result.output.lower() or "required" in result.output.lower()


def test_schema_stdout():
    result = runner.invoke(app, ["schema"])
    assert result.exit_code == 0
    assert "PolicyProfile" in result.output
    assert "RiskLandscape" in result.output


def test_schema_to_directory(tmp_path):
    result = runner.invoke(app, ["schema", "--output", str(tmp_path)])
    assert result.exit_code == 0
    profile_schema = tmp_path / "policy-profile.schema.json"
    landscape_schema = tmp_path / "risk-landscape.schema.json"
    assert profile_schema.exists()
    assert landscape_schema.exists()
    data = json.loads(profile_schema.read_text())
    assert data["title"] == "PolicyProfile"
    data = json.loads(landscape_schema.read_text())
    assert data["title"] == "RiskLandscape"


# ---------------------------------------------------------------------------
# Document conversion (_load_input with markitdown)
# ---------------------------------------------------------------------------

def test_markitdown_extensions_cover_expected():
    assert ".pdf" in _MARKITDOWN_EXTENSIONS
    assert ".docx" in _MARKITDOWN_EXTENSIONS
    assert ".html" in _MARKITDOWN_EXTENSIONS
    assert ".htm" in _MARKITDOWN_EXTENSIONS
    assert ".pptx" in _MARKITDOWN_EXTENSIONS
    assert ".xlsx" in _MARKITDOWN_EXTENSIONS


def test_load_input_pdf_converts_via_markitdown(tmp_path):
    pdf_file = tmp_path / "policy.pdf"
    pdf_file.write_bytes(b"fake pdf content")

    mock_result = MagicMock()
    mock_result.text_content = "# Converted Policy\n\nSome policy text."

    with patch("risk_landscaper.cli._convert_document", return_value=mock_result.text_content) as mock_convert:
        text, fmt, profile = _load_input(pdf_file)
        mock_convert.assert_called_once_with(pdf_file)
        assert fmt == "markdown"
        assert profile is None
        assert text == "# Converted Policy\n\nSome policy text."


def test_load_input_docx_converts_via_markitdown(tmp_path):
    docx_file = tmp_path / "policy.docx"
    docx_file.write_bytes(b"fake docx content")

    with patch("risk_landscaper.cli._convert_document", return_value="Policy content from docx"):
        text, fmt, profile = _load_input(docx_file)
        assert fmt == "markdown"
        assert text == "Policy content from docx"


def test_load_input_html_converts_via_markitdown(tmp_path):
    html_file = tmp_path / "policy.html"
    html_file.write_text("<html><body><h1>Policy</h1></body></html>")

    with patch("risk_landscaper.cli._convert_document", return_value="# Policy"):
        text, fmt, profile = _load_input(html_file)
        assert fmt == "markdown"
        assert text == "# Policy"


def test_load_input_json_not_converted(tmp_path):
    json_file = tmp_path / "policy.json"
    json_file.write_text(json.dumps([{"policy_concept": "P1", "concept_definition": "D1"}]))

    with patch("risk_landscaper.cli._convert_document") as mock_convert:
        text, fmt, profile = _load_input(json_file)
        mock_convert.assert_not_called()
        assert fmt == "json_array"


def test_load_input_markdown_not_converted(tmp_path):
    md_file = tmp_path / "policy.md"
    md_file.write_text("# My Policy\n\nContent here.")

    with patch("risk_landscaper.cli._convert_document") as mock_convert:
        text, fmt, profile = _load_input(md_file)
        mock_convert.assert_not_called()
        assert fmt == "markdown"
        assert text == "# My Policy\n\nContent here."


# ---------------------------------------------------------------------------
# Export subcommand
# ---------------------------------------------------------------------------

def test_export_jsonld(tmp_path):
    import yaml
    from risk_landscaper.models import RiskLandscape, RiskCard
    landscape = RiskLandscape(
        run_slug="test-run",
        risks=[RiskCard(risk_id="test-risk", risk_name="Test Risk")],
    )
    yaml_file = tmp_path / "risk-landscape.yaml"
    yaml_file.write_text(yaml.dump(landscape.model_dump(), default_flow_style=False))

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["export", str(yaml_file), "--format", "jsonld", "--output", str(out_dir)])
    assert result.exit_code == 0
    jsonld_path = out_dir / "risk-landscape.jsonld"
    assert jsonld_path.exists()
    data = json.loads(jsonld_path.read_text())
    assert "@context" in data
    assert data["rl:hasRiskCard"][0]["@id"] == "nexus:test-risk"


def test_export_default_format(tmp_path):
    import yaml
    from risk_landscaper.models import RiskLandscape
    landscape = RiskLandscape(run_slug="test-run")
    yaml_file = tmp_path / "risk-landscape.yaml"
    yaml_file.write_text(yaml.dump(landscape.model_dump(), default_flow_style=False))

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["export", str(yaml_file), "--output", str(out_dir)])
    assert result.exit_code == 0
    assert (out_dir / "risk-landscape.jsonld").exists()


def test_export_missing_file():
    result = runner.invoke(app, ["export", "/nonexistent/file.yaml", "--output", "/tmp/out"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


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


def test_run_format_jsonld_flag(tmp_path):
    """Verify --format jsonld is accepted as a valid CLI option."""
    result = runner.invoke(app, [
        "run", "/nonexistent/policy.json",
        "--output", str(tmp_path / "out"),
        "--base-url", "http://localhost:8000/v1",
        "--model", "test",
        "--nexus-base-dir", "/tmp/nexus",
        "--format", "jsonld",
    ])
    # Will fail because policy file doesn't exist, but --format should be accepted
    assert "no such option" not in result.output.lower()
    assert "does not exist" in result.output


# ---------------------------------------------------------------------------
# Compare subcommand
# ---------------------------------------------------------------------------

import yaml
from risk_landscaper.models import RiskLandscape, RiskCard, PolicyProfile, Organization, Policy


def _write_run_dir(tmp_path, name, landscape, profile):
    """Create a run output directory with landscape YAML and profile JSON."""
    run_dir = tmp_path / name
    run_dir.mkdir()
    (run_dir / "risk-landscape.yaml").write_text(
        yaml.dump(landscape.model_dump(), default_flow_style=False, sort_keys=False)
    )
    (run_dir / "policy-profile.json").write_text(
        json.dumps(profile.model_dump(), indent=2)
    )
    return run_dir


def test_compare_two_runs(tmp_path):
    la = RiskLandscape(
        run_slug="a", timestamp="2026-01-01",
        risks=[RiskCard(risk_id="r1", risk_name="R1", risk_level="high")],
        framework_coverage={"NIST": 1},
    )
    pa = PolicyProfile(
        organization=Organization(name="Alpha"),
        policies=[Policy(policy_concept="P1", concept_definition="D1")],
    )
    lb = RiskLandscape(
        run_slug="b", timestamp="2026-01-02",
        risks=[
            RiskCard(risk_id="r1", risk_name="R1", risk_level="low"),
            RiskCard(risk_id="r2", risk_name="R2"),
        ],
        framework_coverage={"NIST": 1, "IBM": 1},
    )
    pb = PolicyProfile(
        organization=Organization(name="Beta"),
        policies=[
            Policy(policy_concept="P1", concept_definition="D1"),
            Policy(policy_concept="P2", concept_definition="D2"),
        ],
    )

    dir_a = _write_run_dir(tmp_path, "run-a", la, pa)
    dir_b = _write_run_dir(tmp_path, "run-b", lb, pb)
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["compare", str(dir_a), str(dir_b), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output

    assert (out_dir / "comparison.yaml").exists()
    assert (out_dir / "comparison-report.html").exists()

    data = yaml.safe_load((out_dir / "comparison.yaml").read_text())
    assert len(data["landscapes"]) == 2
    assert len(data["shared_risks"]) == 1
    assert data["shared_risks"][0]["risk_id"] == "r1"


def test_compare_missing_directory(tmp_path):
    la = RiskLandscape(run_slug="a", risks=[])
    pa = PolicyProfile(policies=[])
    dir_a = _write_run_dir(tmp_path, "run-a", la, pa)

    result = runner.invoke(app, ["compare", str(dir_a), "/nonexistent/dir", "-o", "/tmp/out"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_compare_single_directory_rejected(tmp_path):
    la = RiskLandscape(run_slug="a", risks=[])
    pa = PolicyProfile(policies=[])
    dir_a = _write_run_dir(tmp_path, "run-a", la, pa)
    out_dir = tmp_path / "out"

    result = runner.invoke(app, ["compare", str(dir_a), "-o", str(out_dir)])
    assert result.exit_code != 0
    assert "at least 2" in result.output.lower() or "two" in result.output.lower()


def test_compare_missing_landscape_yaml(tmp_path):
    run_dir = tmp_path / "bad-run"
    run_dir.mkdir()
    (run_dir / "policy-profile.json").write_text("{}")

    la = RiskLandscape(run_slug="d", risks=[])
    pa = PolicyProfile(policies=[])
    _write_run_dir(tmp_path, "good-run", la, pa)

    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["compare", str(run_dir), str(tmp_path / "good-run"), "-o", str(out_dir)])
    assert result.exit_code != 0
    assert "risk-landscape.yaml" in result.output
