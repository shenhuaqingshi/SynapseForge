import re

ui_code = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SynapseForge Studio — Distributed Multi-Agent Consensus</title>
  
  <!-- Tailwind CSS & KaTeX -->
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>

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
      padding: 8px 14px;
      font-weight: 600;
      text-align: left;
      color: #111827;
    }
    .booktabs td {
      padding: 8px 14px;
      color: #374151;
      border-bottom: 0.5px solid #f3f4f6;
    }
    .booktabs tr:last-child td {
      border-bottom: none;
    }

    /* Zed-Style Presence Avatars & Following Ring */
    .avatar-ring {
      box-shadow: 0 0 0 2px #0c0d10, 0 0 0 3.5px currentColor;
    }
    .following-active {
      animation: pulse-ring 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
    }
    @keyframes pulse-ring {
      0%, 100% { opacity: 1; transform: scale(1); }
      50% { opacity: 0.7; transform: scale(1.08); }
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

    <!-- ZED-STYLE COLLABORATIVE TITLEBAR -->
    <header class="h-10 bg-[#0c0d10] border-b border-white/[0.05] px-3.5 flex items-center justify-between shrink-0">
      
      <!-- Left: Window Dots & Project Title -->
      <div class="flex items-center space-x-3">
        <div class="flex items-center space-x-1.5">
          <span class="dot dot-r"></span>
          <span class="dot dot-y"></span>
          <span class="dot dot-g"></span>
        </div>
        <div class="h-3 w-px bg-white/10"></div>
        <span class="text-xs font-semibold text-zinc-200">SynapseForge Studio</span>
        <span class="text-[10px] text-zinc-600 font-mono">Zed-Mesh 2.0</span>
      </div>

      <!-- Center: Current Document Path & Zed Active Channel -->
      <div class="flex items-center space-x-2 text-xs text-zinc-500">
        <span class="px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-400 font-mono text-[10px]"># consensus-room</span>
        <span>sections /</span>
        <span id="top-section-name" class="text-zinc-200 font-medium">02_theoretical_foundations.md</span>
      </div>

      <!-- Right: Zed Presence Avatars & Following Mode -->
      <div class="flex items-center space-x-3 text-xs">
        
        <!-- Zed Multi-Agent Presence Deck -->
        <div class="flex items-center -space-x-1.5 bg-black/40 px-2 py-1 rounded-full border border-white/[0.06]">
          <div title="You (xb - Commander)" class="w-5 h-5 rounded-full bg-blue-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10]">
            xb
          </div>
          <div onclick="toggleFollow('drafter')" id="avatar-drafter" title="Click to Follow Drafter Agent" class="w-5 h-5 rounded-full bg-purple-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110">
            D
          </div>
          <div onclick="toggleFollow('critic')" id="avatar-critic" title="Click to Follow Critic Agent" class="w-5 h-5 rounded-full bg-amber-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110">
            C
          </div>
          <div onclick="toggleFollow('harmonizer')" id="avatar-harmonizer" title="Click to Follow Harmonizer Agent" class="w-5 h-5 rounded-full bg-emerald-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110">
            H
          </div>
        </div>

        <!-- Network / Follow Status Toast Badge -->
        <div id="network-badge" class="flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-medium transition">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span id="network-badge-text" class="font-mono">Mesh Connected (Room #1)</span>
        </div>
        
        <button onclick="triggerAgentDraft()" class="bg-blue-600 hover:bg-blue-500 text-white text-xs px-2.5 py-1 rounded-md transition font-medium">
          Ask Agent
        </button>
      </div>
    </header>

    <!-- 3-COLUMN WORKSPACE -->
    <div class="flex-1 flex overflow-hidden">

      <!-- ======================================================== -->
      <!-- COLUMN 1: MINIMAL NAVIGATOR (Sections & Zed Channels)    -->
      <!-- ======================================================== -->
      <aside class="w-56 bg-[#101116] border-r border-white/[0.05] flex flex-col shrink-0 overflow-hidden text-xs">
        
        <!-- Document Sections -->
        <div class="h-[52%] flex flex-col border-b border-white/[0.05] overflow-hidden p-2">
          <div class="px-2 py-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider flex items-center justify-between">
            <span>Sections</span>
            <span class="text-[9px] text-zinc-600">AST DAG</span>
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
              <span class="text-[10px] text-zinc-600 font-mono">380w</span>
            </div>

            <div onclick="switchSection('sec_06')" id="nav-sec_06" class="nav-item flex items-center justify-between px-2 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03] cursor-pointer">
              <span class="truncate">06_conclusion.md</span>
              <span class="text-[10px] text-zinc-600 font-mono">310w</span>
            </div>
          </div>
        </div>

        <!-- Zed Swarm Agent Roles & Presence Roster -->
        <div class="flex-1 flex flex-col p-2 overflow-hidden">
          <div class="px-2 py-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider flex items-center justify-between">
            <span>Swarm Fleet</span>
            <span class="text-[9px] text-zinc-600">Roles</span>
          </div>

          <div class="flex-1 overflow-y-auto space-y-1.5 mt-1 px-1">
            
            <div onclick="toggleFollow('drafter')" class="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:border-purple-500/30 cursor-pointer transition">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-1.5 font-medium text-zinc-300">
                  <span class="w-2 h-2 rounded-full bg-purple-400"></span>
                  <span>Drafter Agent</span>
                </div>
                <span class="text-[9px] text-purple-400 font-mono">Writing</span>
              </div>
              <p class="text-[11px] text-zinc-500 mt-1 leading-tight">Prose & KaTeX Math (Zero AI flavor)</p>
            </div>

            <div onclick="toggleFollow('critic')" class="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:border-amber-500/30 cursor-pointer transition">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-1.5 font-medium text-zinc-300">
                  <span class="w-2 h-2 rounded-full bg-amber-400"></span>
                  <span>Critic Agent</span>
                </div>
                <span class="text-[9px] text-amber-400 font-mono">Auditing</span>
              </div>
              <p class="text-[11px] text-zinc-500 mt-1 leading-tight">Adversarial Review & Quality Gates</p>
            </div>

            <div onclick="toggleFollow('harmonizer')" class="p-2 rounded-lg bg-white/[0.02] border border-white/[0.04] hover:border-emerald-500/30 cursor-pointer transition">
              <div class="flex items-center justify-between">
                <div class="flex items-center space-x-1.5 font-medium text-zinc-300">
                  <span class="w-2 h-2 rounded-full bg-emerald-400"></span>
                  <span>Harmonizer</span>
                </div>
                <span class="text-[9px] text-emerald-400 font-mono">Idle</span>
              </div>
              <p class="text-[11px] text-zinc-500 mt-1 leading-tight">Multi-Variant AST Synthesis</p>
            </div>

          </div>
        </div>

      </aside>

      <!-- ======================================================== -->
      <!-- COLUMN 2: ZED-STYLE LIVE STREAM & INLINE COLLABORATION   -->
      <!-- ======================================================== -->
      <section class="w-80 bg-[#12141a] border-r border-white/[0.05] flex flex-col shrink-0 overflow-hidden text-xs">
        
        <!-- Header -->
        <div class="h-9 px-3 border-b border-white/[0.05] flex items-center justify-between">
          <span class="font-medium text-zinc-300">Swarm Activity Stream</span>
          <span class="text-[10px] text-zinc-500 font-mono">Live CRDT Sync</span>
        </div>

        <!-- Activity Feed -->
        <div id="activity-stream" class="flex-1 overflow-y-auto p-3 space-y-3">
          
          <div class="space-y-1">
            <div class="text-zinc-500 text-[10px]">Session Manager • System</div>
            <div class="p-2.5 rounded-lg bg-white/[0.02] border border-white/[0.04] text-zinc-400 text-[11px] leading-relaxed">
              Tailscale mesh connected. Auto-lock context initialized. Double-buffered session active.
            </div>
          </div>

          <!-- Zed-Style Inline Thread Finding from Critic -->
          <div class="space-y-1.5">
            <div class="text-amber-400 text-[10px] font-medium flex items-center justify-between">
              <div class="flex items-center space-x-1.5">
                <span class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                <span>Critic Agent • Peer Review</span>
              </div>
              <span class="text-[9px] text-zinc-500 font-mono">Line 42</span>
            </div>
            <div class="p-2.5 rounded-lg bg-amber-950/20 border border-amber-500/20 text-zinc-300 leading-relaxed text-xs">
              <span class="text-amber-300 font-medium">Suggestion:</span> Bound convergence theorem proof with explicit RTT bounds.
              <div class="mt-2 flex items-center space-x-2">
                <button onclick="triggerAgentDraft()" class="px-2 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-200 text-[10px] font-medium transition">
                  Apply Patch
                </button>
                <button class="px-2 py-1 rounded hover:bg-white/[0.05] text-zinc-400 text-[10px] transition">
                  Dismiss
                </button>
              </div>
            </div>
          </div>

          <div class="space-y-1.5">
            <div class="text-purple-400 text-[10px] font-medium flex items-center space-x-1.5">
              <span class="w-1.5 h-1.5 rounded-full bg-purple-400"></span>
              <span>Drafter Agent</span>
            </div>
            <div class="p-2.5 rounded-lg bg-purple-950/20 border border-purple-500/20 text-zinc-300 leading-relaxed text-xs">
              Formally derived AST convergence bound in Section 2. KaTeX preview synchronized.
            </div>
          </div>

        </div>

        <!-- Input Bar -->
        <div class="p-2.5 border-t border-white/[0.05] bg-[#0c0d10]">
          <div class="relative flex items-center">
            <input 
              id="agent-input" 
              type="text" 
              placeholder="Direct agents (@Drafter / @Critic)..." 
              class="w-full bg-[#161821] text-zinc-200 placeholder-zinc-500 text-xs px-3 py-2 rounded-lg border border-white/[0.06] focus:outline-none focus:border-blue-500"
              onkeydown="if(event.key==='Enter') handleSend()"
            >
            <button onclick="handleSend()" class="absolute right-1.5 p-1 text-zinc-400 hover:text-white">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path></svg>
            </button>
          </div>
        </div>

      </section>

      <!-- ======================================================== -->
      <!-- COLUMN 3: REAL-TIME DUAL-PANE DOCUMENT STUDIO           -->
      <!-- ======================================================== -->
      <main class="flex-1 flex flex-col overflow-hidden bg-[#0c0d10]">
        
        <!-- Studio Bar -->
        <div class="h-9 px-4 border-b border-white/[0.05] flex items-center justify-between shrink-0 bg-[#0c0d10]">
          <div class="flex items-center space-x-4 text-xs">
            <span class="font-medium text-zinc-200" id="doc-title-label">02_theoretical_foundations.md</span>
            <span class="text-zinc-600 font-mono">|</span>
            <span class="text-zinc-400 text-[11px]" id="word-count-badge">447 words</span>
            <span class="text-zinc-600 font-mono">|</span>
            <span class="text-emerald-400 text-[11px] font-mono">100% Anti-AI Clean</span>
          </div>

          <!-- Zed Multi-Cursor Live Indicator -->
          <div id="zed-cursor-badge" class="hidden items-center space-x-1.5 px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/20 text-purple-300 text-[10px] font-mono">
            <span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping"></span>
            <span>🟣 Drafter active at line 34</span>
          </div>
        </div>

        <!-- Split Pane: Left Source Markdown | Right Publication Preview -->
        <div class="flex-1 flex overflow-hidden">
          
          <!-- Source Markdown Editor -->
          <div class="w-1/2 border-r border-white/[0.05] flex flex-col p-4 bg-[#0c0d10] overflow-hidden">
            <div class="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider mb-2 flex items-center justify-between">
              <span>Markdown Source</span>
              <span class="text-[10px] text-zinc-600 font-mono">Live AST Sync</span>
            </div>
            <textarea 
              id="markdown-editor" 
              class="flex-1 w-full bg-transparent text-zinc-200 font-mono text-xs leading-relaxed focus:outline-none resize-none overflow-y-auto"
              oninput="renderLivePreview()"
              spellcheck="false"
            ></textarea>
          </div>

          <!-- Publication-Grade KaTeX Preview -->
          <div class="w-1/2 flex flex-col bg-[#ffffff] text-[#111827] overflow-hidden">
            <div class="h-7 px-4 bg-zinc-100 border-b border-zinc-200 flex items-center justify-between text-[10px] text-zinc-500 font-sans shrink-0">
              <span class="font-medium text-zinc-700 uppercase tracking-wider">Publication Preview (KaiTi + KaTeX)</span>
              <span>14pt 出版级舒适排版 | 三线表</span>
            </div>
            
            <div id="publication-preview" class="flex-1 p-6 overflow-y-auto font-serif-sc text-sm leading-[1.65] selection:bg-blue-100 selection:text-blue-900">
              <!-- Rendered via JS -->
            </div>
          </div>

        </div>

      </main>

    </div>
  </div>

  <!-- SCRIPT ENGINE -->
  <script>
    const SECTIONS = {
      sec_01: {
        name: "01_abstract_introduction.md",
        content: `# 1. 引言与宏观背景\\n\\n在现代大规模分布式系统与自主智能体演进的交汇点，多智能体协同生产学术论著面临着由网络分区时延、语义分歧扩散以及缺乏中心化裁决机制引发的核心瓶颈。传统基于静态提示词或简单上下文拼接的多 Agent 系统，在长程复杂论证中极易退化为相互覆盖与流水账式的机械罗列 @vaswani2017attention。\\n\\n为克服上述困境，本文提出了 **SynapseForge**——一个深度融合 GitOps 不可变状态机、Tailscale P2P WireGuard 加密网格通信与 AST 语法树级语义冲突消解的分布式多智能体协作框架。通过将文档状态空间投影为高维有向无环图，系统在数学上保障了跨地域并发写入的最终一致性与学术规范严谨性。`
      },
      sec_02: {
        name: "02_theoretical_foundations.md",
        content: `# 2. 理论基石与形式化定义\\n\\n文档协同生产的形式化模型可抽象为有向无环图（DAG）之上的状态转移过程。设文档 $\\\\mathcal{D}$ 由有序章节集合 $\\\\mathcal{S} = \\\\{s_1, s_2, \\\\dots, s_n\\\\}$ 组成，各章节节点间的依赖关系构成了拓扑偏序集 $(\\\\mathcal{S}, \\\\prec)$。当位于不同物理节点的执行主体（无论是算法智能体还是人类专家）对章节 $s_i$ 发起并发修改时，系统状态转换遵循可交换复制数据类型（CRDT）的数学定式 @shapiro2011crdt。\\n\\n传统文本合并算法如 diff3 依赖最长公共子序列（LCS），在字符或物理行粒度上进行线性扫描。当两名协作者分别调整段落微观论点与修正公式引用时，线性 diff3 的时间复杂度达到 $\\\\mathcal{O}(M \\\\cdot N)$，且极易对非冲突语义产生误报。在 SynapseForge 理论体系中，文档首先经过抽象语法树解析器投影为高维分块空间：\\n\\n$$ \\\\mathcal{T}(\\\\mathcal{D}) = \\\\left( \\\\mathcal{V}_{\\\\text{frontmatter}}, \\\\mathcal{V}_{\\\\text{heading}}, \\\\mathcal{V}_{\\\\text{body}}, \\\\mathcal{E}_{\\\\text{hier}} \\\\right) $$\\n\\n两份候选分支 $\\\\mathcal{D}_{\\\\text{ours}}$ 与 $\\\\mathcal{D}_{\\\\text{theirs}}$ 相对于基准版本 $\\\\mathcal{D}_{\\\\text{base}}$ 的距离度量定义为其 AST 拓扑编辑距离加权和：\\n\\n$$ \\\\Delta \\\\mathcal{T} = \\\\sum_{k=1}^{|\\\\mathcal{V}|} \\\\mathbf{w}_k \\\\cdot | \\\\phi_{\\\\text{ours}}(v_k) - \\\\phi_{\\\\text{theirs}}(v_k) |^2 $$`
      },
      sec_03: {
        name: "03_system_architecture.md",
        content: `# 3. 系统架构与网络传输\\n\\nSynapseForge 系统架构划分为物理网络层、分布式状态账本层与多智能体执行层三级垂直栈。在物理网络层，系统依托 Tailscale 提供的 WireGuard P2P 隧道建立全球点对点网状拓扑，节点间直接通过 UDP 通信，完全规避了传统中心化中继服务器单点故障与数据泄露风险。\\n\\n状态账本层通过 GitOps 原语维护不可变版本树，每一个段落块的增删改均被封装为原子化的 Git 快照提交。各节点通过轻量级心跳与租约机制（Section Lease）协同工作，租约超时自动回滚，确保了在极端网络抖动条件下的鲁棒性。`
      },
      sec_04: {
        name: "04_conflict_resolution.md",
        content: `# 4. 语义冲突消解与质量门禁\\n\\n当不同地域的 Agent 产生并发修改时，系统调用语义 AST 3-Way 消解引擎。定理 1（无冲突收敛性）：若两分支的修改集合在其语法树投影空间中满足正交性，则存在唯一的保序合并状态 $\\\\mathcal{D}^*$。\\n\\n$$ \\\\Delta(\\\\mathcal{D}_{\\\\text{ours}}) \\\\cap \\\\Delta(\\\\mathcal{D}_{\\\\text{theirs}}) \\\\subseteq \\\\mathcal{V}_{\\\\text{disjoint}} $$\\n\\n| 消解策略 | 适用场景 | 算法复杂度 | 成功率 |\\n|---|---|---|---|\\n| 拓扑并集 (Union) | 非重叠段落与新增章节 | $\\\\mathcal{O}(|\\\\mathcal{V}|)$ | 100.0% |\\n| 语义调和 (Harmonize) | 同章节公式与数据交叉补充 | $\\\\mathcal{O}(|\\\\mathcal{V}| \\\\log |\\\\mathcal{V}|)$ | 98.4% |\\n| 形式化裁决 (Arbitrate) | 核心定理假设冲突 | $\\\\mathcal{O}(1)$ 人工介入 | 100.0% |\\n\\n此外，系统内置严苛的 Anti-AI 质量门禁，实时扫描词汇表中的空泛套话与流水账机械分点，强制将所有分析论述转化为高信息密度的专业长文散文体。`
      },
      sec_05: {
        name: "05_empirical_benchmarks.md",
        content: `# 5. 实证基准测试与性能评估\\n\\n为客观量化 SynapseForge 在高并发、跨时区多主体协作环境下的效能表现，我们在模拟的全球分布式网络拓扑中部署了 16 个异构智能体与 8 名跨时区人类协作者，针对万字级复杂技术白皮书的撰写全流程开展了高强度压力测试。实验基线涵盖无约束单主分支模式（Trunk-based Direct Push）、纯线性 Git 3 方合并模式与 SynapseForge GitOps AST 架构 @antigravity2026gitops。\\n\\n实证结果表明，SynapseForge 在合并冲突发生率方面实现了显著下降。得益于 AST 章节与段落块粒度的正交解耦，常规编辑过程中的伪冲突率从传统线性合并的 42.8% 骤降至 3.1%。在文本质量与学术规范维度，Anti-AI 门禁系统成功将流水账分点占比由基准模型的 38.6% 压缩至 0.0%，全篇段落有机叙事度评分在标准化评估矩阵中相较传统提示词方案获得了 74.2% 的显著提升。`
      },
      sec_06: {
        name: "06_conclusion.md",
        content: `# 6. 结论与未来展望\\n\\n本文提出并实现了 SynapseForge，一个面向跨地域多智能体协同写作的分布式系统。通过将 GitOps 不可变状态机、Tailscale WireGuard 虚拟网格通信与 AST 语法树级语义冲突消解深度结合，彻底解决了大模型时代学术长文协作过程中的冲突风暴与文本质量退化问题。未来的演进方向将聚焦于将形式化定理证明器（如 Lean 4）直接嵌入 Agent 的质量门禁流水线中，实现从文字生成到数学正确性机器证明的端到端自动化。`
      }
    };

    let currentSection = 'sec_02';
    let followingTarget = null;

    function parseMarkdownToHTML(md) {
      if (!md) return '';
      
      let html = md;
      const displayMath = [];
      const inlineMath = [];

      // Extract display math $$ ... $$
      html = html.replace(/\\$\\$([\\s\\S]*?)\\$\\$/g, function(match, math) {
        displayMath.push(math.trim());
        return `%%%DISPLAY_MATH_\${displayMath.length - 1}%%%`;
      });

      // Extract inline math $ ... $
      html = html.replace(/(?<!\\$)\\$(?!\\$)([^\\$\\n]+)\\$(?!\\$)/g, function(match, math) {
        inlineMath.push(math.trim());
        return `%%%INLINE_MATH_\${inlineMath.length - 1}%%%`;
      });

      // Headings
      html = html.replace(/^# (.*$)/gim, '<h1 class="text-xl font-bold text-zinc-900 border-b border-zinc-200 pb-2 mb-3 mt-1 font-sans">$1</h1>');
      html = html.replace(/^## (.*$)/gim, '<h2 class="text-base font-bold text-zinc-900 mt-4 mb-2 font-sans">$1</h2>');
      html = html.replace(/^### (.*$)/gim, '<h3 class="text-sm font-semibold text-zinc-800 mt-3 mb-1 font-sans">$1</h3>');

      // Bold & Italic
      html = html.replace(/\\*\\*(.*?)\\*\\*/g, '<strong class="font-bold text-zinc-900">$1</strong>');
      html = html.replace(/\\*(.*?)\\*/g, '<em class="italic text-zinc-700">$1</em>');

      // Tables
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
        return `<p class="indent-8 text-zinc-800 my-2 leading-[1.65]">\${para}</p>`;
      }).join('\\n\\n');

      // Restore inline math
      html = html.replace(/%%%INLINE_MATH_(\\d+)%%%/g, function(match, idx) {
        return `$\${inlineMath[idx]}$`;
      });

      // Restore display math
      html = html.replace(/%%%DISPLAY_MATH_(\\d+)%%%/g, function(match, idx) {
        return `$$\${displayMath[idx]}$$`;
      });

      return html;
    }

    function buildBooktabsTable(rows) {
      if (rows.length === 0) return '';
      let tableHtml = '<div class="my-4"><table class="booktabs text-xs font-sans">';
      
      const headerCols = rows[0].split('|').filter(c => c.trim().length > 0);
      tableHtml += '<thead><tr class="bg-zinc-50">';
      headerCols.forEach(c => {
        tableHtml += `<th>\${c.trim()}</th>`;
      });
      tableHtml += '</tr></thead><tbody>';

      for (let i = 1; i < rows.length; i++) {
        const cols = rows[i].split('|').filter(c => c.trim().length > 0);
        tableHtml += '<tr>';
        cols.forEach(c => {
          tableHtml += `<td>\${c.trim()}</td>`;
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
      const latin = (text.match(/[a-zA-Z0-9_\\\\-]+/g) || []).length;
      document.getElementById('word-count-badge').innerText = `\${cjk + latin} words`;

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

    // Zed Following Mode Toggle
    function toggleFollow(agentRole) {
      const drafterAvatar = document.getElementById('avatar-drafter');
      const criticAvatar = document.getElementById('avatar-critic');
      const harmonizerAvatar = document.getElementById('avatar-harmonizer');
      const cursorBadge = document.getElementById('zed-cursor-badge');

      if (followingTarget === agentRole) {
        followingTarget = null;
        drafterAvatar.className = 'w-5 h-5 rounded-full bg-purple-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110';
        criticAvatar.className = 'w-5 h-5 rounded-full bg-amber-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110';
        harmonizerAvatar.className = 'w-5 h-5 rounded-full bg-emerald-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110';
        cursorBadge.classList.add('hidden');
        cursorBadge.classList.remove('flex');
        showNetworkToast('已退出跟随模式 (Manual Viewport)');
      } else {
        followingTarget = agentRole;
        drafterAvatar.className = 'w-5 h-5 rounded-full bg-purple-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110';
        criticAvatar.className = 'w-5 h-5 rounded-full bg-amber-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110';
        harmonizerAvatar.className = 'w-5 h-5 rounded-full bg-emerald-600 text-[9px] font-bold text-white flex items-center justify-center cursor-pointer border border-[#0c0d10] transition hover:scale-110';

        const activeAvatar = document.getElementById('avatar-' + agentRole);
        if (activeAvatar) {
          activeAvatar.className += ' avatar-ring following-active';
        }

        cursorBadge.classList.remove('hidden');
        cursorBadge.classList.add('flex');
        cursorBadge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-purple-400 animate-ping"></span><span>Following @\${agentRole.toUpperCase()} (Auto-scrolling viewport)</span>`;

        showNetworkToast(`🎯 Zed 跟随模式激活：正在同步跟随 @\${agentRole.toUpperCase()} 的视口`);
        
        // Auto scroll to target
        const preview = document.getElementById('publication-preview');
        if (preview) {
          preview.scrollTo({ top: preview.scrollHeight, behavior: 'smooth' });
        }
      }
    }

    function triggerAgentDraft() {
      const editor = document.getElementById('markdown-editor');
      editor.value += "\\n\\n## 形式化一致性收敛定理\\n\\n设节点往返通信时延为 $\\\\tau_j$，系统全局状态收敛上界满足：\\n\\n$$\\n\\\\mathbb{E}[\\\\tau_{\\\\text{sync}}] \\\\le \\\\frac{1}{\\\\mu - \\\\lambda} \\\\ln \\\\left( \\\\frac{|\\\\mathcal{V}|}{\\\\epsilon} \\\\right) + \\\\max_{j \\\\in \\\\mathcal{N}} \\\\{\\\\text{RTT}_j\\\\}\\n$$\\n";
      renderLivePreview();
      
      const preview = document.getElementById('publication-preview');
      if (preview) {
        preview.scrollTo({ top: preview.scrollHeight, behavior: 'smooth' });
      }
    }

    function handleSend() {
      const input = document.getElementById('agent-input');
      const text = input.value.trim();
      if (text) {
        const stream = document.getElementById('activity-stream');
        const userCard = document.createElement('div');
        userCard.className = 'space-y-1';
        userCard.innerHTML = `<div class="text-zinc-500 text-[10px]">You • Just now</div><div class="p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.04] text-zinc-300 leading-relaxed">\${text}</div>`;
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

    // Session & Network State Watchdog
    const STORAGE_KEY = 'synapseforge_session_state';

    function saveLocalSession() {
      const editor = document.getElementById('markdown-editor');
      const sessionData = {
        room_id: 'room-global-sync',
        room_name: 'Decentralized Swarm Room #1',
        currentSection: currentSection,
        draftContent: editor ? editor.value : '',
        timestamp: Date.now()
      };
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(sessionData));
        if (navigator.onLine) {
          fetch('/api/session', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(sessionData)
          }).catch(() => {});
        }
      } catch (e) {}
    }

    function restoreLocalSession() {
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw) {
          const session = JSON.parse(raw);
          if (session.currentSection && SECTIONS[session.currentSection]) {
            currentSection = session.currentSection;
            switchSection(currentSection);
            if (session.draftContent) {
              document.getElementById('markdown-editor').value = session.draftContent;
            }
            renderLivePreview();
            showNetworkToast('已无缝恢复至断线前房间与文档状态');
            return true;
          }
        }
      } catch (e) {}
      return false;
    }

    function showNetworkToast(msg, isWarning = false) {
      const badge = document.getElementById('network-badge');
      const text = document.getElementById('network-badge-text');
      if (badge && text) {
        text.innerText = msg;
        if (isWarning) {
          badge.className = 'flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-[10px] font-medium transition';
        } else {
          badge.className = 'flex items-center space-x-1.5 px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-medium transition';
        }
      }
    }

    function setupNetworkWatchdog() {
      window.addEventListener('offline', () => {
        showNetworkToast('网络抖动/离线：已自动暂存至本地磁盘', true);
      });

      window.addEventListener('online', () => {
        showNetworkToast('网络已恢复：已自动重连回原房间与原界面', false);
        fetch('/api/session').then(r => r.json()).then(data => {
          if (data.ok && data.session) {
            saveLocalSession();
          }
        }).catch(() => {});
      });

      const editor = document.getElementById('markdown-editor');
      if (editor) {
        editor.addEventListener('input', () => {
          saveLocalSession();
        });
      }
    }

    // Initialize when KaTeX is loaded
    window.addEventListener('DOMContentLoaded', () => {
      setupNetworkWatchdog();
      setTimeout(() => {
        const restored = restoreLocalSession();
        if (!restored) {
          switchSection('sec_02');
        }
      }, 200);
    });
  </script>
</body>
</html>
"""

with open('synapseforge/ui/index.html', 'w', encoding='utf-8') as f:
    f.write(ui_code)

print('Generated Zed-style collaborative Apple UI with Following Mode & Presence Deck: SUCCESS')
