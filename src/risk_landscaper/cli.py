import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml

from risk_landscaper import debug
from risk_landscaper.llm import LLMConfig, TokenTracker, create_client
from risk_landscaper.models import Policy, PolicyProfile, RunReport
from risk_landscaper.nexus_adapter import detect_nexus_format, nexus_to_policy_profile

app = typer.Typer()


@app.callback()
def main():
    """Risk landscaper — policy-driven risk landscape generation."""


_MARKITDOWN_EXTENSIONS = {".pdf", ".docx", ".html", ".htm", ".pptx", ".xlsx"}


def _convert_document(path: Path) -> str:
    try:
        from markitdown import MarkItDown
    except ImportError:
        raise typer.Exit(
            f"Cannot convert {path.suffix} files without markitdown. "
            f"Install it with: pip install 'risk-landscaper[docs]'"
        )
    converter = MarkItDown()
    result = converter.convert(str(path))
    return result.text_content


def _load_input(path: Path) -> tuple[str, str, PolicyProfile | None]:
    if path.suffix.lower() in _MARKITDOWN_EXTENSIONS:
        text = _convert_document(path)
        return text, "markdown", None
    text = path.read_text()
    if path.suffix == ".json":
        raw = json.loads(text)
        if isinstance(raw, list):
            return text, "json_array", None
        if detect_nexus_format(raw):
            profile = nexus_to_policy_profile(raw)
            return text, "policy_profile", profile
        if "policies" in raw:
            profile = PolicyProfile(**raw)
            return text, "policy_profile", profile
    return text, "markdown", None


def _create_risk_handlers(nexus_base_dir: str, nexus_chroma_dir: Path) -> dict:
    from risk_landscaper.nexus import RiskIndex, build_structural_context, create_tool_handlers
    from ai_atlas_nexus import AIAtlasNexus

    nexus = AIAtlasNexus(base_dir=nexus_base_dir)
    all_risks = nexus.get_all_risks()
    risks_by_id = {r.id: r for r in all_risks}
    all_actions = nexus.get_all_actions()
    actions_by_id = {a.id: a for a in all_actions}
    taxonomies = nexus.get_all_taxonomies()
    groups = nexus.get_all("groups")
    nexus_chroma_dir.mkdir(parents=True, exist_ok=True)

    idx = RiskIndex(nexus_chroma_dir)
    if idx.needs_reindex(len(all_risks)):
        ctx = build_structural_context(risks_by_id, groups, actions_by_id)
        idx.index_risks(all_risks, structural_context=ctx)
    return create_tool_handlers(
        risk_index=idx, risks_by_id=risks_by_id, actions_by_id=actions_by_id,
        taxonomies=taxonomies, groups=groups,
    )


