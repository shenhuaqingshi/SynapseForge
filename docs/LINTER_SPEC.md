# SynapseForge Quality Gate & Anti-AI Linter Specification

SynapseForge enforces rigorous academic and technical publication standards to ensure all written outputs remain cohesive, precise, and completely devoid of formulaic AI artifacts.

## 1. Anti-AI Flavor Standards (Zero AI Flavor)

| Category | Prohibited Pattern | Required Alternative |
|---|---|---|
| Cliché Openings | "在当今数字化时代...", "随着...的快速发展...", "In today's fast-paced world..." | Direct opening stating core technical mechanism, mathematical premise, or empirical metric. |
| Cliché Transitions | "首先、其次、再次、最后", "总而言之", "综上所述", "值得注意的是", "不可否认的是" | Natural semantic bridges between paragraphs based on mechanistic causality. |
| Vacuous Buzzwords | "赋能", "闭环", "顶层设计", "抓手", "打法", "全方位矩阵", "game-changer", "delve", "tapestry" | Precise engineering or scientific terms with quantitative metrics. |

## 2. Ban on Formulaic List Addiction

Technical analysis must be structured in **continuous narrative analytical prose** (150–300 words per paragraph):
- Consecutive bullet points (`-`, `*`, `1.`) exceeding 35% of content lines are strictly blocked.
- Multi-dimensional comparisons must be formatted into **academic 3-line tables (booktabs)**.

## 3. Typographical & Citation Integrity

- **CJK-Latin Spacing**: Chinese and Western/numeric characters must have space separation.
- **Booktabs Tables**: Tables must include top rule, bottom rule, and header separator line with zero vertical borders.
- **BibTeX Verification**: Every `@cite_key` in the Markdown document must exist in `bibliography.bib`.
