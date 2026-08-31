"""
Publication PDF Compiler Tool for SynapseForge.
Complying with `publication-pdf-layout` standards: Pure KaiTi (Chinese) + Times New Roman (Western),
comfortable 14pt body font, 1.48 line-height, booktabs tables, deep-black bold headings.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


TYPST_ACADEMIC_TEMPLATE = """// SynapseForge Publication-Grade PDF Layout
#set page(
  paper: "a4",
  margin: (x: 2.0cm, top: 2.4cm, bottom: 2.4cm),
  fill: rgb("#ffffff"),
  header: align(right)[#text(size: 10pt, font: ("Times New Roman", "KaiTi", "FZKai-Z03", "AR PL UKai CN", "LXGW WenKai"), fill: rgb("#666666"))[{{HEADER_TITLE}}]],
  footer: context align(center)[#text(size: 10pt, font: ("Times New Roman", "KaiTi", "FZKai-Z03", "AR PL UKai CN", "LXGW WenKai"))[#counter(page).display()]],
)

// 正文设定：楷体 + Times，14pt舒适出版级字号
#set text(
  font: ("Times New Roman", "KaiTi", "FZKai-Z03", "AR PL UKai CN", "LXGW WenKai"),
  size: 14pt,
  lang: "zh",
  fill: rgb("#111111"),
  stroke: 0.015pt + rgb("#111111"),
)

#set par(
  leading: 0.88em,
  first-line-indent: 2em,
  justify: true,
)

// 强力深黑加粗 (weight: bold + stroke: 0.09pt)
#show strong: it => text(weight: "bold", stroke: 0.09pt + rgb("#000000"), font: ("Times New Roman", "KaiTi", "FZKai-Z03", "AR PL UKai CN", "LXGW WenKai"))[#it.body]

// 各级标题阶梯加粗
#show heading.where(level: 1): it => block(
  above: 1.8em,
  below: 1.2em,
  text(size: 18.5pt, weight: "bold", stroke: 0.12pt + rgb("#000000"), font: ("Times New Roman", "KaiTi", "FZKai-Z03", "AR PL UKai CN", "LXGW WenKai"))[#it.body]
)

#show heading.where(level: 2): it => block(
  above: 1.4em,
  below: 0.9em,
  text(size: 16.5pt, weight: "bold", stroke: 0.10pt + rgb("#000000"), font: ("Times New Roman", "KaiTi", "FZKai-Z03", "AR PL UKai CN", "LXGW WenKai"))[#it.body]
)

#show heading.where(level: 3): it => block(
  above: 1.1em,
  below: 0.6em,
  text(size: 14.5pt, weight: "bold", stroke: 0.08pt + rgb("#000000"), font: ("Times New Roman", "KaiTi", "FZKai-Z03", "AR PL UKai CN", "LXGW WenKai"))[#it.body]
)

// 出版级三线表 (Booktabs)
#show table: set table(
  stroke: none,
  fill: none,
)

#show table.cell: it => {
  set text(size: 11pt, font: ("Times New Roman", "KaiTi", "FZKai-Z03", "AR PL UKai CN", "LXGW WenKai"))
  it
}

