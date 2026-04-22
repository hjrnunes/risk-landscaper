"""Nexus knowledge graph integration — risk index and query handlers.

Vendored from nexus-mcp (taxonomy-refiner/nexus-mcp). Provides semantic
search over AI Atlas Nexus risks via ChromaDB and handler functions for
risk details, cross-mappings, and related actions.
"""

from collections import defaultdict
from pathlib import Path
from typing import Any

import chromadb

COLLECTION_NAME = "risk_entries"
SCHEMA_VERSION = 2


def build_structural_context(
    risks_by_id: dict[str, Any],
    groups: list,
    actions_by_id: dict[str, Any] | None = None,
    *,
    max_siblings: int = 8,
) -> dict[str, str]:
    group_names: dict[str, str] = {}
    for g in groups:
        g_type = getattr(g, "type", "")
        if g_type == "RiskGroup" or hasattr(g, "isDefinedByTaxonomy"):
            group_names[g.id] = g.name

    group_members: dict[str, list] = defaultdict(list)
    for risk in risks_by_id.values():
        group_id = getattr(risk, "isPartOf", "")
        if group_id:
            group_members[group_id].append(risk)

    result: dict[str, str] = {}
    for risk_id, risk in risks_by_id.items():
        parts: list[str] = []

        group_id = getattr(risk, "isPartOf", "")
        if group_id and group_id in group_names:
            parts.append(f"PartOf: {group_names[group_id]}")
            siblings = [r.name for r in group_members[group_id] if r.id != risk_id and r.name is not None]
            if siblings:
                siblings.sort()
                if len(siblings) <= max_siblings:
                    parts.append(f"Siblings: {', '.join(siblings)}")
                else:
                    shown = siblings[:max_siblings]
                    parts.append(
                        f"Siblings: {', '.join(shown)} (+{len(siblings) - max_siblings} more)"
                    )

        mapping_attrs = [
            ("exact_mappings", "Exact"),
            ("close_mappings", "Close"),
            ("broad_mappings", "Broad"),
            ("narrow_mappings", "Narrow"),
            ("related_mappings", "Related"),
        ]
        for attr, label in mapping_attrs:
            target_ids = getattr(risk, attr, [])
            if not target_ids:
                continue
            names = []
            for tid in target_ids:
                target = risks_by_id.get(tid)
                if target:
                    names.append(target.name)
            if names:
                parts.append(f"{label}: {', '.join(names)}")

        if actions_by_id:
            action_ids = getattr(risk, "hasRelatedAction", [])
            action_names = []
            for aid in action_ids:
                action = actions_by_id.get(aid)
                if action:
                    action_names.append(action.name)
            if action_names:
                parts.append(f"Actions: {', '.join(action_names)}")

        if parts:
            result[risk_id] = ". ".join(parts)

    return result


