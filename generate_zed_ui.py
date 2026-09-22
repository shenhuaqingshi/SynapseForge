"""SynapseForge Studio UI generator — monochrome minimal edition.

Reads the real manuscript sections from ./sections/ and emits a self-contained
synapseforge/ui/index.html. At runtime the page prefers the live daemon APIs
(/api/sections, /api/doc/save, /api/prompts, /api/pdf/build) and gracefully
falls back to the embedded snapshot when opened as a static file.

Design language: strictly black & white, KaiTi (Chinese) + Times New Roman
(Western), publication-grade typography, minimal chrome.
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
    :root {
      --ink: #000;
      --paper: #fff;
      --hairline: rgba(0, 0, 0, 0.14);
      --wash: rgba(0, 0, 0, 0.045);
      --ink-60: rgba(0, 0, 0, 0.6);
      --ink-40: rgba(0, 0, 0, 0.4);
    }

    * { box-sizing: border-box; }

    body {
      font-family: "Times New Roman", "KaiTi", "STKaiti", "Kaiti SC", "AR PL UKai CN", serif;
      background: var(--paper);
      color: var(--ink);
      -webkit-font-smoothing: antialiased;
      overflow: hidden;
    }

    .font-mono { font-family: "Times New Roman", "JetBrains Mono", Menlo, monospace; }

    .lbl {
      font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase;
      color: var(--ink-40); font-family: "Times New Roman", serif;
    }

    /* Buttons — outline or solid black, nothing else */
    .btn {
      display: inline-flex; align-items: center; gap: 6px;
      padding: 4px 12px; font-size: 12.5px; line-height: 1.5;
      color: var(--ink); background: var(--paper);
      border: 1px solid var(--ink); border-radius: 0;
      cursor: pointer; white-space: nowrap; transition: all .12s ease;
      font-family: inherit;
    }
    .btn:hover { background: var(--wash); }
    .btn-solid { background: var(--ink); color: var(--paper); }
    .btn-solid:hover { background: rgba(0,0,0,0.82); }

    /* Nav items */
    .nav-item {
      display: flex; align-items: baseline; justify-content: space-between; gap: 8px;
      padding: 6px 10px; cursor: pointer; font-size: 13px;
      color: var(--ink-60); transition: all .12s ease;
      border-left: 2px solid transparent;
    }
    .nav-item:hover { color: var(--ink); background: var(--wash); }
    .nav-item.is-active { color: var(--ink); border-left-color: var(--ink); background: var(--wash); }

    /* Prompt cards */
    .prompt-card {
      padding: 8px 10px; border: 1px solid var(--hairline); cursor: pointer;
      transition: all .12s ease; background: var(--paper);
    }
    .prompt-card:hover { border-color: var(--ink); }

    /* Presence */
    .avatar {
      width: 22px; height: 22px; border-radius: 50%;
      display: inline-flex; align-items: center; justify-content: center;
      font-size: 10px; color: var(--ink); background: var(--paper);
      border: 1px solid var(--ink); cursor: pointer; transition: all .12s ease;
      font-family: "Times New Roman", serif;
    }
    .avatar.is-followed { background: var(--ink); color: var(--paper); }

    /* Academic table — pure booktabs */
    .booktabs {
      width: 100%; border-collapse: collapse; margin: 1.4em 0; font-size: 13px;
      border-top: 1.6px solid var(--ink); border-bottom: 1.6px solid var(--ink);
    }
    .booktabs th { border-bottom: 1px solid var(--ink); padding: 7px 14px; font-weight: bold; text-align: left; }
    .booktabs td { padding: 7px 14px; }
    .booktabs tbody tr + tr td { border-top: 0.5px solid var(--hairline); }

    /* Preview typography — KaiTi body, Times headings */
    #publication-preview h1 {
      font-size: 21px; font-weight: bold; text-align: center;
      margin: 6px 0 18px; padding-bottom: 10px; border-bottom: 1px solid var(--ink);
    }
    #publication-preview h2 { font-size: 16px; font-weight: bold; margin: 22px 0 8px; }
    #publication-preview h3 { font-size: 14px; font-weight: bold; margin: 16px 0 6px; }
    #publication-preview p  { text-indent: 2em; margin: 8px 0; text-align: justify; }

    .field {
      width: 100%; background: var(--paper); color: var(--ink);
      border: 1px solid var(--hairline); border-radius: 0;
      padding: 7px 10px; font-size: 13px; font-family: inherit;
      transition: border-color .12s ease;
    }
    .field:focus { outline: none; border-color: var(--ink); }

    /* Toast — black bar */
    #toast {
      position: fixed; bottom: 24px; left: 50%; transform: translate(-50%, 6px);
      background: var(--ink); color: var(--paper);
      font-size: 12.5px; padding: 7px 16px; letter-spacing: 0.02em;
      opacity: 0; pointer-events: none; transition: all .22s ease; z-index: 60;
    }
    #toast.show { opacity: 1; transform: translate(-50%, 0); }

    /* Scrollbars — hairline */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.18); }
    ::-webkit-scrollbar-thumb:hover { background: rgba(0,0,0,0.35); }

    .divider { border-color: var(--hairline); }
  </style>
</head>
<body class="h-screen w-screen select-none bg-white">

  <div class="h-full flex flex-col">

    <!-- ═══════════ TITLE BAR ═══════════ -->
    <header class="h-11 border-b divider px-5 flex items-center justify-between shrink-0">
      <div class="flex items-baseline gap-3">
        <span class="text-[15px] font-bold tracking-wide">SynapseForge</span>
        <span class="lbl hidden sm:inline">Studio</span>
      </div>

      <div id="top-section-name" class="text-[13px] text-black/60 truncate max-w-[40%]">—</div>

      <div class="flex items-center gap-3">
        <div class="flex items-center gap-1.5" id="presence">
          <span class="avatar" style="cursor:default" title="You (Commander)">余</span>
          <span class="avatar" id="avatar-drafter" title="Follow Drafter" onclick="toggleFollow('drafter')">D</span>
          <span class="avatar" id="avatar-critic" title="Follow Critic" onclick="toggleFollow('critic')">C</span>
          <span class="avatar" id="avatar-harmonizer" title="Follow Harmonizer" onclick="toggleFollow('harmonizer')">H</span>
        </div>
        <span id="network-status" class="lbl">Mesh</span>
        <button class="btn" onclick="openPromptModal()">提示词</button>
        <button class="btn btn-solid" onclick="triggerAgentDraft()">Ask Agent</button>
      </div>
    </header>

    <!-- ═══════════ WORKSPACE ═══════════ -->
    <div class="flex-1 flex overflow-hidden">

      <!-- Column 1 · Navigator -->
      <aside class="w-52 border-r divider flex flex-col shrink-0 overflow-hidden">
        <div class="h-1/2 flex flex-col border-b divider overflow-hidden py-3">
          <div class="px-4 pb-2 lbl">目录 · Sections</div>
          <div id="section-nav" class="flex-1 overflow-y-auto"></div>
        </div>
        <div class="flex-1 flex flex-col py-3 overflow-hidden">
          <div class="px-4 pb-2 flex items-baseline justify-between">
            <span class="lbl">提示词 · Prompts</span>
            <button onclick="openPromptModal()" class="text-[11px] underline underline-offset-2 hover:opacity-60 transition">自定义</button>
          </div>
          <div id="prompt-cards" class="flex-1 overflow-y-auto space-y-2 px-3"></div>
        </div>
      </aside>

      <!-- Column 2 · Swarm stream -->
      <section class="w-72 border-r divider flex flex-col shrink-0 overflow-hidden">
        <div class="px-4 pt-3 pb-2 lbl">协作动态 · Activity</div>

        <div id="activity-stream" class="flex-1 overflow-y-auto px-4 pb-3 space-y-4">
          <div>
            <div class="lbl mb-1">System</div>
            <div class="text-[13px] leading-relaxed border divider p-2.5">
              Tailscale mesh 已连接,提示词预设自 <span class="font-mono">./prompts/</span> 载入。
            </div>
          </div>

          <div>
            <div class="lbl mb-1 flex items-baseline justify-between">
              <span>Critic Agent · 审校</span><span>Line 42</span>
            </div>
            <div class="text-[13px] leading-relaxed border divider p-2.5">
              建议:将收敛定理证明界定为显式 RTT 上界。
              <div class="mt-2 flex items-center gap-2">
                <button onclick="triggerAgentDraft()" class="btn" style="padding:2px 8px;font-size:11.5px">采纳</button>
                <button class="text-[11.5px] underline underline-offset-2 hover:opacity-60 transition">忽略</button>
              </div>
            </div>
          </div>

          <div>
            <div class="lbl mb-1">Drafter Agent</div>
            <div class="text-[13px] leading-relaxed border divider p-2.5">
              已应用 <span class="font-mono">prompts/drafter.md</span> 写作规则,KaTeX 预览同步完成。
            </div>
          </div>
        </div>

        <div class="p-3 border-t divider">
          <div class="relative flex items-center">
            <input id="agent-input" type="text" placeholder="向智能体下达指令…"
              class="field pr-8"
              onkeydown="if(event.key==='Enter') handleSend()">
            <button onclick="handleSend()" class="absolute right-2.5 hover:opacity-50 transition" aria-label="发送">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5 21 12l-7.5 7.5M21 12H3"/></svg>
            </button>
          </div>
        </div>
      </section>

      <!-- Column 3 · Document studio -->
      <main class="flex-1 flex flex-col overflow-hidden">
        <div class="h-10 px-5 border-b divider flex items-center justify-between shrink-0">
          <div class="flex items-baseline gap-3 min-w-0 text-[13px]">
            <span class="font-bold truncate" id="doc-title-label">—</span>
            <span class="text-black/40 shrink-0" id="word-count-badge">0 字</span>
            <span id="save-state" class="text-black/40 shrink-0 transition text-[12px]"></span>
          </div>
          <div id="follow-badge" class="hidden text-[11.5px] items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-black animate-ping"></span>
            <span id="follow-badge-text"></span>
          </div>
        </div>

        <div class="flex-1 flex overflow-hidden">
          <!-- Source editor -->
          <div class="w-1/2 border-r divider flex flex-col px-5 py-4 overflow-hidden">
            <div class="lbl pb-2 flex items-baseline justify-between">
              <span>Markdown 源稿</span><span style="text-transform:none;letter-spacing:0">Live Sync</span>
            </div>
            <textarea id="markdown-editor" spellcheck="false"
              class="flex-1 w-full bg-transparent font-mono text-[13px] leading-[1.8] focus:outline-none resize-none overflow-y-auto"
              oninput="onEditorInput()"></textarea>
          </div>

          <!-- Preview -->
          <div class="w-1/2 flex flex-col overflow-hidden">
            <div class="h-10 px-4 border-b divider flex items-center justify-between shrink-0">
              <div class="flex items-center gap-1 text-[12.5px]">
                <button id="btn-mode-web" onclick="switchPreviewMode('web')" class="px-2.5 py-1 border border-black font-bold">预览</button>
                <button id="btn-mode-pdf" onclick="switchPreviewMode('pdf')" class="px-2.5 py-1 border border-black/20 hover:border-black transition flex items-center gap-1.5">
                  PDF
                  <span id="pdf-latency-tag" class="text-[10px] font-mono hidden"></span>
                </button>
              </div>
              <div class="flex items-center gap-3 text-[12px]">
                <span id="pdf-status-text" class="text-black/40">Live Sync</span>
                <button onclick="downloadCurrentPdf()" class="underline underline-offset-2 hover:opacity-60 transition">导出 PDF</button>
              </div>
            </div>

            <div id="publication-preview" class="flex-1 px-10 py-8 overflow-y-auto text-[14px] leading-[1.85]"></div>

            <div id="pdf-preview-container" class="flex-1 hidden overflow-hidden border-t divider">
              <iframe id="pdf-viewer-frame" class="w-full h-full border-0 bg-white" title="PDF preview"></iframe>
            </div>
          </div>
        </div>
      </main>
    </div>
  </div>

  <!-- ═══════════ PROMPT PRESET MODAL ═══════════ -->
  <div id="prompt-modal" class="fixed inset-0 bg-black/40 z-50 hidden items-center justify-center p-4">
    <div class="bg-white border border-black w-full max-w-2xl flex flex-col overflow-hidden text-[13px]">
      <div class="h-11 px-5 border-b divider flex items-center justify-between">
        <span class="font-bold">自定义 Agent 提示词预设</span>
        <button onclick="closePromptModal()" class="hover:opacity-50 transition p-1" aria-label="关闭">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18 18 6M6 6l12 12"/></svg>
        </button>
      </div>

      <div class="p-6 space-y-5 overflow-y-auto max-h-[75vh]">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="lbl block mb-1.5">角色标识 Role ID</label>
            <input id="modal-role-id" type="text" placeholder="drafter / my_philosopher" class="field">
          </div>
          <div>
            <label class="lbl block mb-1.5">显示名称</label>
            <input id="modal-display-name" type="text" placeholder="学术起草专家" class="field">
          </div>
        </div>

        <div>
          <label class="lbl block mb-1.5">模型路由 Model</label>
          <select id="modal-model" class="field">
            <option value="deepseek-v3">DeepSeek-V3 · 学术长文叙事</option>
            <option value="deepseek-reasoner">DeepSeek-R1 · 深度逻辑推理与定理证明</option>
            <option value="gemini-2.0-flash">Gemini 2.0 Flash · 高速检索与代码生成</option>
            <option value="claude-3-7-sonnet">Claude 3.7 Sonnet · 结构审校与综合</option>
            <option value="ollama/qwen2.5:72b">Local Ollama / Qwen 2.5 · 离线私有化</option>
          </select>
        </div>

        <div>
          <div class="flex items-baseline justify-between mb-1.5">
            <label class="lbl">系统提示词 Markdown</label>
            <span class="text-[11px] text-black/40">保存至 prompts/ 目录,全节点同步生效</span>
          </div>
          <textarea id="modal-prompt-content" rows="10" spellcheck="false"
            placeholder="# Role: Custom Agent&#10;&#10;## Writing Guidelines&#10;1. Use formal tone…&#10;2. Enforce LaTeX formulas…"
            class="field font-mono resize-none leading-relaxed"></textarea>
        </div>
      </div>

      <div class="h-12 px-5 border-t divider flex items-center justify-end gap-2">
        <button onclick="closePromptModal()" class="btn">取消</button>
        <button onclick="saveUserCustomPrompt()" class="btn btn-solid">保存预设</button>
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

    const USER_PROMPT_PRESETS = {
      drafter:    { id: 'drafter',    name: 'Drafter · 学术起草专家',   model: 'deepseek-v3',       prompt: '# Role: Senior Academic Drafter\n\n## Writing Principles\n1. Zero AI clichés\n2. Dense narrative prose (150-300 words per paragraph)\n3. KaTeX equations & booktabs tables' },
      critic:     { id: 'critic',     name: 'Critic · 严苛审稿专家',    model: 'deepseek-reasoner', prompt: '# Role: Adversarial Peer Reviewer\n\n## Audit Checklist\n1. Flag hollow phrases\n2. Check bibliography references @citekey\n3. Verify math proof bounds' },
      harmonizer: { id: 'harmonizer', name: 'Harmonizer · 多方案调和官', model: 'deepseek-v3',       prompt: '# Role: Multi-Variant Harmonizer\n\n## Principles\n1. Reconcile tone differences\n2. Fuse mathematical and empirical variants\n3. Deduplicate bibliography keys' },
    };

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
        count.className = 'text-[10.5px] text-black/35 font-mono shrink-0';
        count.textContent = countWords(sec.content);
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
        const card = document.createElement('div');
        card.className = 'prompt-card';
        card.onclick = () => openPromptModal(p.id);
        const name = document.createElement('div');
        name.className = 'text-[12.5px] font-bold truncate';
        name.textContent = p.name;
        const model = document.createElement('div');
        model.className = 'text-[11px] text-black/40 font-mono truncate mt-0.5';
        model.textContent = p.model;
        card.appendChild(name); card.appendChild(model);
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
      if (!roleId) { showToast('请输入 Role ID'); return; }

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
      html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
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
      let t = '<table class="booktabs"><thead><tr>';
      cells(rows[0]).forEach(c => { t += `<th>${c}</th>`; });
      t += '</tr></thead><tbody>';
      for (let i = 1; i < rows.length; i++) {
        t += '<tr>';
        cells(rows[i]).forEach(c => { t += `<td>${c}</td>`; });
        t += '</tr>';
      }
      return t + '</tbody></table>';
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
      document.getElementById('word-count-badge').innerText = `${countWords(text)} 字`;
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
      const btnWeb = document.getElementById('btn-mode-web');
      const btnPdf = document.getElementById('btn-mode-pdf');
      const on = 'px-2.5 py-1 border border-black font-bold';
      const off = 'px-2.5 py-1 border border-black/20 hover:border-black transition';
      btnWeb.className = mode === 'web' ? on : off;
      btnPdf.className = (mode === 'pdf' ? on : off) + ' flex items-center gap-1.5';
      document.getElementById('publication-preview').classList.toggle('hidden', mode === 'pdf');
      document.getElementById('pdf-preview-container').classList.toggle('hidden', mode !== 'pdf');
      if (mode === 'pdf') triggerLivePdfRender(true); else renderLivePreview();
    }

    function triggerLivePdfRender(immediate = false) {
      if (livePdfDebounceTimer) clearTimeout(livePdfDebounceTimer);
      const run = () => {
        const text = document.getElementById('markdown-editor').value;
        const statusText = document.getElementById('pdf-status-text');
        const latencyTag = document.getElementById('pdf-latency-tag');
        statusText.innerText = '编译中…';
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
              statusText.innerText = 'PDF 就绪';
            } else {
              statusText.innerText = res.error ? '编译失败' : 'PDF 不可用';
            }
          })
          .catch(() => { statusText.innerText = '守护进程离线'; });
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
      setSaveState('未保存');
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
        .catch(() => { setSaveState('本地暂存'); });
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
        document.getElementById('follow-badge-text').innerText = `跟随 @${followingTarget.toUpperCase()}`;
        const preview = document.getElementById('publication-preview');
        preview.scrollTo({ top: preview.scrollHeight, behavior: 'smooth' });
      } else {
        badge.classList.add('hidden'); badge.classList.remove('flex');
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
      const userMeta = document.createElement('div');
      userMeta.className = 'lbl mb-1';
      userMeta.textContent = 'You';
      const userBody = document.createElement('div');
      userBody.className = 'text-[13px] leading-relaxed border divider p-2.5';
      userBody.textContent = text;
      userCard.appendChild(userMeta); userCard.appendChild(userBody);
      stream.appendChild(userCard);

      const agentCard = document.createElement('div');
      const agentMeta = document.createElement('div');
      agentMeta.className = 'lbl mb-1';
      agentMeta.textContent = 'Drafter Agent';
      const agentBody = document.createElement('div');
      agentBody.className = 'text-[13px] leading-relaxed border divider p-2.5';
      agentBody.textContent = '已将指令并入当前章节 AST,数学公式同步更新。';
      agentCard.appendChild(agentMeta); agentCard.appendChild(agentBody);
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
          return true;
        }
      } catch (e) {}
      return false;
    }

    function setupNetworkWatchdog() {
      const el = document.getElementById('network-status');
      window.addEventListener('offline', () => { el.innerText = '离线'; });
      window.addEventListener('online', () => { el.innerText = 'Mesh'; });
    }

    // ── Toast ──
    let toastTimer = null;
    function showToast(msg) {
      const toast = document.getElementById('toast');
      toast.innerText = msg;
      toast.classList.add('show');
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toast.classList.remove('show'), 2400);
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
