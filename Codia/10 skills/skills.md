# Skill 可复用技能包 总结

Skill 是写给 Agent 的 SOP（标准操作流程）。它把一组可复用的 prompt、专属工具和参考资料打包成一个**独立、可编辑、可分发**的能力包，解决了两个核心问题：

1. **重复 prompt 不需要每次手打** — 从源码硬编码搬进 Markdown 文件，随时改、即时生效
2. **工具太多时模型容易选错** — 通过渐进式披露 + 工具白名单，把模型注意力收窄到正确的工具上【指定某个流程中用哪些工具】

---

## 为什么需要 Skill

### 痛点一：反复输入同样的 prompt

每次 commit、review、test 都要打一大段几乎一样的指令，格式要求、检查维度、注意事项每次都重打一遍。不打又不行，Agent 不知道你期望什么标准。

### 痛点二：工具越多，模型越容易选错

内置工具有 5 个，接入 MCP 后可能变成 15、25 个。常见翻车场景：

- 该用 Grep 搜索时选了 Bash 的 grep，功能差不多但权限绕过去了
- 20 个工具摆面前，分不清什么时候该用 Glob 什么时候该用 Grep
- 该先 `git diff` 再 `git add`，顺序搞反了

### 为什么不用 Slash Command 的 prompt 类型？

上一章的 `/review` 就是 prompt 类命令，但有几个硬伤：

- prompt 硬编码在 Handler 里，改一个字就要重新编译
- 只有开发者能加新命令，用户没法自定义
- 没法做工具级隔离和安全保护
- 没法附带专属工具、参考文档等资源

---

## Skill 的本质：写给 Agent 的 SOP

SOP 是写给人看的操作流程，人按流程执行。Skill 是写给 Agent 的 SOP，Agent 按流程执行。

关键区别：人可以「领会精神」，写得模糊一点也能理解。Agent 只会「照字面做」，所以 **Skill 里的指令要比人类 SOP 更精确、更具体**。

---

## Skill vs Slash Command：什么时候用什么

```
不需要 AI 参与 ──→ local / local-ui 类 Slash Command（/clear、/plan）
                      确定性强、不耗 token、毫秒响应

需要 AI，但简单 ──→ prompt 类 Slash Command（/review）
                      不需要自定义、不需要工具隔离

需要 AI，较复杂 ──→ Skill（/commit、/test）
                      可编辑、可带专属工具、可限制权限、可分发
```

一个比喻：

- `local` / `local-ui` Slash Command = 电灯开关，按下去就亮，确定
- `prompt` Slash Command = 贴在开关旁边的任务清单，能用但灵活度有限
- Skill = 给实习生的任务清单，他会按指示做，但有自己的判断空间

---

## Skill 文件结构

### 单文件 Skill

一个 `.md` 文件，分为两部分：

**上半部分 — YAML Frontmatter（元信息）**：

```yaml
---
name: commit              # 唯一标识，也是命令名
description: 分析 git diff 并生成规范的 commit
allowedTools:             # 工具白名单
  - Bash
  - ReadFile
  - Grep
mode: inline              # inline（默认）| fork
---
```

**下半部分 — Prompt Body（发给 LLM 的指令）**：

使用 Markdown 编写，包含任务说明、执行步骤、注意事项等。

### 目录型 Skill

当 Skill 需要自带专属工具和参考资料时，演化为目录结构：

```
backend-interview/
├── SKILL.md              # 入口：frontmatter + SOP 流程
├── tool.json             # 专属工具定义（function calling schema）
└── references/           # 工具实现代码、长文档、API 参考等
    └── parse_resume_tool.go
```

`tool.json` 负责**注册新工具**（往系统里塞一个原本不存在的工具），`allowedTools` 负责**可见性**（限制 Skill 能看到哪些已有工具）。两者职责不重叠。

---

