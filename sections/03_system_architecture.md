# 系统架构与 GitOps 状态机

SynapseForge 的工程内核将 GitHub 的原生基建深度转化为分布式智能体群体的可信协同计算平台。系统架构划分为三大解耦层次：拓扑调度层（Orchestrator Layer）、质量门禁层（Quality Gate Layer）与出版渲染层（Publication Synthesis Layer）。

拓扑调度层直接对接 GitHub Issues 与 Pull Requests。当人类提出特定章节的撰写需求时，调度器通过解析带有结构化前缀的任务指令，自动计算依赖拓扑并派生专用工作分支（如 `synapse/sec_03_architecture`）。此时，租约管理器（Lease Ledger）在持久化账本中向指定智能体授予限定时长的写入租约，避免多智能体无序争抢同一上下文资源。

质量门禁层是保障内容质量与学术纯粹性的核心防线。在 GitHub Actions 持续集成管线中，提交的文件必须通过去 AI 味检测器（Anti-AI Linter）、结构连贯性校验器（Coherence Linter）与学术排版规范检查器（Style Linter）的联合熔断机制。任何带有套路化转折词、空洞宣教用语或破坏学术长文有机叙事的流水账列表均会被 CI 阻断并自动追加行级修正建议。

| 架构分层 | 核心组件 | 依托 GitHub 原生资源 | 核心功能边界 |
|---|---|---|---|
| 拓扑调度层 | StateManager / IssueDispatcher | Issues, Branches, Webhooks | 任务 DAG 拆解、章节租约分发、跨时区派发 |
| 质量门禁层 | AntiAILinter / PRReviewBot | GitHub Actions, Pull Requests | 消除 AI 异味、形式化合并、事实核查与行级审查 |
| 出版渲染层 | PublicationPipeline | GitHub Pages, Releases | 编译矢量 PDF、生成响应式 Web、输出 Typst 源码 |

该架构赋予了跨地区团队高度异步的自治能力，所有状态流转与评审痕迹均透明固化在 Git 历史与评审对话树中，具备完备的可审计性与可复现性。
