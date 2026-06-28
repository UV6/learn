# 0001: Agent Basics Completed

2026-06-28

## What was learned

- Agent = LLM + Tools + Orchestration Loop。LangChain 的 `create_agent()` 封装了完整的 Agent 循环
- 工具定义只需要：函数名 + type hints + docstring，LLM 通过描述自动判断何时调用
- Agent Loop 是 LLM 推理 → 决定调用工具 → 获取结果 → 再次推理，直到不需要工具
- 实际用 DeepSeek API（OpenAI 兼容协议）运行了第一个 Agent，Agent 自动进行了重试（"北京" 失败后用 "Beijing" 重试）

## Key insights

- 用户不需要写任何循环逻辑 — Agent 自动处理工具调用和重试
- DeepSeek 通过 `init_chat_model("openai:deepseek-chat", ...)` + 自定义 base_url 接入
- Agent 展示了 emergent behavior：工具返回 "No data" 后自动用拼音重试

## Gaps / questions to revisit

- Agent 的最大迭代次数如何控制？
- 如果有多个工具，Agent 的选择机制是怎样的？
- Streaming 模式（`agent.stream()`）的工作方式