## Frontmatter 字段详解

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | Skill 唯一标识，也是调用命令名。不与内置命令冲突 |
| `description` | 是 | 一句话描述，用于 `/help` 列表和意图匹配 |
| `allowedTools` | 推荐 | 工具白名单，限制 Skill 执行时可用的工具 |
| `model` | 否 | 指定使用的 LLM 模型（简单任务用便宜的，复杂用强的） |
| `mode` | 否 | `inline`（默认）或 `fork` |
| `context` | 否 | fork 模式下带多少上下文：`full` / `recent` / `none` |

---

## inline vs fork：两种执行模式

这是理解 Skill 系统最重要的概念之一。是否注入到 prompt 中

### inline 模式（默认）

Skill 的 prompt 被注入到当前对话中，走 Agent Loop。Skill 能看到之前的对话上下文，执行结果也留在对话历史里。

```
[用户消息 1]
[Agent 回复 1]
[用户消息 2]
[用户: /commit]           ← 触发
[系统注入 Skill prompt]   ← inline 注入
[Agent 执行]              ← 能看到前面的上下文
[用户消息 3]              ← 能看到执行结果
```

**适合 `/commit`**：Agent 前面可能帮你改过代码，需要这些上下文才能判断该 commit 哪些文件。

### fork 模式

Skill 在独立上下文中执行，不影响也不受当前对话影响。执行完后只把结果摘要返回到主对话。

```
[主对话]                    [fork 会话]
用户消息 1                  
Agent 回复 1               
用户: /review              
  ────────────→           Skill prompt（独立上下文）
  （主对话暂停）            独立执行审查
  ←────────────            返回审查报告
Agent 显示审查报告
```

**适合 `/review`**：代码审查应该客观。inline 模式下 Agent 之前说过「这个实现挺好的」，这种自我认同会影响审查结果。fork 切断对话历史，相当于换个全新视角。

### `context` 字段控制 fork 带多少背景

| 值 | 含义 |
|----|------|
| `none` | 完全隔离，审查场景最稳妥 |
| `recent` | 最近 5 条消息 |
| `full` | 主对话的摘要 |

---

## $ARGUMENTS：让 Skill 接收参数

Prompt body 中的 `$ARGUMENTS` 会被替换为用户传入的参数：

```
输入：/review 重点关注安全问题
替换后：请审查以下代码变更。重点关注安全问题。...
```

不带参数时 `$ARGUMENTS` 替换为空字符串，所以在 prompt 里用「如果没有指定...」做兜底。

---

## 三层 Skill 搜索路径

优先级从高到低（同名 Skill 高优先级覆盖低优先级）：

```
1. 项目级：{projectDir}/.codia/skills/     ← 团队共享，可提交到 git
2. 用户级：~/.codia/skills/                 ← 个人定制
3. 内置级：编译进二进制的 Skill                ← 随 Codia 分发
```

这个设计跟 npm 包搜索路径、Git `.gitconfig` 一样：先本地，再全局，最后内置。

---

## 自动注册为命令（显式调用） + 意图识别（两阶段加载）

### 显式调用

Skill 加载后自动注册为 Slash Command，用户可以直接 `/commit` 调用。注册时复用上一章的 `PROMPT` 命令类型，在 `/help` 列表中标注 `[skill]`：

```
可用命令：
  /help, /h, /?        显示帮助信息
  /commit [skill]      分析 git diff 并生成规范的 commit
  /review [skill]      审查代码变更
  /test [skill]        运行测试并分析结果
```

### 意图识别（两阶段加载）

用户不需要记住所有 Skill 的名字。Agent 能根据自然语言自动匹配：

```
用户：「帮我做个后端面试准备」
  → Agent 判断匹配 backend-interview Skill
  → 调用 LoadSkill("backend-interview")
  → 加载完整 SOP 和专属工具
  → 按流程执行
```

**第一阶段 — 轻量注册**：启动时只加载每个 Skill 的 frontmatter（name + description），注入到 system prompt，告诉 Agent 有哪些 Skill 可用。落到 prompt cache 的稳定前缀区，即使 30 个 Skill 开销也很低。

