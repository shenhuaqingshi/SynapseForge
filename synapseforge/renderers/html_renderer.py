"""
Publication-Grade Responsive HTML Renderer for SynapseForge Documents.
Implements modern typography, sticky Table of Contents, booktabs styling, and KaTeX math support.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import markdown


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css">
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
  <style>
    :root {
      --font-body: "KaiTi", "STKaiti", "楷体", "Times New Roman", Georgia, serif;
      --font-heading: "SimHei", "STHeiti", "黑体", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --bg-page: #f8fafc;
      --bg-card: #ffffff;
      --text-main: #1e293b;
      --text-muted: #64748b;
      --primary: #1e3a8a;
      --border-color: #e2e8f0;
      --line-height: 1.58;
    }
    
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 0;
      font-family: var(--font-body);
      font-size: 17px;
      line-height: var(--line-height);
      color: var(--text-main);
      background-color: var(--bg-page);
    }
    
    .container {
      display: flex;
      max-width: 1280px;
      margin: 0 auto;
      min-height: 100vh;
    }

    /* Sidebar Navigation */
    .sidebar {
      width: 280px;
      padding: 40px 24px;
      position: sticky;
      top: 0;
      height: 100vh;
      overflow-y: auto;
      border-right: 1px solid var(--border-color);
      background: #ffffff;
    }
    .sidebar h3 {
      font-family: var(--font-heading);
      font-size: 15px;
      text-transform: uppercase;
      letter-spacing: 1px;
      color: var(--text-muted);
      margin-bottom: 16px;
    }
    .sidebar ul {
      list-style: none;
      padding: 0;
      margin: 0;
    }
    .sidebar li {
      margin-bottom: 10px;
      font-size: 14px;
    }
    .sidebar a {
      color: var(--text-main);
      text-decoration: none;
      transition: color 0.2s;
    }
    .sidebar a:hover {
      color: var(--primary);
      font-weight: bold;
    }

    /* Main Article */
    .content-area {
      flex: 1;
      padding: 48px 64px;
      max-width: 900px;
      background: var(--bg-card);
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
    }

    .doc-header {
      border-bottom: 2px solid var(--border-color);
      padding-bottom: 28px;
      margin-bottom: 40px;
    }
    h1 {
      font-family: var(--font-heading);
      font-size: 32px;
      font-weight: 800;
      color: #0f172a;
      line-height: 1.3;
      margin-top: 0;
    }
    .meta-bar {
      font-size: 14px;
      color: var(--text-muted);
      margin-top: 12px;
    }
    .meta-bar span {
      margin-right: 18px;
    }

    h2 {
      font-family: var(--font-heading);
      font-size: 24px;
      font-weight: 700;
      color: #1e3a8a;
      margin-top: 48px;
      margin-bottom: 18px;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 8px;
    }
    h3 {
      font-family: var(--font-heading);
      font-size: 19px;
      font-weight: 600;
      color: #334155;
      margin-top: 32px;
      margin-bottom: 12px;
    }
    p {
      text-align: justify;
      margin-bottom: 20px;
      text-indent: 2em;
    }
    p.no-indent, .doc-header p, blockquote p, li p {
      text-indent: 0;
    }

    /* Academic Booktabs Table */
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 32px 0;
      font-size: 15px;
      border-top: 2.5px solid #0f172a;
      border-bottom: 2.5px solid #0f172a;
    }
    th {
      border-bottom: 1.5px solid #0f172a;
      padding: 10px 14px;
      text-align: left;
      font-family: var(--font-heading);
      font-weight: 600;
      background-color: #f8fafc;
    }
    td {
      padding: 9px 14px;
      border-top: 0.5px solid #e2e8f0;
      vertical-align: top;
    }
    tr:last-child td {
      border-bottom: none;
    }

    /* Code Blocks */
    pre {
      background: #0f172a;
      color: #f8fafc;
      padding: 18px 20px;
      border-radius: 8px;
      overflow-x: auto;
      font-family: "JetBrains Mono", Consolas, Monaco, monospace;
      font-size: 14px;
      line-height: 1.45;
    }
    code {
      font-family: "JetBrains Mono", Consolas, Monaco, monospace;
      font-size: 0.9em;
      background: #f1f5f9;
      padding: 2px 6px;
      border-radius: 4px;
      color: #0f172a;
    }
    pre code {
      background: transparent;
      padding: 0;
      color: inherit;
    }

    /* Blockquotes */
    blockquote {
      border-left: 4px solid var(--primary);
      margin: 24px 0;
      padding: 12px 20px;
      background: #eff6ff;
      border-radius: 0 8px 8px 0;
      font-style: normal;
      color: #1e40af;
    }

    /* SVG Figures */
    .figure-container {
      text-align: center;
      margin: 36px 0;
    }
    .figure-caption {
      font-size: 14px;
      color: var(--text-muted);
      margin-top: 10px;
      font-weight: 500;
    }
  </style>
</head>
<body>
  <div class="container">
    <nav class="sidebar">
      <h3>Table of Contents</h3>
      <ul>
        {% for h in headings %}
        <li style="margin-left: {{ (h.level - 1) * 12 }}px;">
          <a href="#{{ h.slug }}">{{ h.title }}</a>
        </li>
        {% endfor %}
      </ul>
    </nav>
    <main class="content-area">
      <div class="doc-header">
        <h1>{{ title }}</h1>
        <div class="meta-bar">
          <span><strong>Authors</strong>: {{ authors }}</span>
          <span><strong>Generated by</strong>: SynapseForge Swarm</span>
        </div>
      </div>
      <article>
        {{ content_html | safe }}
      </article>
    </main>
  </div>
  <script>
    document.addEventListener("DOMContentLoaded", function () {
      if (window.renderMathInElement) {
        renderMathInElement(document.body, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "$", right: "$", display: false },
          ],
          throwOnError: false,
        });
      }
    });
  </script>
</body>
</html>
"""


class HTMLRenderer:
    """Renders consolidated Markdown into a clean, publication-ready HTML whitepaper."""

    @staticmethod
    def render(markdown_text: str, title: str, authors: List[str] = None) -> str:
        # Render Markdown to HTML with the toc extension so the heading ids in
        # the body are the ones python-markdown itself generates.
        md = markdown.Markdown(
            extensions=["tables", "fenced_code", "toc", "sane_lists"]
        )
        html_body = md.convert(markdown_text)

        # Build the sidebar TOC from the toc extension tokens so the anchor
        # hrefs always match the real ids in the body (python-markdown gives
        # Chinese headings ids like "_1", not \w-based slugs).
        headings = []

        def _collect_toc(tokens):
            for tok in tokens:
                if tok.get("level", 0) <= 3:
                    headings.append({
                        "level": tok["level"],
                        "title": tok["name"],
                        "slug": tok["id"],
                    })
                _collect_toc(tok.get("children", []))

        _collect_toc(getattr(md, "toc_tokens", []))

        from jinja2 import Environment
        from markupsafe import Markup

        # autoescape escapes title/authors/headings; the Markdown-rendered
        # body is trusted and explicitly marked safe.
        env = Environment(autoescape=True)
        t = env.from_string(HTML_TEMPLATE)
        return t.render(
            title=title,
            authors=", ".join(authors or ["SynapseForge Swarm"]),
            headings=headings,
            content_html=Markup(html_body),
        )