{{CONTENT}}
"""


class PDFTool:
    """Publication-grade Chinese PDF compiler using Typst and pure KaiTi typography across Windows, macOS, and Linux."""

    def __init__(self, typst_bin: Optional[str] = None):
        self.typst_bin = typst_bin or self._find_typst_bin()

    def _find_typst_bin(self) -> str:
        which_path = shutil.which("typst")
        if which_path:
            return which_path

        candidates = [
            "/usr/bin/typst",
            "/usr/local/bin/typst",
            "/opt/homebrew/bin/typst",
            str(Path.home() / ".cargo" / "bin" / "typst"),
            str(Path.home() / ".cargo" / "bin" / "typst.exe"),
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        return "typst"

    def is_available(self) -> bool:
        return Path(self.typst_bin).exists() or shutil.which("typst") is not None

    def _convert_latex_math_to_typst(self, md: str) -> str:
        """Sanitizes LaTeX math formulas into Typst compatible math syntax."""
        # Convert display math blocks $$ ... $$ to Typst block math
        def repl_display(match):
            m = match.group(1).strip()
            m = m.replace(r'\left(', '(').replace(r'\right)', ')')
            m = m.replace(r'\left[', '[').replace(r'\right]', ']')
            m = m.replace(r'\left\{', '(').replace(r'\right\}', ')')
            m = m.replace(r'\left', '').replace(r'\right', '')
            m = m.replace(r'\dots', 'dots').replace(r'\cdots', 'dots')
            m = re.sub(r'\\mathcal\{([^}]+)\}', r'cal(\1)', m)
            m = re.sub(r'\\mathbb\{([^}]+)\}', r'bb(\1)', m)
            m = re.sub(r'\\mathbf\{([^}]+)\}', r'bold(\1)', m)
            m = re.sub(r'\\text\{([^}]+)\}', r'"\1"', m)
            m = m.replace(r'\cap', r'inter')
            m = m.replace(r'\cup', r'union')
            m = m.replace(r'\subseteq', r'subset.eq')
            m = m.replace(r'\le', r'<=')
            m = m.replace(r'\ge', r'>=')
            m = m.replace(r'\ln', r'ln')
            m = m.replace(r'\max', r'max')
            m = m.replace(r'\sum', r'sum')
            m = m.replace(r'\epsilon', r'epsilon')
            m = m.replace(r'\tau', r'tau')
            m = m.replace(r'\mu', r'mu')
            m = m.replace(r'\lambda', r'lambda')
            m = m.replace(r'\prec', r'prec')
            m = m.replace(r'\cdot', 'dot.c').replace('cdot', 'dot.c')
            m = m.replace(r'\{', r'(').replace(r'\}', r')')
            m = re.sub(r'\\([a-zA-Z]+)', r'\1', m)
            return f"\n$ {m} $\n"

        md = re.sub(r'\$\$([\s\S]*?)\$\$', repl_display, md)

        # Inline math $ ... $
        def repl_inline(match):
            m = match.group(1).strip()
            m = m.replace(r'\left(', '(').replace(r'\right)', ')')
            m = m.replace(r'\left[', '[').replace(r'\right]', ']')
            m = m.replace(r'\left\{', '(').replace(r'\right\}', ')')
            m = m.replace(r'\left', '').replace(r'\right', '')
            m = m.replace(r'\dots', 'dots').replace(r'\cdots', 'dots')
            m = re.sub(r'\\mathcal\{([^}]+)\}', r'cal(\1)', m)
            m = re.sub(r'\\mathbb\{([^}]+)\}', r'bb(\1)', m)
            m = re.sub(r'\\mathbf\{([^}]+)\}', r'bold(\1)', m)
            m = re.sub(r'\\text\{([^}]+)\}', r'"\1"', m)
            m = m.replace(r'\le', r'<=').replace(r'\ge', r'>=')
            m = m.replace(r'\cap', r'inter')
            m = m.replace(r'\prec', r'prec')
            m = m.replace(r'\cdot', 'dot.c').replace('cdot', 'dot.c')
            m = m.replace(r'\{', r'(').replace(r'\}', r')')
            m = re.sub(r'\\([a-zA-Z]+)', r'\1', m)
            return f"$ {m} $"

        md = re.sub(r'(?<!\$)\$(?!\$)([^\$\n]+)\$(?!\$)', repl_inline, md)
        return md

    def compile_markdown_to_pdf(
        self,
        markdown_path: Path,
        output_pdf: Path,
        title: str = "SynapseForge Academic Report",
    ) -> Dict[str, Any]:
        """Compiles Markdown into publication-grade Chinese/English PDF using Typst."""
        if not markdown_path.exists():
            return {"ok": False, "error": f"Input markdown {markdown_path} not found"}

        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        raw_md = markdown_path.read_text(encoding="utf-8")

        # Convert simple markdown headers/body into typst syntax
        typst_content = self._convert_latex_math_to_typst(raw_md)
        typst_content = typst_content.replace("### ", "=== ")
        typst_content = typst_content.replace("## ", "== ")
        typst_content = typst_content.replace("# ", "= ")

        # If bibliography exists and document has citations, link it
        has_citations = bool(re.search(r'@[a-zA-Z0-9_\-]+', raw_md))
        bib_file = Path.cwd() / "bibliography.bib"
        if has_citations and bib_file.exists():
            try:
                shutil.copy(bib_file, output_pdf.parent / "bibliography.bib")
                typst_content += '\n\n#bibliography("bibliography.bib", title: "参考文献", style: "ieee")\n'
            except Exception:
                pass
        else:
            typst_content = re.sub(r'@([a-zA-Z0-9_\-]+)', r'[\1]', typst_content)

        full_typst = TYPST_ACADEMIC_TEMPLATE.replace("{{HEADER_TITLE}}", title).replace("{{CONTENT}}", typst_content)
        
        temp_typst = output_pdf.with_suffix(".typ")
        temp_typst.write_text(full_typst, encoding="utf-8")

        if self.is_available():
            root_dir = str(output_pdf.parent.resolve())
            cmd = [self.typst_bin, "compile", "--root", root_dir, str(temp_typst), str(output_pdf)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                return {
                    "ok": True,
                    "output_pdf": str(output_pdf),
                    "engine": "typst",
                    "page_standard": "A4 / 14pt KaiTi + Times / Booktabs",
                    "file_size": output_pdf.stat().st_size if output_pdf.exists() else 0,
                }
            else:
                # Fallback without --root
                fallback_cmd = [self.typst_bin, "compile", str(temp_typst), str(output_pdf)]
                fb_res = subprocess.run(fallback_cmd, capture_output=True, text=True)
                if fb_res.returncode == 0:
                    return {
                        "ok": True,
                        "output_pdf": str(output_pdf),
                        "engine": "typst",
                        "page_standard": "A4 / 14pt KaiTi + Times / Booktabs",
                        "file_size": output_pdf.stat().st_size if output_pdf.exists() else 0,
                    }
                return {"ok": False, "error": res.stderr or fb_res.stderr, "engine": "typst"}

        return {"ok": False, "error": "Typst compiler not available"}