**第二阶段 — 按需加载**：Agent 判断匹配后调用 `LoadSkill` 工具，加载完整 SOP body 和专属工具。SOP 通过 `tool_result` 进入对话历史，只占一次 token，后续轮次不再重复。如果对话长了触发 auto-compact，SOP 和其他早期消息一起被摘要压缩。

### 为什么不把 SOP 钉在每轮都注入的「环境上下文」里？

- **Token 开销**：3000 token 的 Skill 跑 20 轮就多花 6 万 token，且不享受 prompt cache
- **放进对话历史**：只占一次 token，后续随对话自然推进。auto-compact 触发时自动摘要，不需要专门处理
- **嵌套共存**：多个 Skill 激活后，各自的 SOP 都在对话里，模型都能看到

---

## allowedTools：渐进式披露与安全

在skill 中显示当前能用哪些 skill

### 为什么需要限制工具？

**准确率**：commit Skill 只暴露 Bash、ReadFile、Grep 三个工具，模型的选择范围从二十几个骤降到 3 个，选错概率大幅降低。

**安全**：第三方 Skill 即使 prompt 里有恶意内容试图 `rm -rf /`，如果 `allowedTools` 里没有 Bash，它根本执行不了。这就是最小权限原则。

### 实现方式

```
allowedTools 为空 → 用全部工具（向后兼容）
allowedTools 非空 → 只注册白名单里的工具，其余丢掉
```

额外做了 **fail-fast 依赖检查**：执行前先确认白名单里每个工具都存在，任何一个找不到立刻报错，不等 Agent 跑起来再失败。

---

## Skill 能不能互相调用？

可以。`LoadSkill` 被标记为**系统工具**，不受 `allowedTools` 约束，所有 Skill 都能用它。

### 为什么不把 LoadSkill 也放白名单？

因为工具分两类：

- **业务工具**（Bash、ReadFile、WriteFile）：操作外部世界，有副作用，必须被白名单管辖
- **系统工具**（LoadSkill）：只影响 Agent 自身状态，是 Skill 系统的运行基础设施，授权没意义

所以 `allowedTools` 的定位是**业务工具白名单**，同时承担：管副作用 + 管信息可见性。

---

## 三个内置 Skill

### 1. commit — 分析 diff 并【生成】规范提交

- 模式：`inline`
- 流程：`git status` → `git diff` + `git diff --staged` → 分析 → 生成 conventional commit message → 逐个 `git add` → `git commit`
- 关键细节：不用 `git add -A`，逐文件判断；超过 10 个文件主动建议拆分

### 2. review — 隔离上下文做客观审查

- 模式：`fork`（关键！切断自我认同）
- 从上一章的硬编码 Slash Command 升级为 Skill
- 五个维度：逻辑正确性、安全性、性能、代码风格、可维护性
- 严重程度分级：Critical / Warning / Info

### 3. test — 跑测试并区分失败类型

- 模式：`inline`
- 流程：检测项目类型 → 运行测试 → 分析输出
- **关键能力**：区分代码 bug 导致的失败 vs 测试本身写错导致的失败，修复方向完全不同
- 全绿时也报告覆盖率和可能的遗漏场景

---

## Skill 在工具生态中的位置

```
Skill          ← 编排层：把工具调用编排成任务级工作流
  ↑
MCP            ← 接入层：开放的工具接入协议
  ↑
Function Calling ← 原子层：单次工具调用
```

三者互补：Function Calling 负责调用，MCP 负责接入，Skill 负责编排。

---

## 本章小结

Skill 系统让可复用的 AI 操作从源代码变成了**可编辑的 Markdown 资产**：

- 改 prompt 不用重新编译，改 `.md` 文件就行
- 用户和团队可以自定义 Skill，放进对应目录即生效
- 两阶段加载让 Agent 平时只看到摘要，用时才加载完整内容
- `allowedTools` 同时解决准确率和安全问题
- inline / fork 两种模式覆盖不同上下文需求
- 目录型 Skill 自带工具和参考资料，可打包分发

Slash Command 的边界是「内置固定命令」，Skill 突破了这个边界 —— 让能力变成可编辑、可分发、可组合的资产。
