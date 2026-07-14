# 理论学习：Slash Command 命令框架

> **架构定位**：本章实现的是**交互层的命令框架**。让常用操作绕过 Agent 引擎直接执行，省 Token 又快。

---

## 一、为什么需要 Slash Command

MewCode 已经能对话、调用工具、自主决策了。但有些操作有个尴尬的问题：它们**根本不需要 AI 参与**，却可能走一遍 LLM，白白消耗 token。

| 场景 | 如果不走命令框架 |
|---|---|
| 清屏 | 输入"清除对话"，LLM 思考后回复"已清除"，实际根本没清 |
| 查 token 用量 | 为了知道还剩多少 token，先消耗 token 去问 LLM |
| 切换 Plan Mode | 模式切换是 UI 层的事，跟 AI 没有关系 |

这些操作的共同特点是：**确定性、程序化、不需要推理**。让 LLM 来做，就像"让博士去按电灯开关"。

> **核心思路**：所有以 `/` 开头的输入走命令解析器，本地直接执行，绕过 Agent Loop。

这样能得到：
- **毫秒级响应**
- **不消耗 token**
- **结果稳定、不受模型随机性影响**

---

## 二、命令框架要解决的三件事

如果只有两三个命令，用 `if-else` 硬编码也可以。但 MewCode 内置 10 个命令，以后还会更多，必须有一套框架。

### 1. 注册：给命令发身份证

每个命令声明自己的元信息，集中交给 `registry` 管理：

```
Command:
    name        字符串       // 命令名，如 "compact"
    aliases     字符串列表    // 别名，如 ["c"]
    description 字符串       // 简短描述
    usage       字符串       // 用法示例
    type        CommandType  // 命令类型（local / local-ui / prompt）
    argPrompt   字符串       // 缺参数时的提示语（可选）
    hidden      布尔值       // 是否在 /help 中隐藏
    handler     函数         // 执行函数
```

注册示例：
```
registry.register(Command{
    name:        "help",
    aliases:     ["h", "?"],
    description: "显示帮助信息",
    type:        LOCAL,
    handler:     handleHelp,
})
```

这很像 Web 框架的路由注册：`router.GET("/users", handleUsers)`。声明式注册，框架负责分发。

**并发安全**：注册中心内部需要用读写锁。当前命令都在启动时注册，但下一章 Skill 系统会在运行时动态注册，到时候注册和查找可能并发。

### 2. 解析：拆出命令名和参数

输入 `/compact 保留数据库相关内容`，解析成：
- 命令名：`compact`
- 参数：`保留数据库相关内容`

基本规则：
- 以 `/` 开头
- 第一个空格前是命令名
- 之后是参数
- 命令名统一转小写（`/Help` = `/help`）

### 3. 执行：统一的 Handler 签名

```
CommandHandler = function(ctx: CommandContext) -> error

CommandContext:
    args         字符串           // 原始参数字符串
    agent        Agent实例        // Agent 实例
    conversation Conversation实例 // 当前对话
    session      Session实例      // 当前会话
    ui           UIController     // UI 控制接口
    config       Config           // 全局配置
```

`CommandContext` 把命令需要的资源打包，命令只关心做什么，不用自己找依赖。

`UIController` 是 UI 层暴露的接口：
```
interface UIController:
    addSystemMessage(text)       // 显示系统消息
    sendUserMessage(text)        // 将文本作为用户消息发送给 Agent
    setPlanMode(enabled)         // 切换 Plan Mode
    getTokenCount() -> int       // 获取当前 token 数
    refreshStatus()              // 刷新状态栏
```

命令通过 `UIController` 与 UI 交互，但不关心 UI 具体怎么实现。

---

## 三、三种命令类型

不是所有命令执行方式都一样，所以分成三类：

| 类型 | 说明 | 例子 |
|---|---|---|
| `local` | 纯本地执行，结果以系统消息显示 | `/help`、`/status`、`/session list` |
| `local-ui` | 本地执行，但会改变 UI 状态 | `/clear`、`/plan`、`/do` |
| `prompt` | 构造预设 prompt 发送给 Agent | `/review` |

### 3.1 local 型

执行完就结束，不走 Agent Loop，不消耗 token。

### 3.2 local-ui 型

会触发 UI 状态变化，比如：
- `/clear`：关闭当前会话并新建一个，重置界面
- `/plan`：切换到 Plan Mode，状态栏、工具可用性都跟着变
- `/do`：切回执行模式

### 3.3 prompt 型

本质是"带快捷方式的 prompt"。比如 `/review` 会自动生成一段代码审查 prompt 发给 Agent：

```
function handleReview(ctx):
    prompt = "请审查当前 git diff 中的代码变更。重点关注：\n" +
        "1. 逻辑错误\n2. 安全问题\n3. 性能问题\n4. 代码风格"
    if ctx.args != "":
        prompt += "\n\n额外关注：" + ctx.args
    ctx.ui.sendUserMessage(prompt)
```

这种命令**会消耗 token**，但帮用户省掉了记忆和输入复杂 prompt 的麻烦，而且 prompt 质量更稳定。

---

## 四、提升易用性的三个设计

### 4.1 别名

高频命令给短别名，减少输入成本：
- `/compact` → `/c`
- `/help` → `/h`、`/?`

