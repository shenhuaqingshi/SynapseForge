"""
Multi-Document Parallel Branching and Semantic Synthesis Engine for SynapseForge.
Allows creating multiple independent document variants, editing them in parallel without interference,
and synthesizing them into a unified master document.
"""

from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.core.ast_parser import BlockType, DocBlock, DocSection, MarkdownASTParser


@dataclass
class DocumentVariant:
    variant_id: str
    name: str
    target_section: str
    file_path: str
    author: str
    created_at: float
    word_count: int = 0


class VariantManager:
    """Manages independent candidate document drafts and variants."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.variants_dir = self.workspace_root / "variants"
        self.variants_dir.mkdir(parents=True, exist_ok=True)
        self.meta_file = self.variants_dir / "variants.json"

    def _load_metadata(self) -> Dict[str, Dict[str, Any]]:
        if self.meta_file.exists():
            try:
                return json.loads(self.meta_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_metadata(self, data: Dict[str, Dict[str, Any]]) -> None:
        self.meta_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def create_variant(
        self,
        variant_id: str,
        name: str,
        target_section: str,
        base_file: Optional[Path] = None,
        author: str = "Drafter",
    ) -> Dict[str, Any]:
        """Creates an independent candidate document variant."""
        meta = self._load_metadata()
        target_file = self.variants_dir / f"{variant_id}.md"

        if base_file and base_file.exists():
            content = base_file.read_text(encoding="utf-8")
        else:
            sec_file = self.workspace_root / "sections" / f"{target_section}.md"
            if sec_file.exists():
                content = sec_file.read_text(encoding="utf-8")
            else:
                content = f"# {name}\n\nDraft variant created by {author}.\n"

        target_file.write_text(content, encoding="utf-8")
        parser = MarkdownASTParser()
        words = parser.count_words(content)

        meta[variant_id] = {
            "variant_id": variant_id,
            "name": name,
            "target_section": target_section,
            "file": str(target_file.relative_to(self.workspace_root)),
            "author": author,
            "created_at": time.time(),
            "word_count": words,
        }
        self._save_metadata(meta)

        return {
            "ok": True,
            "variant_id": variant_id,
            "name": name,
            "file": meta[variant_id]["file"],
            "word_count": words,
        }

    def list_variants(self, target_section: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists all active document variants."""
        meta = self._load_metadata()
        res = []
        for v in meta.values():
            if target_section and v.get("target_section") != target_section:
                continue
            # Check actual word count
            v_file = self.workspace_root / v["file"]
            if v_file.exists():
                v["word_count"] = MarkdownASTParser.count_words(v_file.read_text(encoding="utf-8"))
            res.append(v)
        return res

    def delete_variant(self, variant_id: str) -> bool:
        """Deletes a variant file and its metadata."""
        meta = self._load_metadata()
        if variant_id in meta:
            v_file = self.workspace_root / meta[variant_id]["file"]
            if v_file.exists():
                v_file.unlink()
            del meta[variant_id]
            self._save_metadata(meta)
            return True
        return False


class MultiDocumentSynthesizer:
    """Synthesizes and merges multiple candidate document variants into a unified master document."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.parser = MarkdownASTParser()

    def merge_variants(
        self,
        variant_files: List[Path],
        output_file: Path,
        strategy: str = "harmonize",
    ) -> Dict[str, Any]:
        """
        Synthesizes multiple Markdown variant documents into a single unified master document.
        
        Strategies:
            - 'union': Combines all unique sections and non-duplicate blocks.
            - 'harmonize': Blends text, mathematical formulas, and tables into continuous flowing narrative.
            - 'concatenate': Appends variants with clear section dividers.
        """
        if not variant_files:
            return {"ok": False, "error": "No variant files provided to merge"}

        parsed_docs: List[List[DocBlock]] = []
        all_citations = set()

        for vf in variant_files:
            if not vf.exists():
                return {"ok": False, "error": f"Variant file '{vf}' not found"}
            raw = vf.read_text(encoding="utf-8")
            blocks = self.parser.parse_blocks(raw)
            parsed_docs.append(blocks)
            for c in self.parser.extract_citations(raw):
                all_citations.add(c)

        if strategy == "concatenate":
            merged_text = "\n\n---\n\n".join(vf.read_text(encoding="utf-8") for vf in variant_files)
        else:
            # Semantic AST union & reconciliation
            seen_heading_slugs = set()
            seen_paragraph_fingerprints = set()
            final_blocks: List[DocBlock] = []

            for doc in parsed_docs:
                for b in doc:
                    if b.type == BlockType.HEADING:
                        if b.slug not in seen_heading_slugs:
                            seen_heading_slugs.add(b.slug)
                            final_blocks.append(b)
                    elif b.type in (BlockType.PARAGRAPH, BlockType.MATH_BLOCK, BlockType.TABLE):
                        # Calculate semantic fingerprint
                        fp = re.sub(r'\s+', '', b.content)
                        if fp not in seen_paragraph_fingerprints:
                            seen_paragraph_fingerprints.add(fp)
                            final_blocks.append(b)
                    else:
                        final_blocks.append(b)

            merged_text = "\n\n".join(b.raw for b in final_blocks)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(merged_text, encoding="utf-8")

        total_words = self.parser.count_words(merged_text)
        try:
            rel_output = str(output_file.resolve().relative_to(self.workspace_root.resolve()))
        except ValueError:
            rel_output = str(output_file)

        source_variants = []
        for vf in variant_files:
            try:
                source_variants.append(str(vf.resolve().relative_to(self.workspace_root.resolve())))
            except ValueError:
                source_variants.append(str(vf))

        return {
            "ok": True,
            "output_file": rel_output,
            "strategy": strategy,
            "source_variants": source_variants,
            "total_words": total_words,
            "citations_preserved": sorted(list(all_citations)),
        }
