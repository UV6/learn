# Hook 生命周期钩子 总结

Hook（生命周期钩子）让你在 Agent 运行的关键节点上挂载自动化动作，把那些"每次都要手动重复做的事"交给系统自动执行。

---

## 为什么需要 Hook

用了 Agent 一段时间后，你会养成一些"习惯"：

- Agent 写完代码文件 → 手动跑格式化
- Agent 修改了 `.proto` 文件 → 手动跑代码生成器
- Agent 要执行 `rm -rf /` → 紧张地盯着审批弹窗
- 每次新对话 → 手动敲"请先读 ARCHITECTURE.md"

这些操作有一个共同特点：**触发条件明确，执行动作固定**。每次都一模一样。

Hook 就是把这些"人肉 CI"变成事件驱动的自动化：某个事件发生 → 满足某个条件 → 自动执行某个动作。你不需要在那盯着。

---

## Hook 的三要素

一个 Hook 由三部分组成：**事件**（什么时候）、**条件**（什么情况下）、**动作**（做什么）。

条件可以省略（不写 `if` 就是无条件执行），但事件和动作必须要有。

```yaml
hooks:
  - event: post_tool_use       # 事件：工具执行之后
    if: tool == "WriteFile"    # 条件：只有写文件才触发
    action:                     # 动作：执行什么
      type: command
      command: "lint $FILE_PATH"
```

### 配置文件位置（追加合并）

Hook 配置放在 YAML 文件里，三个位置**追加合并**（不像 Skill 那样覆盖）：

```
1. .mewcode/config.local.yaml   ← 本地临时改动，不追踪，最高优先级
2. .mewcode/config.yaml         ← 项目级，跟仓库走
3. ~/.mewcode/config.yaml       ← 用户级，跨项目共享
```

---

## 事件：Agent 生命周期中的关键时刻

把 Agent 运行过程想象成一条时间线，上面有很多关键节点，每个节点就是一个事件。

### 会话级事件
- `session_start` — 新会话开始时触发
- `session_end` — 会话结束时触发

### 轮次级事件
- `turn_start` — 用户发送新消息时触发
- `turn_end` — Agent 完成回复时触发

### 工具级事件（最常用）
- `pre_tool_use` — 工具执行**之前**触发（**唯一可拦截**）
- `post_tool_use` — 工具执行**之后**触发

### 消息级事件
- `pre_send` — 消息发送给 LLM 之前
- `post_receive` — 收到 LLM 响应之后

### 系统级事件
- `startup` / `shutdown` — 启动/退出
- `error` — 发生错误时
- `compact` — 上下文压缩时
- `permission_request` — 权限审批请求时
- `file_change` — 文件被修改时
- `command_execute` — Slash Command 执行时

> **`pre_tool_use` 和 `post_tool_use` 覆盖了绝大多数使用场景。**

---

## pre_tool_use：唯一能说「不」的事件

`pre_tool_use` 是整个 Hook 系统里最有价值的事件。其他事件都是"通知型"——事情发生了告诉你一声。但 `pre_tool_use` 发生在工具执行**之前**，你可以决定：**允许，还是拒绝**。

### 示例：禁止修改 package-lock.json

```yaml
hooks:
  - event: pre_tool_use
    if: tool == "WriteFile" && args.path ~= "package-lock.json"
    action:
      type: command
      command: "echo 'REJECT: package-lock.json 应该由 npm install 生成'"
    reject: true
```

关键在于 `reject: true`：工具调用被取消，Agent 收到错误信息作为工具结果，然后 Agent 可以调整策略（比如改用 `npm install`）。

### 实现逻辑

```
多个 Hook 匹配同一事件 → 按 YAML 中出现的顺序逐个执行
  → 前面任何一个标记 reject，后面全跳过
  → 返回 ToolRejectedError
  → LLM 看到错误，换一种方式完成任务
```

所以**写 Hook 时顺序很重要**：最兜底的拦截规则放前面。

### 对比：Hook vs 权限系统

| | 权限系统 | Hook |
|--|---------|------|
| 粒度 | 静态，配置固定 | 动态，可按参数内容判断 |
| 示例 | "禁止写 /vendor" | "允许 rm 但不允许 rm -rf /" |

---

## 条件语法：四种操作符

条件语法复用了权限规则的匹配语法，学一套就行。`&&` 和 `||` **不能混用**（避免引入运算符优先级的复杂度）。

| 操作符 | 含义 | 示例 |
|--------|------|------|
| `==` | 精确匹配 | `tool == "Bash"` |
| `!=` | 反向匹配 | `tool != "ReadFile"` |
| `=~` | 正则匹配 | `args.command =~ /rm\\s+-rf/` |
| `~=` | glob 匹配 | `args.path ~= "*.py"` |

