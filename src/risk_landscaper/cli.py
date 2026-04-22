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
    policy_file: Path = typer.Argument(..., help="Policy document (.md/.txt/.json/.pdf/.docx/.html)"),
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
):
    """Run the risk landscaper pipeline: ingest -> detect_domain -> map_risks -> build_landscape -> enrich_chains."""
    if not policy_file.exists():
        typer.echo(f"Error: {policy_file} does not exist", err=True)
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

    report = RunReport(
        model=config.model,
        policy_set=policy_file.name,
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
    text, detected_format, pre_parsed = _load_input(policy_file)
    fmt = input_format or detected_format

    t_stage = time.monotonic()
    if pre_parsed is not None:
        profile = pre_parsed
        typer.echo(f"Loaded pre-parsed profile: {len(profile.policies)} policies")
        _stage_event("ingest", "stage_completed", t_stage, skipped=True)
        report.stages_completed.append("ingest")
    else:
        from risk_landscaper.stages.ingest import ingest
        typer.echo(f"Ingesting {policy_file.name} (format: {fmt})...")
        profile = ingest(
            text, fmt, client, config,
            skip_enrichment=skip_enrichment,
            skip_entity_enrichment=skip_entity_enrichment,
            report=report,
        )
        _stage_event("ingest", "stage_completed", t_stage)
        report.stages_completed.append("ingest")
        typer.echo(f"  Organization: {profile.organization.name if profile.organization else ''}")
        typer.echo(f"  Domain: {profile.domain}")
        typer.echo(f"  Policies: {len(profile.policies)}")

    profile_path = output / "policy-profile.json"
    profile_path.write_text(json.dumps(profile.model_dump(), indent=2))

    from risk_landscaper.reports import build_ingest_report
    meta = {
        "model": config.model,
        "policy_set": policy_file.name,
        "timestamp": report.timestamp,
        "source_document": policy_file.name,
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
        run_slug=policy_file.stem,
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

    from risk_landscaper.reports import build_risk_landscape_report, build_ai_card_report
    build_risk_landscape_report(landscape.model_dump(), output / "risk-landscape.html")
    typer.echo(f"Risk landscape report written to {output / 'risk-landscape.html'}")

    build_ai_card_report(profile, landscape, output / "ai-card.html")
    typer.echo(f"AI Card written to {output / 'ai-card.html'}")

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
