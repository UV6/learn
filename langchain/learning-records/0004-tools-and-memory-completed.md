# 0004: Tools + Memory 理解

2026-06-28

## What was learned

- Tool 三层定义方式：函数自动转换（原型）→ @tool 装饰器（复杂参数）→ BaseTool 类（生产级：Pydantic 验证 + 依赖注入 + 异步）
- Tool 错误处理：永远不抛异常，返回描述性字符串让 LLM 决策
- Memory 三种形态：短期（messages 列表）、摘要（LLM 压缩旧上下文）、持久化（Checkpointer + Vector Store）
- LangGraph Checkpointer：每步自动保存 State，按 thread_id 隔离，支持时间旅行
- Human-in-the-Loop：interrupt() 暂停 → Command(resume=...) 恢复 → 用于高风险操作审批
- Context Window 管理：摘要 + 滑动窗口的混合策略最优

## Key insights

- Checkpointer 是 LangGraph 区别于 create_agent() 的核心能力——让 Agent 从"无状态工具调用"变成"持久化多轮对话"
- Tool 定义的演进映射了开发阶段：原型（函数）→ 完善（@tool）→ 生产（BaseTool）
- 面试中 80% 的场景题与 Tools + Memory 相关

## Gaps / questions to revisit

- interrupt() + Command 的实际运行效果
- 生产环境的 PostgresSaver 配置
- 摘要记忆的具体 prompt 设计和 token 预算控制
