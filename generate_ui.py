import json
from pathlib import Path

sections = {}
for p in sorted(Path('sections').glob('*.md')):
    sec_num = p.stem.split('_')[0]
    sec_key = f'sec_{sec_num}'
    sections[sec_key] = {
        'name': p.name,
        'content': p.read_text(encoding='utf-8')
    }

sections_json = json.dumps(sections, ensure_ascii=False, indent=2)

html_template = """<!DOCTYPE html>
<html lang="zh-CN" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SynapseForge Studio</title>
  
  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  
  <!-- KaTeX for Perfect Mathematical Formula Rendering -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css">
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/contrib/auto-render.min.js"></script>

  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&family=Noto+Serif+SC:wght@400;600&display=swap');

    :root {
      --bg-app: #0c0d10;
      --bg-sidebar: #101116;
      --bg-center: #12141a;
      --bg-editor: #0c0d10;
      --bg-preview: #ffffff;
      --border: rgba(255, 255, 255, 0.05);
      --text-main: #e4e4e7;
      --text-muted: #71717a;
      --accent: #0a84ff;
    }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "PingFang SC", sans-serif;
      background: var(--bg-app);
      color: var(--text-main);
      -webkit-font-smoothing: antialiased;
      overflow: hidden;
      letter-spacing: -0.01em;
    }

    .font-mono {
      font-family: "SF Mono", "JetBrains Mono", Menlo, monospace;
    }

    .font-serif-sc {
      font-family: "Noto Serif SC", "STKaiti", "KaiTi", "Times New Roman", Georgia, serif;
    }

    /* Minimal Apple Traffic Lights */
    .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
    .dot-r { background: #ff5f56; }
    .dot-y { background: #ffbd2e; }
    .dot-g { background: #27c93f; }

    /* Academic 3-Line Table (Booktabs) */
    .booktabs {
      width: 100%;
      border-collapse: collapse;
      border-top: 1.5px solid #111827;
      border-bottom: 1.5px solid #111827;
      margin: 16px 0;
    }
    .booktabs th {
      border-bottom: 1px solid #111827;
      padding: 8px 12px;
      font-weight: 600;
      color: #111827;
      text-align: left;
    }
    .booktabs td {
      border-top: 0.5px solid #e5e7eb;
      padding: 7px 12px;
      color: #374151;
    }

    /* KaTeX equation display refinement */
    .katex-display {
      margin: 1.2em 0 !important;
      overflow-x: auto;
      overflow-y: hidden;
    }
    .katex {
      font-size: 1.05em;
    }

    /* Subtle minimalist scrollbar */
    ::-webkit-scrollbar { width: 4px; height: 4px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.08); border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.15); }
  </style>
</head>
<body class="h-screen w-screen flex items-center justify-center p-2 select-none">

  <!-- MAIN macOS APP SHELL -->
  <div class="w-full h-full max-w-[1800px] max-h-[1050px] rounded-xl bg-[#0c0d10] shadow-2xl flex flex-col overflow-hidden border border-white/[0.06]">

    <!-- MINIMAL TITLEBAR -->
    <header class="h-10 bg-[#0c0d10] border-b border-white/[0.05] px-3.5 flex items-center justify-between shrink-0">
      
      <!-- Left: Window Dots & Project Title -->
      <div class="flex items-center space-x-3">
        <div class="flex items-center space-x-1.5">
          <span class="dot dot-r"></span>
          <span class="dot dot-y"></span>
          <span class="dot dot-g"></span>
        </div>
        <div class="h-3 w-px bg-white/10"></div>
        <span class="text-xs font-medium text-zinc-300">Distributed Multi-Agent Consensus</span>
        <span class="text-[10px] text-zinc-600 font-mono">v1.0</span>
      </div>

      <!-- Center: Current Document Path -->
      <div class="text-xs text-zinc-500">
        sections / <span id="top-section-name" class="text-zinc-200 font-medium">02_theoretical_foundations.md</span>
      </div>

      <!-- Right: Minimal Status -->
      <div class="flex items-center space-x-3 text-xs">
        <div class="flex items-center space-x-1.5 text-zinc-400">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span class="text-[11px] font-mono text-zinc-400">Mesh Active</span>
        </div>
        
        <button onclick="triggerAgentDraft()" class="bg-blue-600 hover:bg-blue-500 text-white text-xs px-2.5 py-1 rounded-md transition font-medium">
          Ask Agent
        </button>
      </div>
    </header>

    <!-- 3-COLUMN WORKSPACE -->
    <div class="flex-1 flex overflow-hidden">

      <!-- ======================================================== -->
      <!-- COLUMN 1: MINIMAL NAVIGATOR (Sections & Agent Fleet)     -->
      <!-- ======================================================== -->
      <aside class="w-56 bg-[#101116] border-r border-white/[0.05] flex flex-col shrink-0 overflow-hidden text-xs">
        
        <!-- Document Sections -->
        <div class="h-[55%] flex flex-col border-b border-white/[0.05] overflow-hidden p-2">
          <div class="px-2 py-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
            Sections
          </div>

          <div class="flex-1 overflow-y-auto space-y-0.5 mt-1">
            <div onclick="switchSection('sec_01')" id="nav-sec_01" class="nav-item flex items-center justify-between px-2 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] cursor-pointer">
              <span class="truncate">01_abstract.md</span>
              <span class="text-[10px] text-zinc-600 font-mono">439w</span>
            </div>

            <div onclick="switchSection('sec_02')" id="nav-sec_02" class="nav-item flex items-center justify-between px-2 py-1.5 rounded-md bg-white/[0.07] text-white font-medium cursor-pointer">
              <span class="truncate">02_theory.md</span>
              <span class="text-[10px] text-zinc-400 font-mono">447w</span>
            </div>

            <div onclick="switchSection('sec_03')" id="nav-sec_03" class="nav-item flex items-center justify-between px-2 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] cursor-pointer">
              <span class="truncate">03_architecture.md</span>
              <span class="text-[10px] text-zinc-600 font-mono">495w</span>
            </div>

            <div onclick="switchSection('sec_04')" id="nav-sec_04" class="nav-item flex items-center justify-between px-2 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] cursor-pointer">
              <span class="truncate">04_consensus.md</span>
              <span class="text-[10px] text-zinc-600 font-mono">430w</span>
            </div>

            <div onclick="switchSection('sec_05')" id="nav-sec_05" class="nav-item flex items-center justify-between px-2 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] cursor-pointer">
              <span class="truncate">05_benchmarks.md</span>
              <span class="text-[10px] text-zinc-600 font-mono">464w</span>
            </div>

            <div onclick="switchSection('sec_06')" id="nav-sec_06" class="nav-item flex items-center justify-between px-2 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] cursor-pointer">
              <span class="truncate">06_conclusion.md</span>
              <span class="text-[10px] text-zinc-600 font-mono">238w</span>
            </div>
          </div>
        </div>

        <!-- Agent Specialists Roster -->
        <div class="flex-1 flex flex-col p-2 overflow-hidden bg-[#0c0d10]/40">
          <div class="px-2 py-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">
            Agent Swarm
          </div>

          <div class="flex-1 overflow-y-auto space-y-1 mt-1 text-xs">
            <div class="p-2 rounded-md bg-white/[0.02] border border-white/[0.03] flex items-center justify-between">
              <div>
                <div class="text-zinc-300 font-medium">Drafter</div>
                <div class="text-[10px] text-zinc-500">LaTeX proof active</div>
              </div>
              <span class="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
            </div>

            <div class="p-2 rounded-md bg-white/[0.02] border border-white/[0.03] flex items-center justify-between">
              <div>
                <div class="text-zinc-300 font-medium">Critic</div>
                <div class="text-[10px] text-zinc-500">Zero AI fluff</div>
              </div>
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
            </div>

            <div class="p-2 rounded-md bg-white/[0.02] border border-white/[0.03] flex items-center justify-between">
              <div>
                <div class="text-zinc-300 font-medium">Harmonizer</div>
                <div class="text-[10px] text-zinc-500">Voice cohesive</div>
              </div>
              <span class="w-1.5 h-1.5 rounded-full bg-zinc-600"></span>
            </div>
          </div>
        </div>

      </aside>

      <!-- ======================================================== -->
      <!-- COLUMN 2: COMMAND & TIMELINE (Center)                   -->
      <!-- ======================================================== -->
      <section class="w-[360px] bg-[#12141a] border-r border-white/[0.05] flex flex-col shrink-0 overflow-hidden text-xs">
        
        <!-- Header -->
        <div class="h-9 px-3 border-b border-white/[0.05] flex items-center justify-between text-zinc-400">
          <span class="font-medium text-zinc-300">Activity Stream</span>
          <span class="text-[11px] font-mono text-zinc-500">Live</span>
        </div>

        <!-- Activity Timeline -->
        <div id="activity-stream" class="flex-1 p-3 overflow-y-auto space-y-3">
          
          <!-- User Prompt -->
          <div class="space-y-1">
            <div class="text-zinc-500 text-[10px]">You • 16:10</div>
            <div class="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.04] text-zinc-300 leading-relaxed">
              Drafter, derive the formal mathematical proof for AST convergence bound.
            </div>
          </div>

          <!-- Drafter Response -->
          <div class="space-y-1.5">
            <div class="text-purple-400 text-[10px] font-medium flex items-center space-x-1.5">
              <span class="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
              <span>Drafter Agent</span>
            </div>
            <div class="p-2.5 rounded-lg bg-purple-950/20 border border-purple-500/20 text-zinc-300 space-y-2">
              <p class="leading-relaxed text-xs">
                Derived formal AST block reconciliation equations and topological space DAG model. KaTeX live preview rendered with perfect typography.
              </p>
            </div>
          </div>

          <!-- Critic Review -->
          <div class="space-y-1.5">
            <div class="text-emerald-400 text-[10px] font-medium flex items-center space-x-1.5">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span>Critic Quality Gate</span>
            </div>
            <div class="p-2.5 rounded-lg bg-emerald-950/15 border border-emerald-500/20 text-zinc-300">
              <p class="leading-relaxed text-xs text-zinc-300">
                ✓ BibTeX @shapiro2011crdt verified.<br>
                ✓ All LaTeX equations syntactically valid.<br>
                ✓ Pure prose flow with zero formulaic AI list.
              </p>
            </div>
          </div>

        </div>

        <!-- Clean Prompt Input -->
        <div class="p-2.5 border-t border-white/[0.05] bg-[#0c0d10]">
          <div class="flex items-center bg-white/[0.04] rounded-lg px-2.5 py-1.5 border border-white/[0.06]">
            <input id="agent-input" onkeydown="if(event.key==='Enter') handleSend()" type="text" placeholder="Instruct agent..." class="bg-transparent text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none flex-1">
            <button onclick="handleSend()" class="text-zinc-400 hover:text-white text-xs ml-1">
              <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
            </button>
          </div>
        </div>
      </section>

      <!-- ======================================================== -->
      <!-- COLUMN 3: REAL-TIME EDITOR & KATEX PREVIEW (Right)       -->
      <!-- ======================================================== -->
      <main class="flex-1 flex flex-col bg-[#0c0d10] overflow-hidden">
        
        <!-- Canvas Toolbar -->
        <div class="h-9 border-b border-white/[0.05] bg-[#0c0d10] px-4 flex items-center justify-between text-xs shrink-0">
          <div class="flex items-center space-x-2 text-zinc-400">
            <span id="doc-title-label" class="font-medium text-zinc-300">02_theoretical_foundations.md</span>
            <span class="text-zinc-600">|</span>
            <span id="word-count-badge" class="font-mono text-[11px] text-zinc-400">447 words</span>
          </div>

          <div class="flex items-center space-x-2">
            <span class="text-[11px] text-emerald-400 font-mono">KaTeX Live Math Active</span>
          </div>
        </div>

        <!-- Split Pane: Source & Real-Time Rendered Publication -->
        <div class="flex-1 flex overflow-hidden">
          
          <!-- Left: Markdown Source Editor -->
          <div class="w-1/2 border-r border-white/[0.05] flex flex-col font-mono text-xs overflow-hidden bg-[#0c0d10]">
            <div class="h-7 bg-white/[0.015] px-3 flex items-center justify-between text-[10px] text-zinc-500 border-b border-white/[0.03]">
              <span>MARKDOWN SOURCE</span>
              <span class="text-zinc-600 font-mono">Live Input</span>
            </div>

            <textarea id="markdown-editor" oninput="renderLivePreview()" class="flex-1 p-5 bg-transparent text-zinc-300 resize-none focus:outline-none leading-relaxed font-mono text-[12px] overflow-y-auto"></textarea>
          </div>

          <!-- Right: Real-time Publication Preview with Pure KaiTi & KaTeX -->
          <div class="w-1/2 flex flex-col bg-[#ffffff] text-zinc-900 overflow-hidden font-serif-sc">
            <div class="h-7 bg-zinc-50 px-3.5 flex items-center justify-between text-[10px] text-zinc-500 border-b border-zinc-200 font-sans">
              <span class="font-medium text-zinc-700">REAL-TIME PUBLICATION PREVIEW</span>
              <span class="text-zinc-500 font-mono">KaiTi + Times • KaTeX Formulas</span>
            </div>

            <div id="publication-preview" class="flex-1 p-8 overflow-y-auto space-y-4 text-justify leading-[1.65] text-[14px]">
              <!-- Content dynamically rendered by renderLivePreview() -->
            </div>
          </div>

        </div>
      </main>

    </div>

  </div>

  <script>
    const SECTIONS = __SECTIONS_JSON__;
    let currentSection = 'sec_02';

    // Real-time Markdown + KaTeX Math parser
    function parseMarkdownToHTML(md) {
      let html = md;

      // Extract and preserve math blocks $$ ... $$
      const displayMath = [];
      html = html.replace(/\\$\\$([\\s\\S]*?)\\$\\$/g, function(match, math) {
        displayMath.push(math);
        return `%%%DISPLAY_MATH_${displayMath.length - 1}%%%`;
      });

      // Extract and preserve inline math $ ... $
      const inlineMath = [];
      html = html.replace(/\\$([^\\$\\n]+?)\\$/g, function(match, math) {
        inlineMath.push(math);
        return `%%%INLINE_MATH_${inlineMath.length - 1}%%%`;
      });

      // Headings
      html = html.replace(/^# (.*$)/gim, '<h1 class="font-sans font-bold text-lg text-zinc-900 border-b border-zinc-200 pb-1.5 mb-3">$1</h1>');
      html = html.replace(/^## (.*$)/gim, '<h2 class="font-sans font-semibold text-base text-zinc-900 border-b border-zinc-150 pb-1 mt-4 mb-2">$1</h2>');
      html = html.replace(/^### (.*$)/gim, '<h3 class="font-sans font-medium text-sm text-zinc-800 mt-3 mb-1.5">$1</h3>');

      // Tables (Convert Markdown tables to Academic 3-line Booktabs tables)
      const lines = html.split('\\n');
      let inTable = false;
      let tableRows = [];
      let newLines = [];

      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line.startsWith('|') && line.endsWith('|')) {
          if (!inTable) {
            inTable = true;
            tableRows = [];
          }
          if (!line.includes('---')) {
            tableRows.push(line);
          }
        } else {
          if (inTable) {
            inTable = false;
            newLines.push(buildBooktabsTable(tableRows));
          }
          newLines.push(lines[i]);
        }
      }
      if (inTable) {
        newLines.push(buildBooktabsTable(tableRows));
      }
      html = newLines.join('\\n');

      // Paragraphs
      html = html.split('\\n\\n').map(para => {
        para = para.trim();
        if (!para) return '';
        if (para.startsWith('<h') || para.startsWith('<table') || para.startsWith('<div')) {
          return para;
        }
        return `<p class="indent-8 text-zinc-800 my-2 leading-[1.65]">${para}</p>`;
      }).join('\\n\\n');

      // Restore inline math
      html = html.replace(/%%%INLINE_MATH_(\\d+)%%%/g, function(match, idx) {
        return `$${inlineMath[idx]}$`;
      });

      // Restore display math
      html = html.replace(/%%%DISPLAY_MATH_(\\d+)%%%/g, function(match, idx) {
        return `$$${displayMath[idx]}$$`;
      });

      return html;
    }

    function buildBooktabsTable(rows) {
      if (rows.length === 0) return '';
      let tableHtml = '<div class="my-4"><table class="booktabs text-xs font-sans">';
      
      // Header row
      const headerCols = rows[0].split('|').filter(c => c.trim().length > 0);
      tableHtml += '<thead><tr class="bg-zinc-50">';
      headerCols.forEach(c => {
        tableHtml += `<th>${c.trim()}</th>`;
      });
      tableHtml += '</tr></thead><tbody>';

      // Data rows
      for (let i = 1; i < rows.length; i++) {
        const cols = rows[i].split('|').filter(c => c.trim().length > 0);
        tableHtml += '<tr>';
        cols.forEach(c => {
          tableHtml += `<td>${c.trim()}</td>`;
        });
        tableHtml += '</tr>';
      }
      tableHtml += '</tbody></table></div>';
      return tableHtml;
    }

    function renderLivePreview() {
      const editor = document.getElementById('markdown-editor');
      const preview = document.getElementById('publication-preview');
      const text = editor.value;

      // Count words
      const cjk = (text.match(/[\\u4e00-\\u9fff]/g) || []).length;
      const latin = (text.match(/[a-zA-Z0-9_\\-]+/g) || []).length;
      document.getElementById('word-count-badge').innerText = `${cjk + latin} words`;

      // Render Markdown HTML
      preview.innerHTML = parseMarkdownToHTML(text);

      // Render KaTeX Math
      if (window.renderMathInElement) {
        renderMathInElement(preview, {
          delimiters: [
            {left: '$$', right: '$$', display: true},
            {left: '$', right: '$', display: false}
          ],
          throwOnError: false
        });
      }
    }

    function switchSection(secId) {
      currentSection = secId;
      document.querySelectorAll('.nav-item').forEach(el => {
        el.className = 'nav-item flex items-center justify-between px-2 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] cursor-pointer';
      });
      const activeNav = document.getElementById('nav-' + secId);
      if (activeNav) {
        activeNav.className = 'nav-item flex items-center justify-between px-2 py-1.5 rounded-md bg-white/[0.07] text-white font-medium cursor-pointer';
      }

      if (SECTIONS[secId]) {
        document.getElementById('markdown-editor').value = SECTIONS[secId].content;
        document.getElementById('doc-title-label').innerText = SECTIONS[secId].name;
        document.getElementById('top-section-name').innerText = SECTIONS[secId].name;
      }
      renderLivePreview();
    }

    function triggerAgentDraft() {
      const editor = document.getElementById('markdown-editor');
      editor.value += "\\n\\n## 形式化一致性收敛定理\\n\\n设节点往返通信时延为 $\\\\tau_j$，系统全局状态收敛上界满足：\\n\\n$$\\n\\\\mathbb{E}[\\\\tau_{\\\\text{sync}}] \\\\le \\\\frac{1}{\\\\mu - \\\\lambda} \\\\ln \\\\left( \\\\frac{|\\\\mathcal{V}|}{\\\\epsilon} \\\\right) + \\\\max_{j \\\\in \\\\mathcal{N}} \\\\{\\\\text{RTT}_j\\\\}\\n$$\\n";
      renderLivePreview();
    }

    function handleSend() {
      const input = document.getElementById('agent-input');
      const text = input.value.trim();
      if (text) {
        const stream = document.getElementById('activity-stream');
        const userCard = document.createElement('div');
        userCard.className = 'space-y-1';
        userCard.innerHTML = `<div class="text-zinc-500 text-[10px]">You • Just now</div><div class="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.04] text-zinc-300 leading-relaxed">${text}</div>`;
        stream.appendChild(userCard);

        const agentCard = document.createElement('div');
        agentCard.className = 'space-y-1.5';
        agentCard.innerHTML = `<div class="text-purple-400 text-[10px] font-medium flex items-center space-x-1.5"><span class="w-1.5 h-1.5 rounded-full bg-purple-400"></span><span>Drafter Agent</span></div><div class="p-2.5 rounded-lg bg-purple-950/20 border border-purple-500/20 text-zinc-300 leading-relaxed text-xs">Incorporating request into current section AST. Math equations updated.</div>`;
        stream.appendChild(agentCard);
        stream.scrollTop = stream.scrollHeight;

        triggerAgentDraft();
        input.value = '';
      }
    }

    // Initialize when KaTeX is loaded
    window.addEventListener('DOMContentLoaded', () => {
      setTimeout(() => {
        switchSection('sec_02');
      }, 200);
    });
  </script>
</body>
</html>
"""

full_html = html_template.replace('__SECTIONS_JSON__', sections_json)
Path('synapseforge/ui/index.html').write_text(full_html, encoding='utf-8')
print('synapseforge/ui/index.html written successfully!')