class RiskIndex:
    def __init__(self, chroma_dir: Path):
        self._chroma_dir = Path(chroma_dir)
        self._client = chromadb.PersistentClient(path=str(self._chroma_dir))

    def index_risks(self, risks: list, structural_context: dict[str, str] | None = None) -> None:
        try:
            self._client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

        collection = self._client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "schema_version": SCHEMA_VERSION},
        )

        if not risks:
            return

        ids = []
        documents = []
        metadatas = []
        for risk in risks:
            doc_parts = [f"{risk.name}: {risk.description}"]
            if risk.concern:
                doc_parts.append(f"Concern: {risk.concern}")
            doc = ". ".join(doc_parts)
            if structural_context and risk.id in structural_context:
                doc = f"{doc}. {structural_context[risk.id]}"

            ids.append(risk.id)
            documents.append(doc)
            metadatas.append({
                "id": risk.id,
                "name": risk.name,
                "description": risk.description or "",
                "concern": risk.concern or "",
                "taxonomy": risk.isDefinedByTaxonomy or "",
                "risk_type": risk.risk_type or "",
                "group": risk.isPartOf or "",
            })

        batch_size = 5000
        for i in range(0, len(ids), batch_size):
            collection.upsert(
                ids=ids[i:i + batch_size],
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )

    def count(self) -> int:
        collection = self._client.get_collection(name=COLLECTION_NAME)
        return collection.count()

    def needs_reindex(self, expected_count: int) -> bool:
        try:
            collection = self._client.get_collection(name=COLLECTION_NAME)
            if collection.count() != expected_count:
                return True
            version = collection.metadata.get("schema_version", 1)
            return version != SCHEMA_VERSION
        except Exception:
            return True

    def search(self, query: str, top_k: int = 10, taxonomy: str | None = None) -> list[dict]:
        try:
            collection = self._client.get_collection(name=COLLECTION_NAME)
        except Exception:
            raise ValueError("No risk index found. Index risks before searching.")

        kwargs = {"query_texts": [query], "n_results": top_k}
        if taxonomy:
            kwargs["where"] = {"taxonomy": taxonomy}

        results = collection.query(**kwargs)

        output = []
        for i in range(len(results["ids"][0])):
            meta = results["metadatas"][0][i]
            output.append({
                "id": meta.get("id", results["ids"][0][i]),
                "name": meta.get("name", meta.get("id", "")),
                "description": meta.get("description") or None,
                "concern": meta.get("concern") or None,
                "taxonomy": meta.get("taxonomy", ""),
                "distance": results["distances"][0][i],
            })
        return output


