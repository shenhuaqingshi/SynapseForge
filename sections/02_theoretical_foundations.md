# 理论基石与形式化建模

文档协同生产的形式化模型可抽象为有向无环图（DAG）之上的状态转移过程。设文档 $\mathcal{D}$ 由有序章节集合 $\mathcal{S} = \{s_1, s_2, \dots, s_n\}$ 组成，各章节节点间的依赖关系构成了拓扑偏序集 $(\mathcal{S}, \prec)$。当位于不同物理节点的执行主体（无论是算法智能体还是人类专家）对章节 $s_i$ 发起并发修改时，系统状态转换遵循可交换复制数据类型（CRDT）的数学定式 @shapiro2011crdt。

传统文本合并算法如 diff3 依赖最长公共子序列（LCS），在字符或物理行粒度上进行线性扫描。当两名协作者分别调整段落微观论点与修正公式引用时，线性 diff3 的时间复杂度达到 $\mathcal{O}(M \cdot N)$，且极易对非冲突语义产生误报。在 SynapseForge 理论体系中，文档首先经过抽象语法树解析器投影为高维分块空间：

$$\mathcal{T}(\mathcal{D}) = \left( \mathcal{V}_{\text{frontmatter}}, \mathcal{V}_{\text{heading}}, \mathcal{V}_{\text{body}}, \mathcal{E}_{\text{hier}} \right)$$

其中 $\mathcal{E}_{\text{hier}}$ 显式编码各级标题与其下辖论证块的父子拓扑。基于该分层空间，三方合并操作 $\mathcal{M}(\mathcal{D}_{\text{base}}, \mathcal{D}_{\text{ours}}, \mathcal{D}_{\text{theirs}})$ 转化为树同构判别与同名节点的语义重构。只要并发修改满足结构正交性判定准则：

$$\Delta(\mathcal{D}_{\text{ours}}) \cap \Delta(\mathcal{D}_{\text{theirs}}) \subseteq \mathcal{V}_{\text{disjoint}}$$

系统即可在 $\mathcal{O}(|\mathcal{V}|)$ 线性时间内达成无损强最终一致性（Strong Eventual Consistency），彻底消解跨时区并发协作引发的合并阻塞。
