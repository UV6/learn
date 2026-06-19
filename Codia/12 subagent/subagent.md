# SubAgent 子任务分发 总结

SubAgent 让系统从单 Agent 进化为**可分发任务**。核心思路很简单：把 Agent 【包装成一个工具】，主 Agent 可以像调用 Bash 或 ReadFile 一样调用子 Agent，在独立上下文中完成任务后返回结果。

---

## 为什么需要 SubAgent

### 问题：上下文污染

用单 Agent 一段时间后会撞上一个根本问题：**上下文污染**。

场景一：你让 Agent 重构一个模块，它读了 20 个文件、改了 5 个文件，上下文里堆满了重构的中间过程（diff、编译错误、修复记录）。然后你说"顺便帮我写一下单元测试"——Agent 要在一大堆噪声里翻找写测试需要的上下文，token 飙升、质量下降。

场景二：你让 Agent 同时做两件事——"查这个 bug"和"更新 README"。两个任务的上下文互不相关，却被塞进同一个对话窗口，互相干扰。

解决思路：既然一个 Agent 的上下文被污染了，那就创建一个新 Agent，给它干净的上下文，专门做那件事。做完把结果拿回来。

---

## 关键洞察：Agent 也是一种工具

回顾 Tool 接口：有名字、有描述、接受参数、返回结果。

Agent 是什么？同样：有名字、有描述、接受任务（参数）、返回结果。

**Agent 和 Tool 的抽象是同构的。** 所以可以把 Agent 包装成一个统一的 `Agent` 工具，注册到 **ToolRegistry** 里：

```
主 Agent 调用 Agent 工具
  → 创建子 Agent（独立上下文）
  → 子 Agent 完成任务
  → 返回结果给主 Agent
```

主 Agent 完全不需要知道调用子 Agent 和调用普通工具有什么区别。在它看来，`Agent` 和 `ReadFile` 都是工具，调用方式一模一样。

### 为什么是统一的一个 Agent 工具？

而不是 `agent_explore`、`agent_plan` 各注册一个？因为 Agent 类型可以动态加载。用户在项目里新建一个定义文件，下次就能用。如果每个类型都独立注册，工具列表会随着定义文件增减而变化，系统提示也要跟着重新渲染。统一成一个工具，通过 `subagent_type` 参数选类型，工具列表始终稳定。
【做成一个工具，但是可以选择不同类型的参数来使用不同的 agent，而不是定义多个 agent】
`Agent` 工具的参数：

| 参数 | 必填 | 说明 |
|------|------|------|
| `prompt` | 是 | 子 Agent 的任务描述 |
| `description` | 是 | 简短描述（3-5 词） |
| `subagent_type` | 否 | 指定预定义 Agent 类型（Explore/Plan 等），留空走 Fork |
| `model` | 否 | 覆盖定义里的模型 |
| `run_in_background` | 否 | 后台异步执行 |
| `name` | 否 | 命名 Agent，便于后续 SendMessage |
| `isolation` | 否 | 启用文件系统隔离（Worktree） |

---

## 两种创建模式

### 定义式：预定义的专家

预先定义好 SubAgent 的角色、能力和行为规范。像一个只读的安全审计员——可以查看代码，但不能修改任何东西。

```yaml
# .mewcode/agents/security-reviewer.md
---
name: security-reviewer
description: 专注于代码安全审查的子 Agent
disallowedTools:
  - Agent
  - Edit
  - Write
  - Bash
model: haiku
permissionMode: dontAsk
maxTurns: 20
---

你是一个专注于代码安全审查的 Agent。
## 职责
- 检查代码中的安全漏洞
- 识别敏感信息泄露风险
## 规则
- 只读取代码，不修改任何文件
- 按严重程度分级报告
- 给出具体的修复建议
```

关键点：
- `disallowedTools` 排除写操作，锁死能力边界
- `model: haiku` 用小模型，不需要顶配推理
- `permissionMode: dontAsk` 自动批准工具调用，不弹审批窗口（因写操作已被排除，安全）
- 从**空白对话**开始，不带父 Agent 的历史

### Fork 式：继承上下文的临时助手

