"""
Unified Publication Pipeline: Assembles, renders, and exports all artifact targets.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.config import ProjectConfig, load_config
from synapseforge.core.ast_parser import MarkdownASTParser
from synapseforge.renderers.html_renderer import HTMLRenderer
from synapseforge.renderers.typst_renderer import TypstRenderer


@dataclass
class BuildResult:
    success: bool
    output_dir: str
    generated_files: List[str] = field(default_factory=list)
    total_words: int = 0
    document_title: str = ""


class PublicationPipeline:
    """Builds multi-format publication deliverables from distributed document sections."""

    def __init__(self, project_root: Optional[Path] = None, config: Optional[ProjectConfig] = None):
        self.project_root = project_root or Path.cwd()
        self.config = config or load_config(self.project_root / "synapseforge.yaml")
        self.output_dir = self.project_root / self.config.render.output_dir

    def build_all(self, master_markdown: str) -> BuildResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        generated = []

        # 1. Master Markdown file
        md_path = self.output_dir / "document.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(master_markdown)
        generated.append(str(md_path.relative_to(self.project_root)))

        # 2. HTML publication file
        html_content = HTMLRenderer.render(
            markdown_text=master_markdown,
            title=self.config.document_title,
            authors=self.config.authors,
        )
        html_path = self.output_dir / "index.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        generated.append(str(html_path.relative_to(self.project_root)))

        # 3. Typst publication file
        typst_content = TypstRenderer.render(
            markdown_text=master_markdown,
            title=self.config.document_title,
            authors=self.config.authors,
        )
        typst_path = self.output_dir / "document.typ"
        with open(typst_path, "w", encoding="utf-8") as f:
            f.write(typst_content)
        generated.append(str(typst_path.relative_to(self.project_root)))

        # 4. Copy assets directory if present
        assets_src = self.project_root / "assets"
        assets_dst = self.output_dir / "assets"
        if assets_src.exists():
            if assets_dst.exists():
                shutil.rmtree(assets_dst)
            shutil.copytree(assets_src, assets_dst)
            generated.append(f"{self.config.render.output_dir}/assets/")

        # Compute word count (CJK-aware: Chinese characters + Western words)
        words = MarkdownASTParser.count_words(master_markdown)

        return BuildResult(
            success=True,
            output_dir=str(self.output_dir.relative_to(self.project_root)),
            generated_files=generated,
            total_words=words,
            document_title=self.config.document_title,
        )