别名匹配逻辑：先精确匹配命令名，再遍历别名。`/c` 先找有没有叫 `c` 的命令，没有再看别名，命中 `compact`。

**别名冲突处理**：两个命令声明同一个别名时，启动阶段直接 panic，让开发者在编译期解决，不要拖到运行时行为不确定。

### 4.2 参数提示 argPrompt

命令需要参数但用户没提供时，显示友好提示而不是冷冰冰报错：

```
Command{
    name:      "resume",
    usage:     "/resume <id>",
    argPrompt: "用法：/resume <id>",
    handler:   handleResume,
}
```

### 4.3 Tab 补全

输入 `/` 后按 Tab 列出所有命令；输入 `/com` 后按 Tab 补全为 `/compact`。

补全逻辑：
- 跳过 `hidden` 命令
- 同时匹配命令名和别名
- 单个匹配直接补全，多个匹配以下拉列表展示

---

## 五、与 UI 事件循环集成

命令拦截必须在消息发给 Agent **之前**：

```
用户按回车
  → trimSpace(input)
  → 如果为空，直接返回
  → parseCommand(input)
    → 不是命令 → sendToAgent(input)
    → 是命令
      → 只有 "/" → showCommandList(registry)
      → 找不到命令 → "未知命令：/xxx，输入 /help 查看可用命令"
      → 缺参数但有 argPrompt → 显示 argPrompt
      → 构建 CommandContext
      → 调用 cmd.handler(ctx)
```

几个设计细节：
- 只输入 `/` 时不报错，直接展示命令列表
- 未知命令时提示 `/help`
- 缺参数时给用法提示

> **原则：错误信息永远带下一步引导。**

状态栏也可以配合显示：
```
[DEFAULT] tokens: 45,230/200k | /help 查看命令
[PLAN]    tokens: 45,230/200k | /do 切换到执行模式
```

---

## 六、MewCode v1 的十个核心命令

| 类型 | 命令 | 说明 |
|---|---|---|
| `local` | `/help` / `/h` / `/?` | 显示帮助信息 |
| `local` | `/compact` / `/c` | 手动触发上下文压缩 |
| `local` | `/session` | 会话管理 |
| `local` | `/memory` | 记忆管理 |
| `local` | `/permission` | 权限管理 |
| `local` | `/status` / `/s` | 显示状态 |
| `local-ui` | `/clear` | 清除对话，开启新会话 |
| `local-ui` | `/plan` / `/p` | 切换到 Plan Mode |
| `local-ui` | `/do` | 切换回执行模式 |
| `prompt` | `/review` | 审查当前 git diff |

### 6.1 本地命令详解

**`/help`**
- 不带参数：列出所有可用命令
- 带参数：显示某命令的详细用法，如 `/help session`

**`/compact`**
- 手动触发上下文压缩
- 不带参数执行标准压缩
- 带参数可指定保留重点，如 `/compact 保留数据库相关内容`
- token 太少时提示"无需压缩"

**`/session`**
- 不带参数：显示当前会话概要
- `/session list`：列出历史会话
- `/session resume <id>`：恢复某会话
- `/session new`：新建会话
- `/session delete <id>`：删除某会话

**`/memory`**
- 不带参数：显示记忆概要
- `/memory list`：列出全部记忆
- `/memory add <类别> <内容>`：手动添加记忆
- `/memory clear`：清空自动记忆（需确认）

**`/permission`**
- 不带参数：显示当前权限模式和规则数量
- `/permission mode <模式>`：切换权限模式
- `/permission rules`：查看生效规则
- `/permission add <规则> <效果>`：添加本地临时规则
- `/permission reset`：重置本地规则

**`/status`**
- 显示综合状态：模式、token、工具数、记忆数、工作目录、版本
- 只是格式化 UI state，没有额外查询

### 6.2 影响 UI 状态的命令

**`/clear`**：关闭当前会话并保存历史，然后创建新会话，重置界面。

**`/plan`**：切换到 Plan Mode。带参数时同时把参数作为任务描述发给 Agent，如 `/plan 设计用户认证模块`。

**`/do`**：切回执行模式，与 `/plan` 成对使用。

### 6.3 转发给 Agent 的命令

**`/review`**：唯一 `prompt` 型命令。把预设的代码审查 prompt 发给 Agent，分析当前 git diff。可带参数指定额外关注点，如 `/review 特别注意并发安全`。

---

## 七、命令系统的边界

Slash Command 适合做：
- 预定义
- 程序化
- 确定性强
- 高频本地操作

它的局限：
- handler 硬编码在源码里
- 修改通常要重新编译
- 用户不能自由扩展

所以 Slash Command 解决的是"**内置固定命令**"的问题。更灵活、可动态加载、可让用户自定义的命令能力，交给下一章的 **Skill 系统**。

另外，Claude Code 中的 MCP prompt 也能以 `mcp__<server>__<prompt>` 的形式接入命令分发链路，MewCode 也把这类"外部贡献命令"的能力放到 Skill 系统里统一处理。

---

## 八、一句话总结

Slash Command 的本质不是"让用户少打几个字"，而是把**不需要 AI 的操作从 Agent Loop 里剥离出来**，建立一套统一的注册、解析、执行框架，让本地操作更快、更省 token、更稳定，同时为后续 Skill 系统打下扩展基础。

> 注：本文图片因飞书认证限制未能下载到本地，保留原始链接。