不指定 `subagent_type` 留空，走 Fork 路径。**继承父 Agent 的完整对话历史。**

```text
父 Agent 对话历史 ──→ Fork 子 Agent 继承全部历史 + 新的任务指令
```

为什么 Fork 要继承对话历史？

1. **实际用途**：你和 Agent 聊了一阵子，它理解了需求和代码状态，Fork 子 Agent 知道你们在聊什么，不需要重新说背景
2. **成本优化**：Fork 子 Agent 和父 Agent 共用相同的系统提示和对话前缀，第一次 API 调用几乎 100% 命中 prompt cache

Fork 子 Agent 始终**以后台方式运行**。主 Agent 发起 Fork 后立刻继续工作，子 Agent 结果通过 `<task-notification>` 异步回传。

### Fork Boilerplate：把子 Agent 从"助手"强制切为"工人"

Fork 子 Agent 继承了父 Agent 的系统提示，那个提示里可能写着"你可以创建子 Agent""和用户确认"。Fork Boilerplate 会覆盖这些默认行为：

```text
<fork_boilerplate>
1. 不能再 Fork
2. 不要对话、不要提问、不要请求确认
3. 直接使用工具
4. 严格限制在被分配的任务范围内
5. 最终报告控制在 500 字以内
</fork_boilerplate>
```

### 决策：什么时候用哪种

```
固定角色、固定职责 ──→ 指定 subagent_type（定义式）
                       独立上下文、可限工具、可选小模型

临时任务、需要上下文 ──→ 留空走 Fork
                       继承对话、命中 cache、强制后台
```

---

## 上下文隔离：隔离什么，共享什么？

**运行时状态要隔离，基础设施可以共享。**

| 隔离（各自独立） | 共享 |
|-----------------|------|
| Conversation（对话历史）— 定义式空白，Fork 继承 | LLM 客户端（同一 API Key/连接池） |
| PermissionTracker（权限审批记录） | 工具集（无状态，共享没问题） |
| FileCache（文件缓存） | Hook 引擎（写文件自动格式化，谁的都得跑） |
| Token 计数（分开统计各 Agent） | 文件系统（操作同一文件系统） |

为什么文件缓存要隔离？特别是后面引入 Worktree 之后，子 Agent 可能工作在完全不同的目录中，共享缓存会导致读到错误内容。

---

## Agent 定义也是 Markdown

和 Skill 一样用 YAML frontmatter + Markdown body，但字段不同：

| | Skill | Agent |
|--|-------|-------|
| 工具限制 | `allowedTools`（白名单） | `tools`（白名单）+ `disallowedTools`（黑名单） |
| body 用途 | 每轮注入的活跃指令 | 子 Agent 的系统提示 |
| body 注入时机 | 每轮 reminder 重新注入 | 启动时注入一次，伴随整个生命周期 |

为什么 Agent 用黑名单？因为 Agent 扮演一个角色，能力接近全集，逐个列出几十个允许的工具不现实，排除少数危险工具更方便。

### 加载优先级【预定义的 agent 才有】

```
1. 项目级：{projectDir}/.mewcode/agents/   ← 离使用场景最近
2. 用户级：~/.mewcode/agents/
3. 内置级：程序编译嵌入
4. 插件级：第三方插件加载                   ← 优先级最低
```

---

## RunToCompletion：子 Agent 怎么执行

主 Agent 是"交互式"的——等用户输入 → 执行 → 再等。子 Agent 是"非交互式"的——拿到任务，从头跑到尾，返回结果：

```text
function runToCompletion(agent, task) -> string:
    agent.conversation.addUserMessage(task)    // 不等用户，直接注入
    loop (最多 maxTurns 轮):
        response = llm.send(messages)
        if response 没有 toolCalls:
            break                              // 纯文本 → 任务完成
        executeToolCalls(response.toolCalls)   // 仍走 Hook: pre → exec → post
    return lastText
```

和主循环区别就两点：不等用户输入（task 直接注入），LLM 不调工具时循环结束。

工具调用权限由 `permissionMode` 决定。`dontAsk` 让工具调用自动批准——前提是 `disallowedTools` 已经排除了危险工具，所以安全。

