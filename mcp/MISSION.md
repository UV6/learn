# Mission: MCP 协议 + Skill 开发

## Why
完成 LangChain 应用层和 LLM 原理层的学习后，需要深入 Agent 的工具生态——MCP (Model Context Protocol) 是 AI Agent 连接外部世界的标准协议，Skill 开发是让 Agent 具备可复用能力的关键技术。目标是能独立开发 MCP Server 和 Claude Code Skill。

## Success looks like
- 能说出 MCP 协议的分层架构：Transport、Protocol、Resources/Tools/Prompts
- 能独立开发一个 MCP Server（Python SDK），提供 Tools 和 Resources
- 能开发一个 Claude Code Skill（含 system prompt + hook 配置）
- 能解释 MCP vs Function Calling vs Plugin 的架构差异
- 能对比 MCP Python SDK 和 TypeScript SDK 的 API 设计

## Constraints
- 语言：Python SDK 为主，TypeScript SDK 为了解
- 环境：已有 Claude Code 可测试 MCP Server
- 时间：约 1 周

## Out of scope
- 大规模 MCP 服务部署/网关
- MCP 协议本身的规范撰写（只学用，不学改协议）