> 小助记：`=~` 等号在前是正则（regex 表达力强、张牙舞爪），`~=` 波浪号在前是 glob（文件路径通配，更温和）。

```yaml
# 几个实际例子
if: tool == "Bash"                                    # 精确匹配
if: tool == "Bash" && args.command =~ /rm\s+-rf/      # 正则匹配 + 且
if: tool == "WriteFile" && args.path ~= "*.proto"     # glob 匹配 + 且
if: tool != "ReadFile"                                # 反向匹配
```

---

## 四种动作执行器

### 1. command — 执行 shell 命令（最常用）

```yaml
action:
  type: command
  command: "prettier --write $FILE_PATH"
  timeout: 10s
```

`$FILE_PATH` 会被替换成实际路径。超时后引擎终止子进程并返回错误。

### 2. prompt — 注入提示词

```yaml
action:
  type: prompt
  message: "请先阅读 ARCHITECTURE.md 了解项目结构。"
```

以 `<hook-notification>` 标签形式注入 system prompt 区域，不污染对话历史。和静态 system prompt 的区别：Hook 是动态的，可以加条件、配合 `once: true` 只在第一次触发。

### 3. http — 发送 HTTP 请求

```yaml
action:
  type: http
  url: "https://hooks.slack.com/services/xxx"
  method: POST
  body: '{"text": "Agent 修改了 $FILE_PATH"}'
```

适合发通知、写日志到外部系统。

### 4. agent — 启动子 Agent

```yaml
action:
  type: agent
  prompt: "请检查刚才写入的文件 $FILE_PATH 是否有安全漏洞。"
```

最强大的执行器：**用 AI 来监督 AI**。每次 Agent 写完文件，自动启动另一个 Agent 做安全审查。不过 agent 执行器依赖第 13 章 SubAgent 的子 Agent 运行时，本章只搭好接口骨架。

---

## 执行控制：once、async 和错误兜底

### once — 只执行一次

```yaml
hooks:
  - event: session_start
    action:
      type: prompt
      message: "技术栈：Python 3.12 + FastAPI + Claude API"
    once: true
```

	第一次触发后标记"已执行"，后续不再触发。**重启 Codia 会重置**——`once` 的语义就是"本次会话只触发一次"。

### async — 异步执行

```yaml
hooks:
  - event: post_tool_use
    if: tool == "WriteFile"
    action:
      type: http
      url: "https://hooks.slack.com/services/xxx"
    async: true
```

后台执行，不等待完成。**但 `pre_tool_use` 不能设为 async**——逻辑上不可能：需要同步返回"允许/拒绝"。

### 错误兜底

**Hook 执行出错只记日志，不中断 Agent 主流程。** Hook 是辅助机制，格式化失败了代码还在，通知没发出去工作成果不受影响。不能让辅助机制的故障把核心流程搞崩。

---

## 上下文变量：让 Hook 知道发生了什么

事件触发时，Hook 引擎创建 HookContext，包含事件的上下文信息。命令和 body 里的 `$xxx` 变量在执行前被替换成实际值。

| 变量 | 替换为 |
|------|--------|
| `$EVENT` | 事件名 |
| `$TOOL_NAME` | 工具名 |
| `$FILE_PATH` | 文件路径 |
| `$MESSAGE` | 消息内容 |
| `$ERROR` | 错误信息 |
| `$TOOL_ARGS.xxx` | 工具参数里 xxx 字段的值 |

未定义的变量替换为空字符串，不报错——容错性更好。

---

## 与 Agent Loop 的集成

Hook 不是独立运行的，而是直接"插"在 Agent 的主循环代码里。下面用伪代码展示 Agent 的一轮完整运行过程，标注了每个 Hook 事件插在哪一行、干的是什么事：

```text
function Agent.run(conversation):

    // ① 会话级：新会话开始，只触发一次
    hooks.runHooks("session_start", ctx)       ← 比如注入项目上下文

    loop:  // 一轮 = 一次用户输入 → Agent 回复

        // ② 轮次级：用户消息到达
        hooks.runHooks("turn_start", ctx)      ← 比如记录本轮开始时间

        // ③ 消息级：消息发给 LLM 之前
        hooks.runHooks("pre_send", ctx)        ← 比如在消息里追加当前时间

        response = llm.send(messages)          ← 核心：调用 LLM

        // ④ 消息级：收到 LLM 响应之后
        hooks.runHooks("post_receive", ctx)    ← 比如记录响应耗时

        // LLM 的响应里可能包含多个工具调用，逐个处理
        for toolCall in response.toolCalls:

            // ⑤ 工具级：执行之前（唯一可拦截的节点）
            err = hooks.runPreToolHooks(ctx)   ← pre_tool_use
            if err is ToolRejectedError:
                // 被 Hook 拒绝了，跳过本次工具调用
                // 拒绝原因作为工具结果返回给 LLM，LLM 会调整策略
                continue

            result = executeTool(toolCall)      ← 真正执行工具

            // ⑥ 工具级：执行之后
            hooks.runHooks("post_tool_use", ctx) ← 比如自动格式化、发通知

        // ⑦ 轮次级：本轮结束
        hooks.runHooks("turn_end", ctx)        ← 比如记录本轮 token 用量
```

