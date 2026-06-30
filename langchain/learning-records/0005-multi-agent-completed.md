# 0005: Multi-Agent Collaboration 理解

2026-06-28

## What was learned

- 多 Agent 的三种核心模式：
  1. **Supervisor 路由** — 集中决策，按意图分发给专业 Agent，最可控
  2. **Subagent 委托** — 子 Agent 包装为 Tool，主 Agent 灵活决策何时委托
  3. **Subgraph 嵌套** — 编译好的 Graph 作为另一个 Graph 的节点，可复用、可测试
- Supervisor 是轻量 LLM 调用，不做具体工作，只决策路由
- Subagent 返回值推荐自然语言（而非结构化 JSON），让主 Agent 直接理解
- 子图 State 必须是父图 State 的子集，子图写回变更对父图透明
- 多 Agent 不是银弹，单 Agent + 5 个 tool 能解决的不需要多 Agent
- 面试项目蓝本：RAG Agent + 订单 Agent + Supervisor 路由 + Checkpointer 记忆

## Key insights

- 模式选择由任务结构决定：可预定义类型 → Supervisor；灵活多变 → Subagent；复杂嵌套 → Subgraph
- 每个子 Agent 独立 context window，天然隔离，避免上下文过载
- 子 Agent 可以用不同模型（便宜的做搜索，贵的做推理），控制成本
- 子 Agent 错误处理：不抛异常，Supervisor 根据错误描述决策（换人/重试/degrade）

## Gaps / questions to revisit

- Swarm/handoff 模式的具体实现（Command(goto=...)）
- 生产环境多 Agent 的 observability（每个子 Agent 的延迟、token 追踪）
- 跨 Agent 的共享 memory（全局用户偏好层）
