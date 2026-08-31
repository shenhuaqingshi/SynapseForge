"""
Document-specific CLI command handlers for agents and automated tools.
Provides programmatic getters, setters, stats, and exports in structured JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from synapseforge.config import load_config
from synapseforge.core.ast_parser import MarkdownASTParser
from synapseforge.core.state import StateManager
from synapseforge.renderers.pipeline import PublicationPipeline


def handle_doc_get(args):
    """Retrieves section content, metadata, and parsed AST blocks in JSON."""
    config = load_config()
    target_file = None
    target_sec = None

    for s in config.sections:
        if s.id == args.section or s.file.endswith(args.section) or s.file == args.section:
            target_file = Path.cwd() / s.file
            target_sec = s
            break

    if not target_file or not target_file.exists():
        # Fallback to direct path search
        direct = Path.cwd() / "sections" / f"{args.section}.md"
        if direct.exists():
            target_file = direct

    if not target_file or not target_file.exists():
        res = {"ok": False, "error": f"Section '{args.section}' not found"}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"✖ Section '{args.section}' not found")
        sys.exit(1)

    content = target_file.read_text(encoding="utf-8")
    parser = MarkdownASTParser()
    blocks = parser.parse_blocks(content)
    citations = parser.extract_citations(content)

    res = {
        "ok": True,
        "section_id": target_sec.id if target_sec else args.section,
        "title": target_sec.title if target_sec else "",
        "file": str(target_file.relative_to(Path.cwd())),
        "word_count": parser.count_words(content),
        "content": content,
        "ast_blocks": [
            {
                "type": b.type.value,
                "line_start": b.line_start,
                "line_end": b.line_end,
                "content": b.content,
            }
            for b in blocks
        ],
        "citations": parser.extract_citations(content),
    }

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"\nSection: {res['section_id']} ({res['word_count']} words, {len(blocks)} blocks)")
        print("-" * 60)
        print(content)
        print("-" * 60)


def handle_doc_stats(args):
    """Computes comprehensive multi-dimensional document statistics for agents."""
    config = load_config()
    parser = MarkdownASTParser()

    total_words = 0
    total_blocks = 0
    total_citations = set()
    total_tables = 0
    total_math_blocks = 0
    section_stats = []

    sec_dir = Path.cwd() / "sections"
    files = list(sec_dir.glob("*.md")) if sec_dir.exists() else []

    for f in sorted(files):
        content = f.read_text(encoding="utf-8")
        words = parser.count_words(content)
        blocks = parser.parse_blocks(content)
        citations = parser.extract_citations(content)
        
        tables_count = sum(1 for b in blocks if b.type.value == "table")
        math_count = sum(1 for b in blocks if b.type.value == "math_block")

        total_words += words
        total_blocks += len(blocks)
        total_tables += tables_count
        total_math_blocks += math_count
        for c in citations:
            total_citations.add(c)

        section_stats.append({
            "file": f.name,
            "word_count": words,
            "block_count": len(blocks),
            "table_count": tables_count,
            "math_count": math_count,
            "citations_count": len(citations),
        })

    res = {
        "ok": True,
        "project_name": config.name,
        "document_title": config.document_title,
        "total_words": total_words,
        "total_sections": len(files),
        "total_blocks": total_blocks,
        "total_tables": total_tables,
        "total_math_blocks": total_math_blocks,
        "unique_citations_count": len(total_citations),
        "unique_citations": sorted(list(total_citations)),
        "sections": section_stats,
    }

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"\nDocument Telemetry: '{config.document_title}'")
        print(f"  - Total Words: {total_words}")
        print(f"  - Sections: {len(files)} | AST Blocks: {total_blocks}")
        print(f"  - Tables (Booktabs): {total_tables} | Equations: {total_math_blocks}")
        print(f"  - Unique Citations: {len(total_citations)} ({', '.join(sorted(list(total_citations))[:5])}...)")
        print()
        for s in section_stats:
            print(f"  • {s['file']:<30} | {s['word_count']:>5} words | {s['table_count']} tables | {s['math_count']} equations")
        print()
