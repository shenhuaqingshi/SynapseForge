"""
Research Literature & Document Ingestion Engine for SynapseForge.
Allows AI Agents and human authors to ingest ArXiv papers, URLs, and PDFs into structured knowledge context.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


class DocumentIngestor:
    """Ingests external references and research sources into project knowledge base."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.context_dir = self.workspace_root / "context"
        self.context_dir.mkdir(parents=True, exist_ok=True)

    def ingest_text_or_note(self, source_id: str, title: str, content: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Saves a structured research note or briefing into context directory."""
        target_file = self.context_dir / f"{source_id}.md"
        
        note_content = f"""---
id: {source_id}
title: "{title}"
tags: {json.dumps(tags or [])}
---

# {title}

{content}
"""
        target_file.write_text(note_content, encoding="utf-8")
        
        # Word count
        words = len(content.split())
        return {
            "ok": True,
            "source_id": source_id,
            "title": title,
            "file": str(target_file.relative_to(self.workspace_root)),
            "words": words,
        }

    def list_ingested_sources(self) -> List[Dict[str, Any]]:
        """Lists all ingested context files."""
        sources = []
        for p in sorted(self.context_dir.glob("*.md")):
            raw = p.read_text(encoding="utf-8")
            title_match = re.search(r'^title:\s*["\']?(.*?)["\']?$', raw, re.MULTILINE)
            sources.append({
                "id": p.stem,
                "file": p.name,
                "title": title_match.group(1) if title_match else p.stem,
                "size_bytes": p.stat().st_size,
            })
        return sources