### 两个关键区别

**`runHooks` vs `runPreToolHooks`**：这是两个不同的方法，名字像但行为完全不同。

| | `runHooks` | `runPreToolHooks` |
|--|-----------|-------------------|
| 用于 | 所有事件（①②③④⑥⑦） | 只用于 `pre_tool_use`(⑤) |
| 能否拦截 | 不能，执行完就完了 | 能，返回 `ToolRejectedError` 则取消工具调用 |
| 是否阻塞 | 取决于 `async` 配置 | 必须同步，否则没法在工具执行前返回拦截决定 |

**⑤ 的拦截流程**：一旦某个 Hook 的 `reject: true`，引擎立刻返回 `ToolRejectedError`，`continue` 跳过本次工具调用。LLM 在下一轮会看到"工具调用被拒绝 + 拒绝原因"，然后调整策略换一种方式完成任务。

### 把这些 Hook 事件放回 Agent 运行的全流程

一次完整的 Agent 运行过程，事件触发的顺序是这样的：

```text
程序启动 ──→ startup                    （只一次）
  │
  └── 会话开始 ──→ session_start         （只一次）
        │
        └── 第 1 轮对话:
              turn_start
              pre_send → LLM → post_receive
              [可能多次] pre_tool_use → 执行工具 → post_tool_use
              turn_end
        │
        └── 第 2 轮对话:
              turn_start → ... → turn_end
        │
        ...
        │
        会话结束 ──→ session_end
程序退出 ──→ shutdown
```

`startup` / `shutdown` / `session_start` / `session_end` 在整个生命周期里各只触发一次。`turn_start` / `turn_end` / `pre_send` / `post_receive` 每轮对话触发一次。`pre_tool_use` / `post_tool_use` 每次工具调用触发一次，一轮对话里可能有多次。

---

## 实战配置示例

### 写文件后自动格式化
```yaml
hooks:
  - id: auto-format
    event: post_tool_use
    if: 'tool == "WriteFile" && args.path ~= "*.py"'
    action:
      type: command
      command: "black $FILE_PATH"
```

### 禁止修改 vendor 目录
```yaml
hooks:
  - id: block-vendor
    event: pre_tool_use
    if: 'tool == "WriteFile" && args.path ~= "vendor/*"'
    action:
      type: command
      command: "echo 'vendor 目录请勿手动修改'"
    reject: true
```

### 新会话自动注入项目上下文
```yaml
hooks:
  - id: project-context
    event: session_start
    action:
      type: prompt
      message: |
        项目信息：
        - 技术栈：Python 3.12 + FastAPI + Claude API
        - 架构文档：参见 ARCHITECTURE.md
    once: true
```

### 拦截高危删除命令
```yaml
hooks:
  - id: block-dangerous-rm
    event: pre_tool_use
    if: 'tool == "Bash" && args.command =~ /rm\s+-rf\s+\//'
    action:
      type: command
      command: "echo '警告：检测到高危删除命令，已拦截'"
    reject: true
```

### 文件修改后发 Slack 通知
```yaml
hooks:
  - id: slack-notify
    event: post_tool_use
    if: 'tool == "WriteFile"'
    action:
      type: http
      url: "https://hooks.slack.com/services/xxx"
      method: POST
      body: '{"text": "Agent 修改了 $FILE_PATH"}'
    async: true
```

---

## 配置加载与校验

加载 Hook 配置时分两步：解析条件表达式为结构化数据，校验配置合法性。

校验规则：
- 事件名必须在合法事件列表中
- action 类型必须是 command / prompt / http / agent 之一
- `reject` 只能用在 `pre_tool_use`
- `async` 不能用在 `pre_tool_use`
- 每种 action 检查必填字段（command 要有 command、http 要有 url 等）
- 非法配置给出明确错误并定位到具体 Hook

---

## 本章小结

Hook 系统的设计哲学是**配置优于编码**：把自动化逻辑从代码里抽出来，变成用户可声明的 YAML 规则。加新规则不需要改代码、不需要重新编译。

核心设计很简洁：**事件 + 条件 + 动作**。四种执行器覆盖了命令执行、提示词注入、HTTP 通知、子 Agent 任务。`pre_tool_use` 的拦截能力让安全策略可以做到基于参数内容的细粒度控制——这是纯静态权限系统做不到的。
