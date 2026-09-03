"""
Citation and BibTeX Management Tool for SynapseForge.
Enables AI Agents and human authors to search, validate, and append clean BibTeX references,
resolve DOIs via CrossRef APIs, and validate citation graphs across document sections.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from synapseforge.core.ast_parser import MarkdownASTParser


def _matching_brace(text: str, open_idx: int) -> Optional[int]:
    """Return the index of the brace that closes ``text[open_idx]``, skipping quoted ``}``."""
    if open_idx < 0 or open_idx >= len(text) or text[open_idx] != "{":
        return None
    depth = 0
    in_quote = False
    escape = False
    for i in range(open_idx, len(text)):
        ch = text[i]
        if in_quote:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_quote = False
            continue
        if ch == '"':
            in_quote = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _iter_bib_entries(content: str):
    """Yield ``(entry_type, cite_key, body, raw)`` for each BibTeX entry.

    Brace-matched so compact one-line entries (no newline before ``}``) parse
    the same as the conventional multiline form.
    """
    i = 0
    n = len(content)
    while i < n:
        at = content.find("@", i)
        if at < 0:
            return
        header = re.match(r"@([a-zA-Z]+)\s*\{\s*([a-zA-Z0-9_\-:]+)\s*,", content[at:])
        if not header:
            i = at + 1
            continue
        brace = content.find("{", at)
        end = _matching_brace(content, brace)
        if end is None:
            return
        body = content[at + header.end() : end]
        raw = content[at : end + 1]
        yield header.group(1), header.group(2), body, raw
        i = end + 1


def _bib_field(body: str, name: str) -> str:
    """Read a BibTeX field, keeping quoted titles and nested braces intact."""
    match = re.search(rf"{re.escape(name)}\s*=\s*", body, re.IGNORECASE)
    if not match:
        return ""
    rest = body[match.end():].lstrip()
    if rest.startswith("{"):
        depth = 0
        for i, ch in enumerate(rest):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return rest[1:i].strip()
        return rest[1:].strip()
    if rest.startswith('"'):
        escape = False
        chars = []
        for ch in rest[1:]:
            if escape:
                chars.append(ch)
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                return "".join(chars).strip()
            chars.append(ch)
        return "".join(chars).strip()
    token = re.match(r"([^,}\s]+)", rest)
    return token.group(1).strip() if token else ""


def _bib_year(body: str) -> str:
    value = _bib_field(body, "year")
    year = re.search(r"(\d{4})", value)
    return year.group(1) if year else ""


class CiteTool:
    """Manages BibTeX citations, DOI lookups, CrossRef search, and citation graph references."""

    def __init__(self, bib_path: Optional[Path] = None, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.bib_file = bib_path or self.workspace_root / "bibliography.bib"
        self.parser = MarkdownASTParser()

    def list_citations(self) -> List[Dict[str, str]]:
        """Parses all existing entries in bibliography.bib."""
        if not self.bib_file.exists():
            return []

        content = self.bib_file.read_text(encoding="utf-8")
        entries = []
        for entry_type, cite_key, body, raw in _iter_bib_entries(content):
            entries.append({
                "key": cite_key,
                "type": entry_type,
                "title": _bib_field(body, "title"),
                "author": _bib_field(body, "author"),
                "year": _bib_year(body),
                "journal": _bib_field(body, "journal") or _bib_field(body, "booktitle"),
                "raw": raw,
            })
        return entries

    def add_bibtex_entry(
        self, key: str, entry_type: str, title: str, author: str, year: str, journal_or_book: str = "", doi: str = ""
    ) -> Dict[str, Any]:
        """Appends a well-formed BibTeX entry to bibliography.bib."""
        self.bib_file.parent.mkdir(parents=True, exist_ok=True)

        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-:]+", key or ""):
            return {"ok": False, "error": f"Invalid citation key '{key}'"}
        if not re.fullmatch(r"[A-Za-z]+", entry_type or ""):
            return {"ok": False, "error": f"Invalid entry type '{entry_type}'"}

        existing = [c["key"] for c in self.list_citations()]
        if key in existing:
            return {"ok": False, "error": f"Citation key '@{key}' already exists in bibliography.bib"}

        doi_field = f"\n  doi       = {{{doi}}}," if doi else ""
        bib_text = f"""
@{entry_type}{{{key},
  author    = {{{author}}},
  title     = {{{title}}},
  year      = {{{year}}},
  journal   = {{{journal_or_book}}}{doi_field}
}}
"""
        with open(self.bib_file, "a", encoding="utf-8") as f:
            f.write(bib_text)

        try:
            rel_file = str(self.bib_file.relative_to(self.workspace_root))
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

    def clean_doi(self, raw_doi: str) -> str:
        """Strips URL prefixes or doi: protocol prefix to yield standard DOI string."""
        doi = raw_doi.strip()
        doi = re.sub(r'^(?:https?://)?(?:dx\.)?doi\.org/', '', doi, flags=re.IGNORECASE)
        doi = re.sub(r'^doi:\s*', '', doi, flags=re.IGNORECASE)
        return doi.strip()
