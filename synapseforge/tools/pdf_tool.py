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
        def sanitize_formula(m: str) -> str:
            m = m.strip()
            m = m.replace(r'\left(', '(').replace(r'\right)', ')')
            m = m.replace(r'\left[', '[').replace(r'\right]', ']')
            m = m.replace(r'\left\{', '(').replace(r'\right\}', ')')
            m = m.replace(r'\left', '').replace(r'\right', '')
            m = m.replace(r'\dots', 'dots').replace(r'\cdots', 'dots')
            
            # Fractions and roots
            for _ in range(5):
                m = re.sub(r'\\frac\{([^{}]+)\}\{([^{}]+)\}', r'(\1) / (\2)', m)
            m = re.sub(r'\\sqrt\[([^\]]+)\]\{([^{}]+)\}', r'root(\1, \2)', m)
            m = re.sub(r'\\sqrt\{([^{}]+)\}', r'sqrt(\1)', m)

            # Standard functions & operators
            m = re.sub(r'\\operatorname\{([^}]+)\}', r'op("\1")', m)
            m = re.sub(r'\\mathrm\{([^}]+)\}', r'upright("\1")', m)
            m = re.sub(r'\\arg\\min|\\argmin', r'op("arg min")', m)
            m = re.sub(r'\\arg\\max|\\argmax', r'op("arg max")', m)
            m = re.sub(r'\\hat\{([^}]+)\}', r'hat(\1)', m)
            m = re.sub(r'\\mathcal\{([^}]+)\}', r'cal(\1)', m)
            m = re.sub(r'\\mathbb\{([^}]+)\}', r'bb(\1)', m)
            m = re.sub(r'\\mathbf\{([^}]+)\}', r'bold(\1)', m)
            m = re.sub(r'\\text\{([^}]+)\}', r'"\1"', m)
            
            # Relations & symbols (using word boundaries or strict patterns)
            m = m.replace(r'\|', '||')
            m = m.replace(r'\{', '(').replace(r'\}', ')')
            m = re.sub(r'\\cap\b', 'inter', m)
            m = re.sub(r'\\cup\b', 'union', m)
            m = re.sub(r'\\subseteq\b', 'subset.eq', m)
            m = re.sub(r'\\subset\b', 'subset', m)
            m = re.sub(r'\\notin\b', ' not in ', m)
            m = re.sub(r'\\in\b', ' in ', m)
            m = re.sub(r'\\leq?\b', '<=', m)
            m = re.sub(r'\\geq?\b', '>=', m)
            m = re.sub(r'\\neq?\b', '!=', m)
            m = re.sub(r'\\approx\b', 'approx', m)
            m = re.sub(r'\\sim\b', 'tilde', m)
            m = re.sub(r'\\times\b', 'times', m)
            m = re.sub(r'\\cdot\b|cdot\b', 'dot.c', m)
            m = re.sub(r'\\to\b|\\rightarrow\b', '->', m)
            m = re.sub(r'\\leftarrow\b', '<-', m)
            m = re.sub(r'\\infty\b', 'oo', m)
            m = re.sub(r'\\forall\b', 'forall', m)
            m = re.sub(r'\\exists\b', 'exists', m)
            m = re.sub(r'\\ln\b', 'ln', m)
            m = re.sub(r'\\log\b', 'log', m)
            m = re.sub(r'\\max\b', 'max', m)
            m = re.sub(r'\\min\b', 'min', m)
            m = re.sub(r'\\sum\b', 'sum', m)
            m = re.sub(r'\\prod\b', 'product', m)
            m = re.sub(r'\\int\b', 'integral', m)
            m = re.sub(r'\\partial\b', 'diff', m)
            m = re.sub(r'\\nabla\b', 'nabla', m)
            m = re.sub(r'\\prec\b', 'prec', m)
            
            # Greek letters
            greek = [
                ("alpha", "alpha"), ("beta", "beta"), ("gamma", "gamma"), ("delta", "delta"),
                ("epsilon", "epsilon"), ("zeta", "zeta"), ("eta", "eta"), ("theta", "theta"),
                ("iota", "iota"), ("kappa", "kappa"), ("lambda", "lambda"), ("mu", "mu"),
                ("nu", "nu"), ("xi", "xi"), ("pi", "pi"), ("rho", "rho"), ("sigma", "sigma"),
                ("tau", "tau"), ("upsilon", "upsilon"), ("phi", "phi"), ("chi", "chi"),
                ("psi", "psi"), ("omega", "omega"),
                ("Gamma", "Gamma"), ("Delta", "Delta"), ("Theta", "Theta"), ("Lambda", "Lambda"),
                ("Xi", "Xi"), ("Pi", "Pi"), ("Sigma", "Sigma"), ("Phi", "Phi"), ("Psi", "Psi"),
                ("Omega", "Omega"),
            ]
            for g_tex, g_typ in greek:
                m = re.sub(rf'\\{g_tex}\b', g_typ, m)

            m = re.sub(r'\\([a-zA-Z]+)', r'\1', m)
            return m

        # Convert display math blocks $$ ... $$ to Typst block math
        def repl_display(match):
            m = sanitize_formula(match.group(1))
            return f"\n$ {m} $\n"

        md = re.sub(r'\$\$([\s\S]*?)\$\$', repl_display, md)

        # Inline math $ ... $
        def repl_inline(match):
            m = sanitize_formula(match.group(1))
            return f"$ {m} $"

        md = re.sub(r'(?<!\$)\$(?!\$)([^\$\n]+)\$(?!\$)', repl_inline, md)
        return md

    def _convert_markdown_tables_to_typst(self, md: str) -> str:
        """Converts GitHub-flavored markdown tables into Typst booktabs-style tables."""
        lines = md.split("\n")
        out: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("|") and line.endswith("|"):
                rows: List[List[str]] = []
                while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    row_line = lines[i].strip()
                    if not re.match(r'^\|[\s\-:|]+\|$', row_line):
                        cells = [c.strip() for c in row_line.strip("|").split("|")]
                        rows.append(cells)
                    i += 1
                if rows:
                    ncols = max(len(r) for r in rows)
                    parts = [
                        "#table(",
                        f"  columns: {ncols},",
                        "  stroke: none,",
                        "  inset: (x: 8pt, y: 5pt),",
                        "  table.hline(y: 0, stroke: 1.2pt),",
                        "  table.hline(y: 1, stroke: 0.8pt),",
                        "  table.header(",
                    ]
                    for cell in rows[0] + [""] * (ncols - len(rows[0])):
                        parts.append(f"    [{cell}],")
                    parts.append("  ),")
                    for body_row in rows[1:]:
                        for cell in body_row + [""] * (ncols - len(body_row)):
                            parts.append(f"  [{cell}],")
                    parts.append("  table.hline(stroke: 1.2pt),")
                    parts.append(")")
                    out.append("\n".join(parts))
                continue
            out.append(lines[i])
            i += 1
        return "\n".join(out)

    @staticmethod
    def _convert_markdown_emphasis_to_typst(md: str) -> str:
        """Converts markdown bold/italic markers into Typst strong/emph syntax."""
        # Italic first: its lookarounds cannot match inside `**bold**`, whereas
        # running bold first would produce `*bold*` that the italic rule re-matches.
        md = re.sub(r'(?<![*\w])\*([^*\n]+)\*(?![*\w])', r'_\1_', md)
        md = re.sub(r'\*\*([^*]+)\*\*', r'*\1*', md)
        return md

    @staticmethod
    def _convert_markdown_headings_to_typst(md: str) -> str:
        """Convert ATX headings at line start only. Do not rewrite inline ``# `` (C#, issue # 12)."""
        fences: list[str] = []

        def _stash(match: re.Match) -> str:
            fences.append(match.group(0))
            return "<<<SFCODE%d>>>" % (len(fences) - 1)

        protected = re.sub(r"```[\s\S]*?```", _stash, md)
        protected = re.sub(r"(?m)^### ", "=== ", protected)
        protected = re.sub(r"(?m)^## ", "== ", protected)
        protected = re.sub(r"(?m)^# ", "= ", protected)
        for i, block in enumerate(fences):
            protected = protected.replace("<<<SFCODE%d>>>" % i, block)
        return protected

    @staticmethod
    def _find_bibliography(markdown_path: Path) -> Optional[Path]:
        """Prefer a .bib next to the manuscript or its parent workspace, not an unrelated cwd file."""
        markdown_path = Path(markdown_path)
        for candidate in (
            markdown_path.parent / "bibliography.bib",
            markdown_path.parent.parent / "bibliography.bib",
            Path.cwd() / "bibliography.bib",
        ):
            if candidate.is_file():
                return candidate
        return None

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
        typst_content = self._convert_markdown_tables_to_typst(typst_content)
        typst_content = self._convert_markdown_emphasis_to_typst(typst_content)
        typst_content = self._convert_markdown_headings_to_typst(typst_content)

        # If bibliography exists and document has citations, link it
        has_citations = bool(re.search(r'(?<![\w.@])@[a-zA-Z0-9_\-]+', raw_md))
        bib_file = self._find_bibliography(markdown_path)
        if has_citations and bib_file is not None and bib_file.exists():
            try:
                shutil.copy(bib_file, output_pdf.parent / "bibliography.bib")
                typst_content += '\n\n#bibliography("bibliography.bib", title: "参考文献", style: "ieee")\n'
            except Exception:
                pass
        else:
            typst_content = re.sub(r'(?<![\w.@])@([a-zA-Z0-9_\-]+)', r'[\1]', typst_content)

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
