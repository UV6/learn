# 0003: LangGraph Workflow Learned

2026-06-28

## What was learned

- LangGraph 是 Agent 编排的底层引擎，create_agent() 底层就是用 LangGraph 实现的
- StateGraph 三要素：State（共享内存）、Node（执行单元）、Edge（普通边 + 条件边）
- State 用 TypedDict/Pydantic 定义，add_messages reducer 控制消息追加而非覆盖
- 条件边通过 router 函数根据 State 决定下一个节点，实现分支逻辑
- 循环控制需要显式设置上限（如 search_count >= 3），避免无限递归
- 面试高频：Checkpointing（状态快照）、Human-in-the-Loop（interrupt/Command）、并行节点、子图

## Key insights

- LangGraph 的核心价值是把 Agent 循环从"黑盒"变成"白盒"——每一步可控制、可观察、可调试
- 条件边是 LangGraph 区别于简单 Chain 的本质差异
- State 的 reducer 机制（add_messages）是理解图状态管理的关键

## Gaps / questions to revisit

- interrupt() + Command 的 Human-in-the-Loop 实际代码
- 子图（Subgraph）在多 Agent 场景的用法
- MemorySaver vs SqliteSaver 的实际使用和序列化
