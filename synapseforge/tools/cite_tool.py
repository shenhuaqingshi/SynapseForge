"""
Citation and BibTeX Management Tool for SynapseForge.
Enables AI Agents and human authors to search, validate, and append clean BibTeX references.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional


class CiteTool:
    """Manages BibTeX citations, DOI lookups, and citation graph references."""

    def __init__(self, bib_path: Optional[Path] = None):
        self.bib_file = bib_path or Path.cwd() / "bibliography.bib"

    def list_citations(self) -> List[Dict[str, str]]:
        """Parses all existing entries in bibliography.bib."""
        if not self.bib_file.exists():
            return []

        content = self.bib_file.read_text(encoding="utf-8")
        entries = []
        pattern = r'@([a-zA-Z]+)\s*\{\s*([a-zA-Z0-9_\-:]+)\s*,\s*([\s\S]*?)\n\}'
        for match in re.finditer(pattern, content):
            entry_type = match.group(1)
            cite_key = match.group(2)
            body = match.group(3)
            
            # Extract title if present
            title_match = re.search(r'title\s*=\s*[\{"](.*?)[\}"]', body, re.IGNORECASE)
            author_match = re.search(r'author\s*=\s*[\{"](.*?)[\}"]', body, re.IGNORECASE)
            year_match = re.search(r'year\s*=\s*[\{"]?(\d{4})[\}"]?', body, re.IGNORECASE)

            entries.append({
                "key": cite_key,
                "type": entry_type,
                "title": title_match.group(1) if title_match else "",
                "author": author_match.group(1) if author_match else "",
                "year": year_match.group(1) if year_match else "",
                "raw": match.group(0),
            })
        return entries

    def add_bibtex_entry(self, key: str, entry_type: str, title: str, author: str, year: str, journal_or_book: str = "") -> Dict[str, Any]:
        """Appends a well-formed BibTeX entry to bibliography.bib."""
        self.bib_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if already exists
        existing = [c["key"] for c in self.list_citations()]
        if key in existing:
            return {"ok": False, "error": f"Citation key '@{key}' already exists in bibliography.bib"}

        bib_text = f"""
@{entry_type}{{{key},
  author    = {{{author}}},
  title     = {{{title}}},
  year      = {{{year}}},
  journal   = {{{journal_or_book}}}
}}
"""
        with open(self.bib_file, "a", encoding="utf-8") as f:
            f.write(bib_text)

        try:
            rel_file = str(self.bib_file.relative_to(Path.cwd()))
        except ValueError:
            rel_file = str(self.bib_file)

        return {
            "ok": True,
            "key": key,
            "title": title,
            "author": author,
            "year": year,
            "file": rel_file,
        }