---

## 父子链路：防止嵌套失控

嵌套通过**工具过滤来隐式限制**，不靠硬编码深度数字：

1. **Fork 不能再 Fork** — 子 Agent 对话历史已有 Fork 标记时，再次 Fork 直接报错
2. **后台 Agent 不能再 spawn Agent** — `ASYNC_AGENT_ALLOWED_TOOLS` 白名单不含 Agent 工具
3. **定义式 Agent 看不到 Agent 工具** — `ALL_AGENT_DISALLOWED_TOOLS` 全局过滤

三条路径并行堵住，Skill fork 同样受这些限制约束（底层复用同一套 Agent 构造逻辑）。

---

## 后台运行模式

三种进入方式：

1. **调用时指定** — `run_in_background: true`
2. **自动超时** — 前台跑超过 120 秒自动切后台
3. **手动切换** — 用户按 ESC

加上 Fork 路径**无条件后台运行**，所有后台任务走统一的 `TaskManager` 生命周期。完成后通过 `<task-notification>` 注入对话，不打断主流程。

后台 Agent 有固定工具白名单（`ASYNC_AGENT_ALLOWED_TOOLS`）：只能读写文件、搜索、Bash、Web 等基础操作，不能用 Agent 工具（不能再 spawn）。

---

## 工具过滤的多层防线

四层依次过滤，每层防不同风险：

```
父 Agent 全部工具
  ↓ 第 1 层：全局禁止列表（ALL_AGENT_DISALLOWED_TOOLS）
       → 所有子 Agent 都不能用：Agent、AskUserQuestion、TaskStop
  ↓ 第 2 层：自定义 Agent 额外禁止（CUSTOM_AGENT_DISALLOWED_TOOLS）
       → 用户/项目定义的 Agent 有额外限制
  ↓ 第 3 层：后台 Agent 白名单（ASYNC_AGENT_ALLOWED_TOOLS）
       → 后台运行的 Agent 只能用基础工具
  ↓ 第 4 层：Agent 定义的 tools + disallowedTools
       → 白名单确定范围，黑名单从中排除
  ↓
最终可用工具集
```

每层都很简单，组合起来覆盖所有风险场景。

---

## 内置 Agent 类型

### Explore — 代码探索

- 模型：最弱的模型
- 能力：只读，Glob / Grep / Read / Bash(ls/git log 等)
- 黑名单：EditFile、WriteFile
- 用 `disallowedTools` 黑名单而非白名单：系统新增只读工具自动能用

### Plan — 架构规划

- 模型：默认
- 能力：只读，分析需求、探索代码库、设计实现路径
- 黑名单：Agent、Edit、Write、NotebookEdit
- **和 Plan 权限模式不同**：Plan 权限模式是主 Agent 切到只读规划状态，Plan Agent 是独立 SubAgent，规划过程的中间分析不会留在主 Agent 上下文里

### general-purpose — 通用子 Agent

- 能力：全部工具
- 用于需要完整能力但独立上下文的场景

### Verification — 验证 Agent

- 通过配置开关 `enableVerificationAgent: true` 启用
- 设计目标：找到"最后 20% 的 bug"
- 必须实际运行代码，读代码不算验证
- 输出：`VERDICT: PASS / FAIL / PARTIAL`
- 为什么做成可配置开关：日常开发关闭保持速度，CI 开启做门禁

---

## 本章小结

SubAgent 的核心设计是把 Agent 包装成统一的 `Agent` 工具，通过 `subagent_type` 参数选类型，留空走 Fork 继承上下文。

- 定义式 = 预定义专家，空白上下文，适合固定角色
- Fork 式 = 临时助手，继承上下文 + 强制后台 + 命中 cache，适合临时任务
- 上下文隔离 = 状态隔离，基础设施共享
- 多层工具过滤 = 全局 + 自定义 + 后台 + 定义，四层堵住嵌套失控和安全风险
- 后台运行 = 三种进入方式 + Fork 无条件后台 + `<task-notification>` 异步通知

但文件系统还是共享的。多个子 Agent 同时改文件会冲突——下一章 Git Worktree 解决这个问题。
