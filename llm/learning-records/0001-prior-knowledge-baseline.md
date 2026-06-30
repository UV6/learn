# Prior Knowledge Baseline — LLM

用户在开始学习 LLM 原理时已具备：
- Java 后端开发经验，熟悉软件工程
- Python 语法基础（边用边查）
- LangChain/LangGraph 应用开发经验（前五课已学）
- 对 LLM 应用层概念有基础认知：token、context window、temperature、RAG、Agent Loop

需要注意的是：
- 可能不熟悉线性代数（矩阵乘法、注意力分数的计算需要）
- 可能不熟悉 PyTorch 基本操作
- 不需要从零学数学——关键是理解直觉和设计动机，而非推导

**Implications**: 课程应从直觉出发（"为什么需要 Attention"），逐步引入公式（"Q×K^T 代表什么"），最后落到代码（"这个 nn.Linear 对应公式中的哪个矩阵"）。