def create_tool_handlers(
        risk_index: RiskIndex,
        risks_by_id: dict,
        actions_by_id: dict,
        taxonomies: list,
        groups: list,
) -> dict:
    risks_by_tag = {}
    for risk in risks_by_id.values():
        if hasattr(risk, "tag") and risk.tag:
            risks_by_tag[risk.tag] = risk

    def search_risks(query: str, top_k: int = 10) -> list[dict]:
        return risk_index.search(query, top_k=top_k)

    def get_risk_details(risk_id: str) -> dict | None:
        risk = risks_by_id.get(risk_id) or risks_by_tag.get(risk_id)
        if risk is None:
            return None
        return {
            "id": risk.id,
            "name": risk.name,
            "description": risk.description,
            "concern": risk.concern,
            "risk_type": getattr(risk, "risk_type", None),
            "descriptor": getattr(risk, "descriptor", []),
            "taxonomy": getattr(risk, "isDefinedByTaxonomy", ""),
            "group": getattr(risk, "isPartOf", ""),
        }

    def get_related_risks(risk_id: str) -> list[dict]:
        risk = risks_by_id.get(risk_id) or risks_by_tag.get(risk_id)
        if risk is None:
            return []

        results = []
        mapping_attrs = [
            ("exact_mappings", "exact"),
            ("close_mappings", "close"),
            ("broad_mappings", "broad"),
            ("narrow_mappings", "narrow"),
            ("related_mappings", "related"),
        ]
        for attr, mapping_type in mapping_attrs:
            for ref_id in getattr(risk, attr, []):
                ref_risk = risks_by_id.get(ref_id)
                if ref_risk is None:
                    continue
                results.append({
                    "id": ref_risk.id,
                    "name": ref_risk.name,
                    "description": ref_risk.description,
                    "taxonomy": getattr(ref_risk, "isDefinedByTaxonomy", ""),
                    "mapping_type": mapping_type,
                })
        return results

    def get_related_actions(risk_id: str) -> list[dict]:
        risk = risks_by_id.get(risk_id) or risks_by_tag.get(risk_id)
        if risk is None:
            return []

        results = []
        for action_id in getattr(risk, "hasRelatedAction", []):
            action = actions_by_id.get(action_id)
            if action is None:
                continue
            results.append({
                "id": action.id,
                "name": action.name,
                "description": action.description,
            })
        return results

    def _is_risk_taxonomy(t) -> bool:
        if getattr(t, "type", "") == "RiskTaxonomy":
            return True
        try:
            from ai_atlas_nexus.ai_risk_ontology.datamodel.ai_risk_ontology import RiskTaxonomy
            return isinstance(t, RiskTaxonomy)
        except ImportError:
            return False

    def _is_risk_group(g) -> bool:
        if getattr(g, "type", "") == "RiskGroup":
            return True
        try:
            from ai_atlas_nexus.ai_risk_ontology.datamodel.ai_risk_ontology import RiskGroup
            return isinstance(g, RiskGroup)
        except ImportError:
            return False

    def list_taxonomies() -> list[dict]:
        results = []
        for t in taxonomies:
            if not _is_risk_taxonomy(t):
                continue
            risk_count = sum(
                1 for r in risks_by_id.values()
                if getattr(r, "isDefinedByTaxonomy", "") == t.id
            )
            results.append({
                "id": t.id,
                "name": t.name,
                "description": getattr(t, "description", ""),
                "risk_count": risk_count,
            })
        return results

    def list_risk_groups(taxonomy: str | None = None) -> list[dict]:
        results = []
        for g in groups:
            if not _is_risk_group(g):
                continue
            g_taxonomy = getattr(g, "isDefinedByTaxonomy", "")
            if taxonomy and g_taxonomy != taxonomy:
                continue
            risk_count = sum(
                1 for r in risks_by_id.values()
                if getattr(r, "isPartOf", "") == g.id
            )
            results.append({
                "id": g.id,
                "name": g.name,
                "taxonomy": g_taxonomy,
                "risk_count": risk_count,
            })
        return results

    def get_risk_group(risk_id: str) -> dict | None:
        risk = risks_by_id.get(risk_id) or risks_by_tag.get(risk_id)
        if risk is None:
            return None
        group_id = getattr(risk, "isPartOf", "")
        if not group_id:
            return None
        for g in groups:
            if not _is_risk_group(g):
                continue
            if g.id == group_id:
                return {
                    "id": g.id,
                    "name": g.name,
                    "taxonomy": getattr(g, "isDefinedByTaxonomy", ""),
                }
        return None

    def explore_risk(risk_id: str) -> dict | None:
        details = get_risk_details(risk_id)
        if details is None:
            return None
        details["related_risks"] = get_related_risks(risk_id)
        details["related_actions"] = get_related_actions(risk_id)
        return details

    def gap_analysis(
            risk_descriptions: list[str],
            target_taxonomy: str = "ibm-risk-atlas",
            distance_threshold: float = 0.5,
    ) -> dict:
        target_risks = {
            r.id: r for r in risks_by_id.values()
            if getattr(r, "isDefinedByTaxonomy", "") == target_taxonomy
        }

        covered = {}
        for desc in risk_descriptions:
            matches = risk_index.search(desc, top_k=5, taxonomy=target_taxonomy)
            for match in matches:
                if match["distance"] <= distance_threshold:
                    rid = match["id"]
                    if rid not in covered or match["distance"] < covered[rid]["distance"]:
                        covered[rid] = {
                            "target_risk": {"id": rid, "name": match["name"]},
                            "matched_description": desc,
                            "distance": match["distance"],
                        }

        gap_risks = []
        for rid, risk in target_risks.items():
            if rid not in covered:
                gap_risks.append({"id": rid, "name": risk.name})

        total = len(target_risks)
        coverage_pct = (len(covered) / total * 100) if total > 0 else 0.0

        return {
            "covered": list(covered.values()),
            "gaps": gap_risks,
            "coverage_pct": round(coverage_pct, 1),
        }

    return {
        "search_risks": search_risks,
        "get_risk_details": get_risk_details,
        "get_related_risks": get_related_risks,
        "get_related_actions": get_related_actions,
        "list_taxonomies": list_taxonomies,
        "list_risk_groups": list_risk_groups,
        "get_risk_group": get_risk_group,
        "explore_risk": explore_risk,
        "gap_analysis": gap_analysis,
    }
