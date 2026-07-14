# /tdd 内置 Skill 开发思路

## 背景

Codia 已经有 `/test` Skill 来跑测试、分析失败原因，但缺少一个能**主动推进完整 TDD 工作流**的能力。用户每次想按 red-green-refactor 开发，都要手动描述流程，步骤多、一致性差。

目标：新增 `/tdd` 内置 Skill，让用户输入 `/tdd <需求>` 后，Agent 自动循环推进测试驱动开发。

---

## 核心洞察：Codia Skill 是什么

Codia 的 Skill 不是传统插件，而是**带元信息的提示词程序**：

- **YAML frontmatter**：名字、描述、执行模式、允许使用的工具
- **Markdown body**：Agent 的行为剧本（SOP）

Skill 系统底层（loader/registry/activator/command）已经实现。新增一个 Skill，本质上就是新增一段合规的 Markdown 文件。Agent 激活 Skill 后，会把正文钉在上下文里，后续行动受其约束。

> 这意味着：测试运行、文件读写、Skill 间调用这些“动作能力”已经由工具层提供，`/tdd` 只需做好**流程编排**。

---

## 关键设计决策

### 1. /tdd 不是 /test 的替代，而是编排层

| Skill | 职责 |
|---|---|
| `/test` | 运行已有测试，分析失败原因 |
| `/tdd` | 循环推进 red → green → refactor |

`/tdd` 在需要跑测试时，通过 `LoadSkill("test")` 复用 `/test` 的能力，自己不重复实现测试分析逻辑。

### 2. 单文件内置 Skill

形态与 `/commit`、`/review`、`/test` 保持一致：

```
src/skill/builtin/tdd.md
```

不采用目录型 Skill，是因为内置 Skill 的统一形态就是单文件。测试原则、mock 指南等参考内容被精简后内联到正文。

### 3. inline 模式

`mode: inline`，因为 `/tdd` 需要在当前会话里：
- 读取项目源码
- 写测试文件
- 改实现
- 与用户交互澄清需求

fork 模式会隔离上下文，不适合这种需要持续文件交互的场景。

### 4. 工具白名单

```yaml
allowedTools: ["Read", "Write", "Edit", "Bash", "LoadSkill"]
```

刚好覆盖 TDD 所需动作：读代码、写测试、改实现、跑命令、加载 `/test`。

### 5. 全自动循环

用户选择：
- 每轮循环自动推进，不需要人工确认
- `/tdd` 自己负责重构阶段

Agent 维护一个行为 checklist，完成一项勾一项，直到全部覆盖。

---

## /tdd 的运行流程

```
用户输入 /tdd 实现字符串反转函数
        │
        ▼
系统加载 src/skill/builtin/tdd.md
        │
        ▼
Agent 按 SOP 执行：
  1. 理解需求 → 确定 seams（函数接口）
  2. 列出行为清单
       - [ ] 普通字符串反转
       - [ ] 空字符串
       - [ ] 含空格字符串
  3. 循环直到清单为空：
       a. RED：为下一个行为写失败测试
       b. RUN：LoadSkill("test") + pnpm test，确认失败
       c. GREEN：写最小实现
       d. RUN：再跑测试，确认通过
       e. REFACTOR：安全小步重构
       f. 勾选已完成行为
  4. 输出最终报告
```

---

## 实现产物

新增文件：`src/skill/builtin/tdd.md`

内容结构：
1. 适用场景
2. 核心原则（seams、red 在 green 前、一次一个行为、最小实现、安全重构）
3. 详细工作流程（7 步）
4. 禁止事项
5. 歧义处理规则

---

## 验证分层

| 层次 | 内容 | 方式 |
|---|---|---|
| 单元 | 不破坏现有 Skill 系统 | `pnpm test` 全绿 |
| 集成 | `/tdd` 能被扫描、注册为命令 | 脚本调用 loader/registry |
| 端到端 | `/tdd` 激活后按循环推进 | 本地终端手动测试 |

---

## 可复用的经验

1. **先澄清需求再写代码**。需求不明时，用 brainstorming/explore skill 把边界画清楚，避免返工。
2. **善用现有能力**。`/test` 已经会分析测试失败，`/tdd` 直接调用它而不是重写。
3. **Skill 是内容，不是代码**。对于流程型能力，写清楚 SOP 比写 TypeScript 更有效。
4. **保持一致性**。新内置 Skill 的形态、模式、工具白名单尽量向已有 Skill 看齐。
5. **端到端必须手动跑**。AI 不写 e2e 脚本，但要把 checklist 给清楚，让用户在真实终端验证。

---

## 后续可优化方向

- 是否给 `/tdd` 加别名（如 `/test-driven`）
- 复杂需求时是否用 TaskCreate/TaskUpdate 显式跟踪循环进度
- 重构阶段是否允许 `/tdd` 调用 `/review` 做代码审查
