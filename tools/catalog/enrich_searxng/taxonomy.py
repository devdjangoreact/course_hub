"""Taxonomy load / prompt block / merge for enrich."""

from __future__ import annotations

import json
from typing import Any

import config

TAXONOMY_PATH = config.CATALOG_ROOT / "enrich_taxonomy.json"


def load_taxonomy() -> dict[str, Any]:
    if not TAXONOMY_PATH.is_file():
        return {"categories": [], "tags": []}
    return json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))


def taxonomy_prompt_block(taxonomy: dict[str, Any]) -> str:
    lines = []
    for item in taxonomy.get("categories") or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        subs = ", ".join(item.get("subcategories") or [])
        lines.append(f"- {item['name']}: [{subs}]")
    tags = ", ".join(str(t) for t in (taxonomy.get("tags") or []))
    return (
        "Allowed taxonomy — prefer exact names; invent short new ones only if nothing fits:\n"
        "Categories + subcategories:\n"
        + ("\n".join(lines) if lines else "(empty)")
        + f"\n\nTags:\n{tags or '(empty)'}"
    )


def merge_taxonomy(extracted: dict[str, Any]) -> None:
    """Append unknown category / subcategory / tags to enrich_taxonomy.json."""
    taxonomy = load_taxonomy()
    categories = list(taxonomy.get("categories") or [])
    tags = list(taxonomy.get("tags") or [])
    cat_by_name = {
        str(c["name"]).casefold(): c for c in categories if isinstance(c, dict) and c.get("name")
    }
    tag_keys = {str(t).casefold() for t in tags}
    changed = False

    def _add_tag(name: str) -> None:
        nonlocal changed
        key = name.casefold()
        if key not in tag_keys:
            tags.append(name)
            tag_keys.add(key)
            changed = True

    cat = extracted.get("category")
    sub = extracted.get("subcategory")
    if isinstance(cat, str) and cat.strip():
        cat_name = cat.strip()
        key = cat_name.casefold()
        if key not in cat_by_name:
            entry = {
                "name": cat_name,
                "subcategories": [sub.strip()] if isinstance(sub, str) and sub.strip() else [],
            }
            categories.append(entry)
            cat_by_name[key] = entry
            changed = True
        elif isinstance(sub, str) and sub.strip():
            entry = cat_by_name[key]
            subs = list(entry.get("subcategories") or [])
            if not any(str(s).casefold() == sub.strip().casefold() for s in subs):
                subs.append(sub.strip())
                entry["subcategories"] = subs
                changed = True
        _add_tag(cat_name)

    if isinstance(sub, str) and sub.strip():
        _add_tag(sub.strip())

    for t in extracted.get("tags") or []:
        if isinstance(t, str) and t.strip():
            _add_tag(t.strip())

    if not changed:
        return
    taxonomy["categories"] = categories
    taxonomy["tags"] = tags
    TAXONOMY_PATH.write_text(
        json.dumps(taxonomy, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  taxonomy updated -> {TAXONOMY_PATH.name}")