@app.command()
def run(
    policy_files: list[Path] = typer.Argument(..., help="Policy document(s) (.md/.txt/.json/.pdf/.docx/.html)"),
    output: Path = typer.Option(..., "--output", "-o", help="Output directory"),
    base_url: str = typer.Option(None, "--base-url", envvar="REFINER_BASE_URL", help="LLM API base URL"),
    model: str = typer.Option(None, "--model", envvar="REFINER_MODEL", help="LLM model name"),
    api_key: str = typer.Option("none", "--api-key", envvar="REFINER_API_KEY", help="LLM API key"),
    nexus_base_dir: str = typer.Option(None, "--nexus-base-dir", envvar="NEXUS_BASE_DIR", help="Path to ai-atlas-nexus repo"),
    nexus_chroma_dir: Path = typer.Option(Path(".chroma"), "--nexus-chroma-dir", envvar="NEXUS_CHROMA_DIR", help="Nexus ChromaDB directory"),
    debug_dir: Path = typer.Option(None, "--debug", help="Directory for per-call debug logs"),
    skip_enrichment: bool = typer.Option(False, "--skip-enrichment", help="Skip ingest enrichment pass"),
    skip_entity_enrichment: bool = typer.Option(False, "--skip-entity-enrichment", help="Skip entity enrichment pass"),
    max_concurrent: int = typer.Option(1, "--max-concurrent", help="Max parallel LLM calls in map_risks"),
    input_format: str = typer.Option(None, "--input-format", help="Input format: markdown or json_array (auto-detected if omitted)"),
    skip_chain_enrichment: bool = typer.Option(False, "--skip-chain-enrichment", help="Skip LLM causal chain enrichment"),
    max_context: int = typer.Option(0, "--max-context", help="Model context window size in tokens (0 = no limit). When set, large documents are chunked to fit."),
    output_format: str = typer.Option("yaml", "--format", "-f", help="Additional output format: yaml (default), jsonld, turtle"),
):
    """Run the risk landscaper pipeline: ingest -> detect_domain -> map_risks -> build_landscape -> enrich_chains."""
    for pf in policy_files:
        if not pf.exists():
            typer.echo(f"Error: {pf} does not exist", err=True)
            raise typer.Exit(1)

    if not base_url or not model:
        typer.echo("Error: --base-url and --model are required (or set REFINER_BASE_URL / REFINER_MODEL)", err=True)
        raise typer.Exit(1)

    if not nexus_base_dir:
        typer.echo("Error: --nexus-base-dir is required (or set NEXUS_BASE_DIR)", err=True)
        raise typer.Exit(1)

    config = LLMConfig(base_url=base_url, model=model, api_key=api_key, max_concurrent=max_concurrent, max_context=max_context)
    tracker = TokenTracker()
    client = create_client(config, tracker=tracker)
    debug.configure(debug_dir)

    policy_set_name = ", ".join(pf.name for pf in policy_files)
    report = RunReport(
        model=config.model,
        policy_set=policy_set_name,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

    output.mkdir(parents=True, exist_ok=True)

    def _stage_event(name: str, event: str, started: float, **extra) -> None:
        report.events.append({
            "stage": name,
            "event": event,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
            **extra,
        })

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

    # --- Stage 2: Detect domain ---
    from risk_landscaper.stages.detect_domain import detect_domain
    t_stage = time.monotonic()
    selected_domains = detect_domain(profile, client, config, report=report)
    _stage_event("detect_domain", "stage_completed", t_stage)
    report.stages_completed.append("detect_domain")
    typer.echo(f"  Domain: {selected_domains}")

    # --- Stage 3: Map risks ---
    from risk_landscaper.stages.map_risks import map_risks
    risk_handlers = _create_risk_handlers(nexus_base_dir, nexus_chroma_dir)
    typer.echo(f"Mapping {len(profile.policies)} policies to risks...")
    t_stage = time.monotonic()
    mappings, risk_details, seen_ids, related_risks, risk_actions, coverage_gaps = map_risks(
        profile.policies, client, config, risk_handlers, report=report,
    )
    _stage_event("map_risks", "stage_completed", t_stage,
                 risk_count=sum(len(m.matched_risks) for m in mappings),
                 policy_count=len(mappings))
    report.stages_completed.append("map_risks")
    total_matches = sum(len(m.matched_risks) for m in mappings)
    typer.echo(f"  {total_matches} risk matches across {len(mappings)} policies")
    if coverage_gaps:
        typer.echo(f"  {len(coverage_gaps)} coverage gap(s) detected")

    # --- Fetch incidents for matched risks ---
    from ai_atlas_nexus import AIAtlasNexus
    nexus = AIAtlasNexus(base_dir=nexus_base_dir)
    t_stage = time.monotonic()
    risk_incidents: dict[str, list[dict]] = {}
    for rid in risk_details:
        incidents = nexus.get_related_risk_incidents(risk_id=rid)
        if incidents:
            risk_incidents[rid] = [
                {
                    "name": inc.name,
                    "description": inc.description,
                    "source_uri": getattr(inc, "source_uri", None),
                    "hasStatus": getattr(inc, "hasStatus", None),
                }
                for inc in incidents
            ]
    total_inc = sum(len(v) for v in risk_incidents.values())
    report.events.append({
        "stage": "build_landscape",
        "event": "incidents_fetched",
        "risks_with_incidents": len(risk_incidents),
        "total_incidents": total_inc,
        "duration_ms": round((time.monotonic() - t_stage) * 1000, 1),
    })
    if risk_incidents:
        typer.echo(f"  {total_inc} incident(s) linked to {len(risk_incidents)} risk(s)")

    # --- Stage 4: Build landscape ---
    from risk_landscaper.stages.build_landscape import build_risk_landscape

    t_stage = time.monotonic()
    landscape = build_risk_landscape(
        mappings=mappings,
        risk_details_cache=risk_details,
        related_risks=related_risks,
        risk_actions=risk_actions,
        risk_incidents=risk_incidents,
        selected_domains=selected_domains,
        model=config.model,
        run_slug=policy_files[0].stem,
        timestamp=report.timestamp,
        coverage_gaps=coverage_gaps,
        policy_profile=profile,
    )
    _stage_event("build_landscape", "stage_completed", t_stage,
                 risk_count=len(landscape.risks),
                 framework_count=len(landscape.framework_coverage))
    report.stages_completed.append("build_landscape")

    # --- Stage 5: Enrich causal chains ---
    if not skip_chain_enrichment:
        from risk_landscaper.stages.enrich_chains import enrich_chains
        primary_count = sum(
            1 for m in mappings for rm in m.matched_risks if rm.relevance == "primary"
        )
        typer.echo(f"Enriching causal chains for {primary_count} primary-relevance risks...")
        t_stage = time.monotonic()
        enrich_chains(landscape, profile.policies, client, config, report=report)
        _stage_event("enrich_chains", "stage_completed", t_stage,
                     primary_count=primary_count)
        report.stages_completed.append("enrich_chains")
        enriched = sum(1 for r in landscape.risks if r.consequences)
        typer.echo(f"  {enriched} risk(s) enriched with causal chains")
    else:
        typer.echo("Skipping causal chain enrichment (--skip-chain-enrichment)")

    # --- Stage 6: Assessment ---
    from risk_landscaper.stages.assess import assess_risk_levels, compute_aims_coverage
    t_stage = time.monotonic()
    assess_risk_levels(landscape, report=report)
    aims = compute_aims_coverage(profile, landscape, report=report)
    _stage_event("assess", "stage_completed", t_stage)
    report.stages_completed.append("assess")
    leveled = sum(1 for r in landscape.risks if r.risk_level)
    typer.echo(f"  {leveled}/{len(landscape.risks)} risks with computed risk level")
    typer.echo(f"  AIMS coverage: {', '.join(aims) if aims else 'none'}")

    landscape_path = output / "risk-landscape.yaml"
    landscape_path.write_text(yaml.dump(
        landscape.model_dump(), default_flow_style=False, sort_keys=False,
    ))
    typer.echo(f"Risk landscape written to {landscape_path}")
    typer.echo(f"  {len(landscape.risks)} unique risks, {len(landscape.framework_coverage)} frameworks")

    if output_format in ("jsonld", "turtle"):
        from risk_landscaper.serialize import landscape_to_jsonld
        doc = landscape_to_jsonld(landscape)
        jsonld_path = output / "risk-landscape.jsonld"
        jsonld_path.write_text(json.dumps(doc, indent=2))
        typer.echo(f"JSON-LD written to {jsonld_path}")
        if output_format == "turtle":
            from risk_landscaper.serialize import landscape_to_turtle
            ttl = landscape_to_turtle(landscape)
            ttl_path = output / "risk-landscape.ttl"
            ttl_path.write_text(ttl)
            typer.echo(f"Turtle written to {ttl_path}")

    from risk_landscaper.reports import build_risk_landscape_report, build_ai_card_report
    build_risk_landscape_report(landscape.model_dump(), output / "risk-landscape.html")
    typer.echo(f"Risk landscape report written to {output / 'risk-landscape.html'}")

    build_ai_card_report(profile, landscape, output / "ai-card.html")
    typer.echo(f"Risk Card written to {output / 'ai-card.html'}")

    # --- Write report ---
    report.token_usage = tracker.to_dict()
    report_path = output / "run-report.json"
    report_path.write_text(json.dumps(report.to_dict(), indent=2))

    from risk_landscaper.reports import build_run_report_html
    build_run_report_html(report.to_dict(), output / "run-report.html")
    typer.echo(f"Run report written to {output / 'run-report.html'}")

    typer.echo(f"Token usage: {tracker.prompt_tokens:,} prompt + {tracker.completion_tokens:,} completion = {tracker.total_tokens:,} total ({tracker.calls} calls)")
    typer.echo("Done.")


@app.command()
def schema(
    output: Path = typer.Option(None, "--output", "-o", help="Output directory (default: stdout)"),
):
    """Export JSON Schema for PolicyProfile and RiskLandscape output formats."""
    from risk_landscaper.models import PolicyProfile, RiskLandscape

    schemas = {
        "policy-profile": PolicyProfile.model_json_schema(),
        "risk-landscape": RiskLandscape.model_json_schema(),
    }

    if output:
        output.mkdir(parents=True, exist_ok=True)
        for name, s in schemas.items():
            path = output / f"{name}.schema.json"
            path.write_text(json.dumps(s, indent=2) + "\n")
            typer.echo(f"Written {path}")
    else:
        for name, s in schemas.items():
            typer.echo(f"--- {name} ---")
            typer.echo(json.dumps(s, indent=2))


@app.command()
def export(
    input_file: Path = typer.Argument(..., help="Risk landscape YAML file to convert"),
    output: Path = typer.Option(..., "--output", "-o", help="Output directory"),
    fmt: str = typer.Option("jsonld", "--format", "-f", help="Output format: jsonld or turtle"),
):
    """Export a risk landscape to JSON-LD or Turtle format."""
    if not input_file.exists():
        typer.echo(f"Error: {input_file} does not exist", err=True)
        raise typer.Exit(1)

    from risk_landscaper.models import RiskLandscape
    from risk_landscaper.serialize import landscape_to_jsonld

    raw = yaml.safe_load(input_file.read_text())
    landscape = RiskLandscape(**raw)

    output.mkdir(parents=True, exist_ok=True)

    if fmt == "turtle":
        from risk_landscaper.serialize import landscape_to_turtle
        ttl = landscape_to_turtle(landscape)
        out_path = output / "risk-landscape.ttl"
        out_path.write_text(ttl)
        typer.echo(f"Turtle written to {out_path}")
    else:
        doc = landscape_to_jsonld(landscape)
        out_path = output / "risk-landscape.jsonld"
        out_path.write_text(json.dumps(doc, indent=2))
        typer.echo(f"JSON-LD written to {out_path}")


@app.command()
def compare(
    run_dirs: list[Path] = typer.Argument(..., help="Run output directories to compare (each must contain risk-landscape.yaml and policy-profile.json)"),
    output: Path = typer.Option(..., "--output", "-o", help="Output directory for comparison report"),
):
    """Compare two or more risk landscape runs."""
    if len(run_dirs) < 2:
        typer.echo("Error: compare requires at least 2 run directories", err=True)
        raise typer.Exit(1)

    for d in run_dirs:
        if not d.exists():
            typer.echo(f"Error: {d} does not exist", err=True)
            raise typer.Exit(1)

    inputs = []
    for d in run_dirs:
        landscape_path = d / "risk-landscape.yaml"
        profile_path = d / "policy-profile.json"

        if not landscape_path.exists():
            typer.echo(f"Error: {landscape_path} not found", err=True)
            raise typer.Exit(1)
        if not profile_path.exists():
            typer.echo(f"Error: {profile_path} not found", err=True)
            raise typer.Exit(1)

        from risk_landscaper.models import RiskLandscape as RiskLandscapeModel
        landscape = RiskLandscapeModel(**yaml.safe_load(landscape_path.read_text()))
        profile = PolicyProfile(**json.loads(profile_path.read_text()))
        inputs.append((d.name, landscape, profile))

    from risk_landscaper.compare import build_comparison
    comparison = build_comparison(inputs)

    output.mkdir(parents=True, exist_ok=True)

    comparison_path = output / "comparison.yaml"
    comparison_path.write_text(yaml.dump(
        comparison.model_dump(), default_flow_style=False, sort_keys=False,
    ))
    typer.echo(f"Comparison written to {comparison_path}")

    from risk_landscaper.reports import build_comparison_report
    build_comparison_report(comparison.model_dump(), output / "comparison-report.html")
    typer.echo(f"Comparison report written to {output / 'comparison-report.html'}")

    typer.echo(f"Compared {len(inputs)} landscapes: {len(comparison.shared_risks)} shared risks, "
               + ", ".join(f"{len(v)} unique to {k}" for k, v in comparison.unique_risks.items()))
