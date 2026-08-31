"""
Multi-Format Academic Publication Exporter for SynapseForge.
Compiles whole multi-section projects into publication-grade PDF, Word (.docx),
standalone HTML, and submission bundle packages.
"""

from __future__ import annotations

import html
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.config import ProjectConfig, load_config
from synapseforge.core.ast_parser import MarkdownASTParser
from synapseforge.tools.office_tool import OfficeTool
from synapseforge.tools.pdf_tool import PDFTool


class MultiFormatExporter:
    """Exports and packages entire SynapseForge projects into multiple standard publication formats."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.dist_dir = self.workspace_root / "dist"
        self.dist_dir.mkdir(parents=True, exist_ok=True)
        self.parser = MarkdownASTParser()

    def assemble_full_document(self) -> str:
        """Assembles all sections in sorted topological DAG order into a unified Markdown manuscript."""
        sec_dir = self.workspace_root / "sections"
        section_files = sorted(sec_dir.glob("*.md"))
        
        full_blocks = []
        for p in section_files:
            content = p.read_text(encoding="utf-8").strip()
            if content:
                full_blocks.append(content)

        return "\n\n---\n\n".join(full_blocks)

    def export_all(self, title: Optional[str] = None) -> Dict[str, Any]:
        """Compiles project into PDF, Word docx, standalone HTML, and zip submission package."""
        config_path = self.workspace_root / "synapseforge.yaml"
        if not config_path.exists():
            config_path = self.workspace_root / "synapseforge.yml"
        config = load_config(config_path) if config_path.exists() else ProjectConfig()
        doc_title = title or config.document_title or "SynapseForge Publication Document"

        # 1. Assemble unified markdown
        full_md_content = self.assemble_full_document()
        full_md_path = self.dist_dir / "full_manuscript.md"
        full_md_path.write_text(full_md_content, encoding="utf-8")

        outputs = {}

        # 2. Compile Publication PDF (Typst / KaiTi + Times)
        pdf_tool = PDFTool()
        pdf_path = self.dist_dir / "publication_paper.pdf"
        pdf_res = pdf_tool.compile_markdown_to_pdf(full_md_path, pdf_path, title=doc_title)
        outputs["pdf"] = pdf_res.get("output_pdf") if pdf_res.get("ok") else None

        # 3. Compile Word Manuscript (.docx)
        office_tool = OfficeTool()
        docx_path = self.dist_dir / "publication_manuscript.docx"
        docx_res = office_tool.create_docx_from_markdown(full_md_path, docx_path, title=doc_title)
        outputs["docx"] = docx_res.get("output_file") if docx_res.get("ok") else None

        # 4. Standalone HTML
        html_path = self.dist_dir / "publication_standalone.html"
        html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>{html.escape(doc_title)}</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
<style>
body {{ font-family: "STKaiti", "KaiTi", "Times New Roman", serif; max-width: 860px; margin: 40px auto; padding: 20px; line-height: 1.65; color: #111827; }}
h1, h2, h3 {{ font-family: -apple-system, sans-serif; font-weight: bold; }}
table {{ border-collapse: collapse; width: 100%; margin: 20px 0; border-top: 1.5px solid #111; border-bottom: 1.5px solid #111; }}
th, td {{ padding: 8px 12px; text-align: left; }}
</style>
</head>
<body>
<h1>{html.escape(doc_title)}</h1>
<pre style="white-space: pre-wrap; font-family: inherit;">{html.escape(full_md_content)}</pre>
</body>
</html>
"""
        html_path.write_text(html_content, encoding="utf-8")
        outputs["html"] = str(html_path.relative_to(self.workspace_root))

        # 5. Build zip package
        zip_path = self.dist_dir / "submission_package.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if pdf_path.exists():
                zf.write(pdf_path, arcname="publication_paper.pdf")
            if docx_path.exists():
                zf.write(docx_path, arcname="publication_manuscript.docx")
            if html_path.exists():
                zf.write(html_path, arcname="publication_standalone.html")
            zf.write(full_md_path, arcname="full_manuscript.md")
        outputs["zip_package"] = str(zip_path.relative_to(self.workspace_root))

        total_words = self.parser.count_words(full_md_content)

        return {
            "ok": True,
            "title": doc_title,
            "total_words": total_words,
            "sections_count": len(list((self.workspace_root / "sections").glob("*.md"))),
            "artifacts": outputs,
        }
