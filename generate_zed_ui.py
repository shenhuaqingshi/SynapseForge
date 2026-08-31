"""SynapseForge Studio UI generator.

Reads the real manuscript sections from ./sections/ and emits a self-contained
synapseforge/ui/index.html. At runtime the page prefers the live daemon APIs
(/api/sections, /api/doc/save, /api/prompts, /api/pdf/build) and gracefully
falls back to the embedded snapshot when opened as a static file.
"""

import json
from pathlib import Path

sections = {}
for p in sorted(Path("sections").glob("*.md")):
    sec_num = p.stem.split("_")[0]
    sections[f"sec_{sec_num}"] = {
        "name": p.name,
        "content": p.read_text(encoding="utf-8"),
    }

sections_json = json.dumps(sections, ensure_ascii=False, indent=2)

html_template = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SynapseForge Studio</title>

  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.css">
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/katex.min.js"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.10/dist/contrib/auto-render.min.js"></script>

  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&family=Noto+Serif+SC:wght@400;600&display=swap');

    :root {
      --bg-app: #0e0f12;
      --bg-panel: #14161b;
      --bg-raised: #1a1d23;
      --border: rgba(255, 255, 255, 0.06);
      --text-main: #e6e6ea;
      --text-muted: #8b8f98;
      --text-faint: #5c6068;
      --accent: #3b82f6;
    }

    * { box-sizing: border-box; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Inter", "PingFang SC", sans-serif;
      background: var(--bg-app);
      color: var(--text-main);
      -webkit-font-smoothing: antialiased;
      overflow: hidden;
    }

    .font-mono { font-family: "SF Mono", "JetBrains Mono", Menlo, monospace; }
    .font-serif-sc { font-family: "Noto Serif SC", "Songti SC", "Times New Roman", Georgia, serif; }

    .surface { background: var(--bg-panel); border-color: var(--border); }
    .raised { background: var(--bg-raised); }

    /* Traffic lights */
    .dot { width: 11px; height: 11px; border-radius: 50%; display: inline-block; }
    .dot-r { background: #ff5f57; } .dot-y { background: #febc2e; } .dot-g { background: #28c840; }

    /* Presence avatars */
    .avatar {
      width: 22px; height: 22px; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 9px; font-weight: 600; color: #fff; cursor: pointer;
      border: 1.5px solid var(--bg-app); transition: transform .15s ease;
    }
    .avatar:hover { transform: translateY(-1px); }
    .avatar.is-followed { box-shadow: 0 0 0 2px var(--bg-app), 0 0 0 3.5px currentColor; }

    /* Booktabs academic table */
    .booktabs {
      width: 100%; border-collapse: collapse; margin: 1.25em 0; font-size: 12.5px;
      border-top: 1.5px solid #1f2937; border-bottom: 1.5px solid #1f2937;
      font-family: "Inter", -apple-system, sans-serif;
    }
    .booktabs th { border-bottom: 1px solid #1f2937; padding: 7px 14px; font-weight: 600; text-align: left; color: #111827; }
    .booktabs td { padding: 7px 14px; color: #374151; border-bottom: .5px solid #f0f0f2; }
    .booktabs tr:last-child td { border-bottom: none; }

    /* Preview typography */
    #publication-preview h1 { font-size: 20px; font-weight: 700; color: #111827; border-bottom: 1px solid #e5e7eb; padding-bottom: 8px; margin: 4px 0 14px; font-family: "Inter", -apple-system, sans-serif; }
    #publication-preview h2 { font-size: 15px; font-weight: 700; color: #111827; margin: 20px 0 8px; font-family: "Inter", -apple-system, sans-serif; }
    #publication-preview h3 { font-size: 13.5px; font-weight: 600; color: #1f2937; margin: 16px 0 6px; font-family: "Inter", -apple-system, sans-serif; }
    #publication-preview p  { text-indent: 2em; margin: 8px 0; color: #1f2937; }

    /* Buttons */
    .btn {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500;
      color: var(--text-muted); border: 1px solid var(--border);
      transition: all .15s ease; cursor: pointer; white-space: nowrap;
    }
    .btn:hover { color: var(--text-main); background: rgba(255,255,255,.05); }
    .btn-primary { background: var(--accent); border-color: transparent; color: #fff; }
    .btn-primary:hover { background: #2f74e0; color: #fff; }

    /* Nav items */
    .nav-item {
      display: flex; align-items: center; justify-content: space-between;
      padding: 6px 10px; border-radius: 6px; color: var(--text-muted);
      cursor: pointer; transition: all .12s ease; font-size: 12px;
    }
    .nav-item:hover { color: var(--text-main); background: rgba(255,255,255,.04); }
    .nav-item.is-active { color: #fff; background: rgba(255,255,255,.07); font-weight: 500; }

    .field {
      width: 100%; background: var(--bg-app); border: 1px solid var(--border);
      border-radius: 6px; padding: 7px 10px; color: var(--text-main); font-size: 12px;
      transition: border-color .15s ease;
    }
    .field:focus { outline: none; border-color: var(--accent); }

    /* Toast */
    #toast {
      position: fixed; bottom: 20px; left: 50%; transform: translate(-50%, 8px);
      background: var(--bg-raised); border: 1px solid var(--border); color: var(--text-main);
      font-size: 12px; padding: 7px 14px; border-radius: 8px;
      opacity: 0; pointer-events: none; transition: all .25s ease; z-index: 60;
      box-shadow: 0 8px 24px rgba(0,0,0,.4);
    }
    #toast.show { opacity: 1; transform: translate(-50%, 0); }

    /* Scrollbars */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(255,255,255,.07); border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,.14); }
  </style>
</head>
<body class="h-screen w-screen flex items-center justify-center p-2 select-none">

  <div class="w-full h-full max-w-[1800px] max-h-[1050px] rounded-xl surface shadow-2xl flex flex-col overflow-hidden border">

    <!-- ═══════════ TITLE BAR ═══════════ -->
    <header class="h-11 border-b px-4 flex items-center justify-between shrink-0">
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-1.5">
          <span class="dot dot-r"></span><span class="dot dot-y"></span><span class="dot dot-g"></span>
        </div>
        <span class="text-[13px] font-semibold text-zinc-200">SynapseForge Studio</span>
        <span class="text-[10px] text-zinc-600 font-mono hidden sm:inline">Zed-Mesh 2.0</span>
      </div>

      <div class="flex items-center gap-2 text-xs text-zinc-500">
        <span class="px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-400 font-mono text-[10px]"># consensus-room</span>
        <span class="text-zinc-700">/</span>
        <span id="top-section-name" class="text-zinc-300 font-medium">—</span>
      </div>

      <div class="flex items-center gap-3">
        <!-- Presence -->
        <div class="flex items-center -space-x-1.5 bg-black/30 px-2 py-1 rounded-full border border-white/[0.05]">
          <div class="avatar bg-blue-600" title="You (Commander)">xb</div>
          <div class="avatar bg-purple-600 text-purple-400" id="avatar-drafter" title="Follow Drafter Agent" onclick="toggleFollow('drafter')">D</div>
          <div class="avatar bg-amber-600 text-amber-400" id="avatar-critic" title="Follow Critic Agent" onclick="toggleFollow('critic')">C</div>
          <div class="avatar bg-emerald-600 text-emerald-400" id="avatar-harmonizer" title="Follow Harmonizer Agent" onclick="toggleFollow('harmonizer')">H</div>
        </div>

        <!-- Mesh status -->
        <div id="network-badge" class="flex items-center gap-1.5 px-2 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-medium">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span id="network-badge-text" class="font-mono">Mesh Connected</span>
        </div>

        <button class="btn" onclick="openPromptModal()">
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 0 1 1.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.27 1.06-.12 1.45l-.774.773a1.125 1.125 0 0 1-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.398.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 0 1-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.506-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.108-1.204l-.526-.738a1.125 1.125 0 0 1 .12-1.45l.773-.773a1.125 1.125 0 0 1 1.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894Z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/></svg>
          提示词
        </button>
        <button class="btn btn-primary" onclick="triggerAgentDraft()">Ask Agent</button>
      </div>
    </header>

    <!-- ═══════════ WORKSPACE ═══════════ -->
    <div class="flex-1 flex overflow-hidden">

      <!-- Column 1 · Navigator -->
      <aside class="w-56 surface border-r flex flex-col shrink-0 overflow-hidden text-xs">
        <div class="h-1/2 flex flex-col border-b overflow-hidden p-2">
          <div class="px-2 py-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider flex items-center justify-between">
            <span>Sections</span><span class="text-[9px] text-zinc-600 normal-case">AST DAG</span>
          </div>
          <div id="section-nav" class="flex-1 overflow-y-auto space-y-0.5 mt-1"></div>
        </div>

        <div class="flex-1 flex flex-col p-2 overflow-hidden">
          <div class="px-2 py-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider flex items-center justify-between">
            <span>User Prompts</span>
            <button onclick="openPromptModal()" class="text-[10px] text-blue-400 hover:text-blue-300 normal-case font-normal">+ 自定义</button>
          </div>
          <div id="prompt-cards" class="flex-1 overflow-y-auto space-y-1.5 mt-1 px-1"></div>
        </div>
      </aside>

      <!-- Column 2 · Swarm stream -->
      <section class="w-80 surface border-r flex flex-col shrink-0 overflow-hidden text-xs">
        <div class="h-10 px-3 border-b flex items-center justify-between">
          <span class="font-medium text-zinc-300 text-[13px]">Swarm Activity</span>
          <span class="text-[10px] text-zinc-500 font-mono">Live CRDT Sync</span>
        </div>

        <div id="activity-stream" class="flex-1 overflow-y-auto p-3 space-y-3">
          <div class="space-y-1">
            <div class="text-zinc-500 text-[10px]">Session Manager · System</div>
            <div class="p-2.5 rounded-lg raised border border-white/[0.04] text-zinc-400 text-[11px] leading-relaxed">
              Tailscale mesh connected. Custom prompts loaded from <span class="font-mono">./prompts/</span>.
            </div>
          </div>

          <div class="space-y-1.5">
            <div class="text-amber-400 text-[10px] font-medium flex items-center justify-between">
              <div class="flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                <span>Critic Agent · Peer Review</span>
              </div>
              <span class="text-[9px] text-zinc-500 font-mono">Line 42</span>
            </div>
            <div class="p-2.5 rounded-lg bg-amber-500/[0.07] border border-amber-500/20 text-zinc-300 leading-relaxed">
              <span class="text-amber-300 font-medium">Suggestion:</span> Bound convergence theorem proof with explicit RTT bounds.
              <div class="mt-2 flex items-center gap-2">
                <button onclick="triggerAgentDraft()" class="px-2 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-[10px] font-medium transition">Apply Patch</button>
                <button class="px-2 py-1 rounded hover:bg-white/[0.05] text-zinc-400 text-[10px] transition">Dismiss</button>
              </div>
            </div>
          </div>

          <div class="space-y-1.5">
            <div class="text-purple-400 text-[10px] font-medium flex items-center gap-1.5">
              <span class="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
              <span>Drafter Agent</span>
            </div>
            <div class="p-2.5 rounded-lg bg-purple-500/[0.07] border border-purple-500/20 text-zinc-300 leading-relaxed">
              Applying prompt rules from <span class="font-mono">prompts/drafter.md</span>. KaTeX preview synchronized.
            </div>
          </div>
        </div>

        <div class="p-2.5 border-t">
          <div class="relative flex items-center">
            <input id="agent-input" type="text" placeholder="Direct agents (@Drafter / @Critic)…"
              class="w-full raised text-zinc-200 placeholder-zinc-600 text-xs pl-3 pr-8 py-2 rounded-lg border border-white/[0.06] focus:outline-none focus:border-blue-500 transition"
              onkeydown="if(event.key==='Enter') handleSend()">
            <button onclick="handleSend()" class="absolute right-2 text-zinc-500 hover:text-zinc-200 transition">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5 21 12l-7.5 7.5M21 12H3"/></svg>
            </button>
          </div>
        </div>
      </section>

      <!-- Column 3 · Document studio -->
      <main class="flex-1 flex flex-col overflow-hidden">
        <div class="h-10 px-4 border-b flex items-center justify-between shrink-0">
          <div class="flex items-center gap-3 text-xs min-w-0">
            <span class="font-medium text-zinc-200 truncate" id="doc-title-label">—</span>
            <span class="text-zinc-700">|</span>
            <span class="text-zinc-500 text-[11px] shrink-0" id="word-count-badge">0 words</span>
            <span id="save-state" class="text-[11px] text-zinc-600 shrink-0 transition"></span>
          </div>
          <div id="follow-badge" class="hidden items-center gap-1.5 px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300 text-[10px] font-mono">
            <span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping"></span>
            <span id="follow-badge-text"></span>
          </div>
        </div>

        <div class="flex-1 flex overflow-hidden">
          <!-- Source editor -->
          <div class="w-1/2 border-r flex flex-col p-4 overflow-hidden">
            <div class="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2 flex items-center justify-between">
              <span>Markdown Source</span><span class="text-zinc-600 normal-case font-normal">Live AST Sync</span>
            </div>
            <textarea id="markdown-editor" spellcheck="false"
              class="flex-1 w-full bg-transparent text-zinc-300 font-mono text-xs leading-relaxed focus:outline-none resize-none overflow-y-auto"
              oninput="onEditorInput()"></textarea>
          </div>

          <!-- Preview -->
          <div class="w-1/2 flex flex-col bg-white overflow-hidden">
            <div class="h-9 px-3 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between shrink-0">
              <div class="flex items-center gap-1 bg-zinc-200/60 p-0.5 rounded-md">
                <button id="btn-mode-web" onclick="switchPreviewMode('web')" class="px-2.5 py-0.5 rounded text-[11px] font-medium bg-white text-zinc-800 shadow-sm transition">Web 预览</button>
                <button id="btn-mode-pdf" onclick="switchPreviewMode('pdf')" class="px-2.5 py-0.5 rounded text-[11px] font-medium text-zinc-500 hover:text-zinc-800 transition flex items-center gap-1">
                  出版级 PDF
                  <span id="pdf-latency-tag" class="text-[9px] bg-emerald-100 text-emerald-700 px-1 rounded font-mono hidden"></span>
                </button>
              </div>
              <div class="flex items-center gap-2 text-[10px] text-zinc-500 font-mono">
                <span id="pdf-status-indicator" class="flex items-center gap-1">
                  <span id="pdf-status-dot" class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                  <span id="pdf-status-text">Live Sync</span>
                </span>
                <button onclick="downloadCurrentPdf()" class="px-2 py-1 bg-zinc-200 hover:bg-zinc-300 rounded text-zinc-700 font-sans transition">导出 PDF</button>
              </div>
            </div>

            <div id="publication-preview" class="flex-1 px-8 py-6 overflow-y-auto font-serif-sc text-[13.5px] leading-[1.75] selection:bg-blue-100"></div>

            <div id="pdf-preview-container" class="flex-1 hidden bg-[#525659] overflow-hidden">
              <iframe id="pdf-viewer-frame" class="w-full h-full border-0 bg-white" title="PDF preview"></iframe>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>

  <!-- ═══════════ PROMPT PRESET MODAL ═══════════ -->
  <div id="prompt-modal" class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 hidden items-center justify-center p-4">
    <div class="surface border rounded-xl w-full max-w-2xl shadow-2xl flex flex-col overflow-hidden text-xs">
      <div class="h-11 px-4 raised border-b flex items-center justify-between">
        <span class="font-semibold text-zinc-200 text-[13px]">自定义 Agent 提示词预设</span>
        <button onclick="closePromptModal()" class="text-zinc-500 hover:text-zinc-200 transition p-1">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/></svg>
        </button>
      </div>

      <div class="p-5 space-y-4 overflow-y-auto max-h-[75vh]">
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-zinc-400 text-[11px] mb-1.5">Agent 角色标识 (Role ID)</label>
            <input id="modal-role-id" type="text" placeholder="e.g. drafter / my_philosopher" class="field">
          </div>
          <div>
            <label class="block text-zinc-400 text-[11px] mb-1.5">显示名称 (Display Name)</label>
            <input id="modal-display-name" type="text" placeholder="e.g. 学术起草专家" class="field">
          </div>
        </div>

        <div>
          <label class="block text-zinc-400 text-[11px] mb-1.5">推荐调用大模型 (Model Routing)</label>
          <select id="modal-model" class="field">
            <option value="deepseek-v3">DeepSeek-V3 · 学术长文叙事</option>
            <option value="deepseek-reasoner">DeepSeek-R1 · 深度逻辑推理与定理证明</option>
            <option value="gemini-2.0-flash">Gemini 2.0 Flash · 高速检索与代码生成</option>
            <option value="claude-3-7-sonnet">Claude 3.7 Sonnet · 结构审校与综合</option>
            <option value="ollama/qwen2.5:72b">Local Ollama / Qwen 2.5 · 离线私有化</option>
          </select>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1.5">
            <label class="text-zinc-400 text-[11px]">系统提示词内容 (Markdown,保存至 prompts/ 目录)</label>
            <span class="text-[10px] text-zinc-600">支持人设、写作规则、禁用词与数学符号要求</span>
          </div>
          <textarea id="modal-prompt-content" rows="10" spellcheck="false"
            placeholder="# Role: Custom Agent&#10;&#10;## Writing Guidelines&#10;1. Use formal tone…&#10;2. Enforce LaTeX formulas…"
            class="field font-mono resize-none leading-relaxed"></textarea>
        </div>
      </div>

      <div class="h-12 px-4 raised border-t flex items-center justify-between">
        <span class="text-[10px] text-zinc-600">提示词将自动同步并在所有协作节点间生效</span>
        <div class="flex items-center gap-2">
          <button onclick="closePromptModal()" class="btn">取消</button>
          <button onclick="saveUserCustomPrompt()" class="btn btn-primary">保存预设</button>
        </div>
      </div>
    </div>
  </div>

  <div id="toast" role="status"></div>

  <!-- ═══════════ SCRIPT ═══════════ -->
  <script>
    // ── Embedded snapshot (fallback when daemon is not running) ──
    const EMBEDDED_SECTIONS = __SECTIONS_JSON__;

    let SECTIONS = EMBEDDED_SECTIONS;
    let currentSection = null;
    let followingTarget = null;
    let currentPreviewMode = 'web';
    let livePdfDebounceTimer = null;
    let saveDebounceTimer = null;

    const DEFAULT_PROMPTS = {
      drafter:    { id: 'drafter',    name: 'Drafter · 学术起草专家',   model: 'deepseek-v3',       prompt: '# Role: Senior Academic Drafter\n\n## Writing Principles\n1. Zero AI clichés\n2. Dense narrative prose (150-300 words per paragraph)\n3. KaTeX equations & booktabs tables' },
      critic:     { id: 'critic',     name: 'Critic · 严苛审稿专家',    model: 'deepseek-reasoner', prompt: '# Role: Adversarial Peer Reviewer\n\n## Audit Checklist\n1. Flag hollow phrases\n2. Check bibliography references @citekey\n3. Verify math proof bounds' },
      harmonizer: { id: 'harmonizer', name: 'Harmonizer · 多方案调和官', model: 'deepseek-v3',       prompt: '# Role: Multi-Variant Harmonizer\n\n## Principles\n1. Reconcile tone differences\n2. Fuse mathematical and empirical variants\n3. Deduplicate bibliography keys' },
    };
    const USER_PROMPT_PRESETS = JSON.parse(JSON.stringify(DEFAULT_PROMPTS));

    const AGENT_COLORS = { drafter: 'purple', critic: 'amber', harmonizer: 'emerald' };

    // ── Boot: prefer live daemon sections ──
    async function boot() {
      try {
        const r = await fetch('/api/sections');
        const data = await r.json();
        if (data.ok && data.sections && Object.keys(data.sections).length) {
          SECTIONS = data.sections;
        }
      } catch (e) { /* static file mode */ }

      buildSectionNav();
      buildPromptCards();
      setupNetworkWatchdog();
      setupKeyboardShortcuts();

      const restored = restoreLocalSession();
      if (!restored) switchSection(Object.keys(SECTIONS)[0] || null);
    }

    // ── Section navigator ──
    function buildSectionNav() {
      const nav = document.getElementById('section-nav');
      nav.innerHTML = '';
      Object.entries(SECTIONS).forEach(([id, sec]) => {
        const el = document.createElement('div');
        el.className = 'nav-item';
        el.id = 'nav-' + id;
        el.onclick = () => switchSection(id);
        const label = document.createElement('span');
        label.className = 'truncate';
        label.textContent = sec.name;
        const count = document.createElement('span');
        count.className = 'text-[10px] text-zinc-600 font-mono shrink-0';
        count.textContent = countWords(sec.content) + 'w';
        el.appendChild(label);
        el.appendChild(count);
        nav.appendChild(el);
      });
    }

    function switchSection(secId) {
      if (!secId || !SECTIONS[secId]) return;
      currentSection = secId;
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('is-active'));
      const active = document.getElementById('nav-' + secId);
      if (active) active.classList.add('is-active');
      document.getElementById('markdown-editor').value = SECTIONS[secId].content;
      document.getElementById('doc-title-label').innerText = SECTIONS[secId].name;
      document.getElementById('top-section-name').innerText = SECTIONS[secId].name;
      setSaveState('');
      renderLivePreview();
    }

    // ── Prompt cards ──
    function buildPromptCards() {
      const wrap = document.getElementById('prompt-cards');
      wrap.innerHTML = '';
      Object.values(USER_PROMPT_PRESETS).forEach(p => {
        const color = AGENT_COLORS[p.id] || 'blue';
        const card = document.createElement('div');
        card.className = 'p-2.5 rounded-lg raised border border-white/[0.04] hover:border-white/[0.12] cursor-pointer transition';
        card.onclick = () => openPromptModal(p.id);
        const row = document.createElement('div');
        row.className = 'flex items-center justify-between';
        const left = document.createElement('div');
        left.className = 'flex items-center gap-1.5 font-medium text-zinc-300 min-w-0';
        const dot = document.createElement('span');
        dot.className = 'w-1.5 h-1.5 rounded-full shrink-0 bg-' + color + '-400';
        const name = document.createElement('span');
        name.className = 'truncate';
        name.textContent = p.name;
        left.appendChild(dot); left.appendChild(name);
        const tag = document.createElement('span');
        tag.className = 'text-[9px] text-zinc-600 font-mono shrink-0';
        tag.textContent = 'prompts/';
        row.appendChild(left); row.appendChild(tag);
        const model = document.createElement('p');
        model.className = 'text-[10.5px] text-zinc-500 mt-1 font-mono truncate';
        model.textContent = p.model;
        card.appendChild(row); card.appendChild(model);
        wrap.appendChild(card);
      });
    }

    // ── Prompt modal ──
    function openPromptModal(roleId) {
      const modal = document.getElementById('prompt-modal');
      modal.classList.remove('hidden'); modal.classList.add('flex');
      const p = roleId && USER_PROMPT_PRESETS[roleId];
      document.getElementById('modal-role-id').value = p ? p.id : '';
      document.getElementById('modal-display-name').value = p ? p.name : '';
      document.getElementById('modal-model').value = p ? p.model : 'deepseek-v3';
      document.getElementById('modal-prompt-content').value = p ? p.prompt : '';
    }

    function closePromptModal() {
      const modal = document.getElementById('prompt-modal');
      modal.classList.add('hidden'); modal.classList.remove('flex');
    }

    function saveUserCustomPrompt() {
      const roleId = document.getElementById('modal-role-id').value.trim();
      const displayName = document.getElementById('modal-display-name').value.trim();
      const model = document.getElementById('modal-model').value;
      const promptContent = document.getElementById('modal-prompt-content').value;
      if (!roleId) { showToast('请输入 Role ID', true); return; }

      USER_PROMPT_PRESETS[roleId] = { id: roleId, name: displayName || roleId, model, prompt: promptContent };
      buildPromptCards();

      fetch('/api/prompts', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_id: roleId, display_name: displayName, model, prompt_content: promptContent }),
      }).catch(() => {});

      closePromptModal();
      showToast(`已保存提示词预设 prompts/${roleId}.md`);
    }

    // ── Markdown → HTML ──
    function parseMarkdownToHTML(md) {
      if (!md) return '';
      let html = md;
      const displayMath = [];
      const inlineMath = [];

      html = html.replace(/\$\$([\s\S]*?)\$\$/g, (_, m) => {
        displayMath.push(m.trim());
        return `%%%DISPLAY_MATH_${displayMath.length - 1}%%%`;
      });
      html = html.replace(/(?<!\$)\$(?!\$)([^\$\n]+)\$(?!\$)/g, (_, m) => {
        inlineMath.push(m.trim());
        return `%%%INLINE_MATH_${inlineMath.length - 1}%%%`;
      });

      html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
      html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
      html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
      html = html.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-zinc-900">$1</strong>');
      html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

      // Tables
      const lines = html.split('\n');
      let inTable = false, tableRows = [];
      const out = [];
      for (const raw of lines) {
        const line = raw.trim();
        if (line.startsWith('|') && line.endsWith('|')) {
          if (!inTable) { inTable = true; tableRows = []; }
          if (!/^\|[\s\-:|]+\|$/.test(line)) tableRows.push(line);
        } else {
          if (inTable) { inTable = false; out.push(buildBooktabsTable(tableRows)); }
          out.push(raw);
        }
      }
      if (inTable) out.push(buildBooktabsTable(tableRows));
      html = out.join('\n');

      // Paragraphs
      html = html.split('\n\n').map(para => {
        para = para.trim();
        if (!para) return '';
        if (/^<(h\d|table|div)/.test(para)) return para;
        return `<p>${para.replace(/\n/g, '<br>')}</p>`;
      }).join('\n');

      html = html.replace(/%%%INLINE_MATH_(\d+)%%%/g, (_, i) => `$${inlineMath[i]}$`);
      html = html.replace(/%%%DISPLAY_MATH_(\d+)%%%/g, (_, i) => `$$${displayMath[i]}$$`);
      return html;
    }

    function buildBooktabsTable(rows) {
      if (!rows.length) return '';
      const cells = r => r.split('|').slice(1, -1).map(c => c.trim());
      let t = '<div class="my-2 overflow-x-auto"><table class="booktabs"><thead><tr>';
      cells(rows[0]).forEach(c => { t += `<th>${c}</th>`; });
      t += '</tr></thead><tbody>';
      for (let i = 1; i < rows.length; i++) {
        t += '<tr>';
        cells(rows[i]).forEach(c => { t += `<td>${c}</td>`; });
        t += '</tr>';
      }
      return t + '</tbody></table></div>';
    }

    // ── Preview ──
    function countWords(text) {
      const cjk = (text.match(/[一-鿿]/g) || []).length;
      const latin = (text.match(/[a-zA-Z0-9_\-]+/g) || []).length;
      return cjk + latin;
    }

    function renderLivePreview() {
      const editor = document.getElementById('markdown-editor');
      const preview = document.getElementById('publication-preview');
      const text = editor.value;
      document.getElementById('word-count-badge').innerText = `${countWords(text)} words`;
      preview.innerHTML = parseMarkdownToHTML(text);
      if (window.renderMathInElement) {
        renderMathInElement(preview, {
          delimiters: [
            { left: '$$', right: '$$', display: true },
            { left: '$', right: '$', display: false },
          ],
          throwOnError: false,
        });
      }
      if (currentPreviewMode === 'pdf') triggerLivePdfRender();
    }

    function switchPreviewMode(mode) {
      currentPreviewMode = mode;
      const active = 'px-2.5 py-0.5 rounded text-[11px] font-medium bg-white text-zinc-800 shadow-sm transition';
      const idle = 'px-2.5 py-0.5 rounded text-[11px] font-medium text-zinc-500 hover:text-zinc-800 transition';
      const btnWeb = document.getElementById('btn-mode-web');
      const btnPdf = document.getElementById('btn-mode-pdf');
      btnWeb.className = mode === 'web' ? active : idle;
      btnPdf.className = (mode === 'pdf' ? active : idle) + ' flex items-center gap-1';
      document.getElementById('publication-preview').classList.toggle('hidden', mode === 'pdf');
      document.getElementById('pdf-preview-container').classList.toggle('hidden', mode !== 'pdf');
      if (mode === 'pdf') triggerLivePdfRender(true); else renderLivePreview();
    }

    function triggerLivePdfRender(immediate = false) {
      if (livePdfDebounceTimer) clearTimeout(livePdfDebounceTimer);
      const run = () => {
        const text = document.getElementById('markdown-editor').value;
        const statusText = document.getElementById('pdf-status-text');
        const statusDot = document.getElementById('pdf-status-dot');
        const latencyTag = document.getElementById('pdf-latency-tag');
        statusText.innerText = 'Compiling…';
        fetch('/api/pdf/build', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ markdown_text: text, title: (SECTIONS[currentSection] && SECTIONS[currentSection].name) || 'SynapseForge Live PDF' }),
        })
          .then(r => r.json())
          .then(res => {
            if (res.ok && res.pdf_url) {
              document.getElementById('pdf-viewer-frame').src = res.pdf_url;
              latencyTag.innerText = `${res.compile_time_ms}ms`;
              latencyTag.classList.remove('hidden');
              statusText.innerText = 'PDF 实时就绪';
              statusDot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-500';
            } else {
              statusText.innerText = res.error ? '编译失败' : 'PDF 不可用';
              statusDot.className = 'w-1.5 h-1.5 rounded-full bg-red-500';
            }
          })
          .catch(() => {
            statusText.innerText = 'Daemon 未连接';
            statusDot.className = 'w-1.5 h-1.5 rounded-full bg-zinc-400';
          });
      };
      if (immediate) run(); else livePdfDebounceTimer = setTimeout(run, 400);
    }

    function downloadCurrentPdf() {
      window.open('/dist/live_preview.pdf', '_blank');
    }

    // ── Editor input: preview + autosave ──
    function onEditorInput() {
      if (currentSection && SECTIONS[currentSection]) {
        SECTIONS[currentSection].content = document.getElementById('markdown-editor').value;
      }
      renderLivePreview();
      saveLocalSession();
      scheduleDocSave();
    }

    function setSaveState(msg) {
      document.getElementById('save-state').innerText = msg;
    }

    function scheduleDocSave() {
      setSaveState('未保存的更改…');
      if (saveDebounceTimer) clearTimeout(saveDebounceTimer);
      saveDebounceTimer = setTimeout(saveCurrentSection, 900);
    }

    function saveCurrentSection() {
      if (!currentSection) return;
      const content = document.getElementById('markdown-editor').value;
      setSaveState('保存中…');
      fetch('/api/doc/save', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ section_id: currentSection, content }),
      })
        .then(r => r.json())
        .then(res => { setSaveState(res.ok ? '已保存' : '保存失败'); })
        .catch(() => { setSaveState('本地暂存(守护进程离线)'); });
    }

    function setupKeyboardShortcuts() {
      window.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 's') {
          e.preventDefault();
          if (saveDebounceTimer) clearTimeout(saveDebounceTimer);
          saveCurrentSection();
        }
      });
    }

    // ── Follow mode ──
    function toggleFollow(agentRole) {
      const badge = document.getElementById('follow-badge');
      followingTarget = followingTarget === agentRole ? null : agentRole;
      ['drafter', 'critic', 'harmonizer'].forEach(id => {
        const el = document.getElementById('avatar-' + id);
        if (el) el.classList.toggle('is-followed', followingTarget === id);
      });
      if (followingTarget) {
        badge.classList.remove('hidden'); badge.classList.add('flex');
        document.getElementById('follow-badge-text').innerText = `Following @${followingTarget.toUpperCase()}`;
        showToast(`跟随模式:正在同步 @${followingTarget.toUpperCase()} 的视口`);
        const preview = document.getElementById('publication-preview');
        preview.scrollTo({ top: preview.scrollHeight, behavior: 'smooth' });
      } else {
        badge.classList.add('hidden'); badge.classList.remove('flex');
        showToast('已退出跟随模式');
      }
    }

    // ── Agent simulation ──
    function triggerAgentDraft() {
      const editor = document.getElementById('markdown-editor');
      editor.value += '\n\n## 形式化一致性收敛定理\n\n设节点往返通信时延为 $\\tau_j$,系统全局状态收敛上界满足:\n\n$$\n\\mathbb{E}[\\tau_{\\text{sync}}] \\le \\frac{1}{\\mu - \\lambda} \\ln \\left( \\frac{|\\mathcal{V}|}{\\epsilon} \\right) + \\max_{j \\in \\mathcal{N}} \\{\\text{RTT}_j\\}\n$$\n';
      onEditorInput();
      const preview = document.getElementById('publication-preview');
      preview.scrollTo({ top: preview.scrollHeight, behavior: 'smooth' });
    }

    function handleSend() {
      const input = document.getElementById('agent-input');
      const text = input.value.trim();
      if (!text) return;
      const stream = document.getElementById('activity-stream');

      const userCard = document.createElement('div');
      userCard.className = 'space-y-1';
      const userMeta = document.createElement('div');
      userMeta.className = 'text-zinc-500 text-[10px]';
      userMeta.textContent = 'You · Just now';
      const userBody = document.createElement('div');
      userBody.className = 'p-2.5 rounded-lg raised border border-white/[0.04] text-zinc-300 leading-relaxed';
      userBody.textContent = text;
      userCard.appendChild(userMeta); userCard.appendChild(userBody);
      stream.appendChild(userCard);

      const agentCard = document.createElement('div');
      agentCard.className = 'space-y-1.5';
      agentCard.innerHTML = '<div class="text-purple-400 text-[10px] font-medium flex items-center gap-1.5">' +
        '<span class="w-1.5 h-1.5 rounded-full bg-purple-400"></span><span>Drafter Agent</span></div>' +
        '<div class="p-2.5 rounded-lg bg-purple-500/[0.07] border border-purple-500/20 text-zinc-300 leading-relaxed">' +
        'Incorporating request into current section AST. Math equations updated.</div>';
      stream.appendChild(agentCard);
      stream.scrollTop = stream.scrollHeight;
      triggerAgentDraft();
      input.value = '';
    }

    // ── Session persistence & watchdog ──
    const STORAGE_KEY = 'synapseforge_session_state';

    function saveLocalSession() {
      try {
        const data = {
          room_id: 'room-global-sync',
          room_name: 'Decentralized Swarm Room #1',
          currentSection,
          draftContent: document.getElementById('markdown-editor').value,
          timestamp: Date.now(),
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        if (navigator.onLine) {
          fetch('/api/session', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
          }).catch(() => {});
        }
      } catch (e) {}
    }

    function restoreLocalSession() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return false;
        const session = JSON.parse(raw);
        if (session.currentSection && SECTIONS[session.currentSection]) {
          switchSection(session.currentSection);
          if (session.draftContent) {
            document.getElementById('markdown-editor').value = session.draftContent;
            SECTIONS[session.currentSection].content = session.draftContent;
            renderLivePreview();
          }
          showToast('已恢复至断线前的房间与文档状态');
          return true;
        }
      } catch (e) {}
      return false;
    }

    function setupNetworkWatchdog() {
      window.addEventListener('offline', () => setNetworkBadge('离线:已自动暂存至本地', true));
      window.addEventListener('online', () => setNetworkBadge('Mesh Connected', false));
    }

    function setNetworkBadge(msg, warn) {
      const badge = document.getElementById('network-badge');
      document.getElementById('network-badge-text').innerText = msg;
      badge.className = warn
        ? 'flex items-center gap-1.5 px-2 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px] font-medium'
        : 'flex items-center gap-1.5 px-2 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-medium';
    }

    // ── Misc ──
    let toastTimer = null;
    function showToast(msg, warn = false) {
      const toast = document.getElementById('toast');
      toast.innerText = msg;
      toast.style.borderColor = warn ? 'rgba(245,158,11,.4)' : 'rgba(255,255,255,.08)';
      toast.classList.add('show');
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
    }

    window.addEventListener('DOMContentLoaded', () => setTimeout(boot, 150));
  </script>
</body>
</html>
"""

full_html = html_template.replace("__SECTIONS_JSON__", sections_json)

out = Path("synapseforge/ui/index.html")
out.write_text(full_html, encoding="utf-8")
print(f"Generated {out} with {len(sections)} embedded sections: SUCCESS")
