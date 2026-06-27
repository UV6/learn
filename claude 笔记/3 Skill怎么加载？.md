### 核心问题

如果你有一套技能规范（React 组件规范、SQL 风格指南、API 设计文档），全部塞进 system prompt 会怎样？每次调用 LLM 都带着几千行规范，不管当前是在改 CSS 颜色还是修 SQL 查询。**99% 的内容和当前任务无关，白白消耗 token。**

### 解决方案：两级加载

技能系统用两层结构解决了"要有的选、但不必全带"的矛盾：

|层|位置|时机|代价|
|---|---|---|---|
|**目录**|SYSTEM prompt|启动时注入|~100 token/技能，每轮都带|
|**内容**|tool_result（工具返回）|Agent 调用 `load_skill` 时|~2000 token/技能，按需|

---

### 第一级：启动时注入目录

Harness 启动时扫描 `skills/` 目录，每个技能对应一个子目录，里面包含 `SKILL.md` 文件：

```
skills/
  agent-builder/SKILL.md
  code-review/SKILL.md
  mcp-builder/SKILL.md
  pdf/SKILL.md
```

`_scan_skills()` 解析每个 `SKILL.md` 的 YAML frontmatter，提取 `name` 和 `description`，存入 `SKILL_REGISTRY` 字典。`list_skills()` 据此生成目录，注入 SYSTEM prompt：

```
Skills available:
- code-review: Review code for bugs, style, and best practices
- mcp-builder: Build MCP servers following best practices
- pdf: Read, create, and manipulate PDF files
Use load_skill to get full details when needed.
```

Agent 每轮都能看到"我有哪些技能可用"，但这只是目录，不花额外 API 调用。

---

### 第二级：load_skill 按需加载

Agent 判断"需要代码审查规范"时，调用 `load_skill("code-review")`。系统通过注册表查找（不走文件路径，避免路径遍历），把技能的完整内容以 `tool_result` 形式注入当前对话。

**关键设计**：技能内容不进 system prompt，而是作为一次工具结果进入 `messages[]`。这意味着：

- 它跟着对话历史走，后续回应都能参考
- 它参与 s08 的压缩管线——旧的、不再需要的技能内容会被压缩掉
- 它不污染 prompt cache

**按需加载解决了"不该提前带的不要带"，compact 解决"该丢的怎么丢"——两句互为补充。**

---

### real Claude Code 的复杂度（教学版做了哪些简化）

**技能来源不止一个目录**：CC 从多个来源加载——`~/.claude/skills/`（用户级）、`.claude/skills/`（项目级）、`--add-dir` 指定的目录、内置技能、MCP 远程技能、legacy commands 等。教学版合并为一个 `skills/` 目录。

**SKILL.md 有更多 frontmatter 字段**：CC 支持的字段包括 `model`（覆盖模型）、`context`（inline/fork 执行模式）、`paths`（按文件路径条件激活）、`allowed-tools`（自动允许的工具列表）、`user-invocable`（用户可用 `/name` 调用）等。教学版只解析 `name` 和 `description`。

**注入机制更精细**：CC 的 `Skill` 工具返回文本只是 "Launching skill: {name}"，真正的技能内容通过 `newMessages` 注入对话。教学版简化为直接把内容放入 tool_result。