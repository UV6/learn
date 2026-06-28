# 0002: RAG Concepts Learned

2026-06-28

## What was learned

- RAG = Retrieval + Augmented + Generation，解决 LLM 知识截止、幻觉、私有知识三大问题
- 五个环节：Load → Split → Embed → Store → Retrieve，各有对应 LangChain 组件
- chunk_size/chunk_overlap/separators 是调参关键，没有万能值
- embedding 的本质：语义相近 → 向量距离近
- 检索不准的排查链：chunk → embedding 模型 → reranker → 混合检索 → prompt 优化
- 评估 RAG：RAGAS 框架（faithfulness + answer relevance + retrieval metrics）

## Key insights

- 本地 embedding（BGE 系列）可避免额外 API 成本
- RAG 可被包装成 Tool 集成到 Agent 中，获得可追溯的知识来源
- 面试核心：RAG vs Fine-tuning 的取舍、检索质量优化方法论

## Gaps / questions to revisit

- 混合检索（BM25 + 向量）的具体实现
- Reranker 的集成方式
- 将 RAG 作为 Agent Tool 的组合模式
