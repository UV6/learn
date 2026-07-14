# Agent Team 多 Agent 团队协作 总结

【agent team 这个 team 模型跟 langgraph、AutoGen 等框架的区别】

Agent Team 把系统从"一个 Agent 带几个临时工"升级到**协作团队**。多个 Agent 并行工作、直接通信、自主协调——SubAgent 是星型拓扑（主 Agent 居中转发），Team 是网状拓扑（队员之间可以直接发消息）。

---

## 为什么 SubAgent 不够？

SubAgent 在处理复杂任务时暴露出两个硬伤：

### 1. 只能串行

重构四个模块，A 和 B 互不依赖，但 SubAgent 只能一个一个来：

```
串行：A → B → C → D（20 分钟）
并行：A + B 同时开工，C 等 A，D 等 B（近一半时间）
```

### 2. 队员之间不能直接通信

查日志的 Agent 发现可疑记录，需要告诉读代码的 Agent"去看 `handler.go:47`"。SubAgent 里做不到——所有信息必须经主 Agent 中转，主 Agent 成了瓶颈。

这就是"经理瓶颈"：团队里所有人只能跟经理汇报，同事之间不能直接说话。

---

## SubAgent vs Agent Team：关键区别

| | SubAgent | Agent Team |
|--|----------|------------|
| 拓扑 | 星型（中心 → 外围） | 网状（队员可直连） |
| 通信 | 只能经主 Agent 中转 | SendMessage 直接发 |
| 任务管理 | 无共享任务列表 | TaskCreate/List/Update 共享看板 |
| 适用 | 一次性、边界清晰的子任务 | 需协作、有依赖的持续性工作 |
| 生命周期 | 用完丢弃 | 可暂停、恢复、续写 |

底层通信不是实时直连——走的是**共享文件邮箱 + 500ms 轮询**，消息在收件人下一轮 Agent Loop 开头被读到。本质是异步的。

---

## MewCode vs 主流多 Agent 框架：关键分歧

讲到这里你可能想：业界已经有 AutoGen、CrewAI、LangGraph 这些多 Agent 框架，MewCode 的 Team 模型和它们有什么不同？

### 主流框架的做法：框架当裁判

AutoGen、CrewAI、LangGraph 的共同思路是**谁在什么时候做什么，由框架决定**：

| 框架 | 协调方式 |
|------|---------|
| AutoGen GroupChat | 一个调度者按规则决定"现在该谁说话" |
| CrewAI | 一个 Crew 对象编排任务在多个 Agent 之间流转 |
| LangGraph | 把多 Agent 协作直接写成**状态机**，每一步跳转到哪预先定义好 |

这些框架把协调逻辑放在**外面**——框架是调度器，Agent 是被调度的执行单元。

### MewCode 的做法：框架不当裁判，只给工具

MewCode 反过来：

- **不引入调度器**。没有"现在该谁说话"的规则引擎
- 把 TaskCreate、SendMessage、TaskUpdate 做成**工具**，注入到每个队员的工具集里
- 谁做什么、什么时候给队友发消息、认领哪个任务——**全由 LLM 自己判断**
- 框架只提供：共享任务列表 + 文件邮箱 + 协调工具

```
主流框架：  框架决定"谁什么时候做什么" → Agent 执行
MewCode：   框架只给"可以协调的工具" → LLM 自己决定怎么协作
```

### 各自的代价

**主流框架的代价**：新增一种协作模式要改调度器。但行为可预测——状态机走到哪一步是确定的。

**MewCode 的代价**：行为不如状态机可预测，LLM 可能做出不理想的协调决策。但收益是——想加新的协作方式只需要加一个工具，调度器不存在，也就不需要改。

用文档的原话说："这是一种把 Agent 当成有判断力的协作者、而不是流水线上某个工位的设计思路。"

---

## Team 的核心结构

```
AgentTeam:
    name            → 团队名称
    leadAgentID     → 谁是负责人（就是当前主 Agent）
    members         → TeammateInfo[] 花名册
    configPath      → ~/.codia/teams/{name}/config.json

TeammateInfo:
    name            → 队员名称，由 Lead 分配
    agentID         → Agent 实例 ID
    agentType       → 使用的 Agent 定义（定义式），留空走 Fork
    model           → 可覆盖模型
    worktreePath    → Worktree 路径（可选）
    backendType     → "tmux" | "iterm2" | "in-process"
    isActive        → true/undefined=活跃，false=空闲（无 terminated 状态，终止直接移除）
    planModeRequired → 是否需要 Lead 审批才能修改
```

两个设计细节：
- `isActive` 只是布尔值，队员终止后直接从 members 列表移除，不留墓碑
- `backendType` 是 member 级别的，同一团队不同队员可用不同后端

### 独立顶层工具

团队模式引入**独立的顶层工具**，不把团队创建塞进 Agent 工具的参数分支：

```text
第一步：TeamCreate(team_name="refactor-auth", description="重构认证模块")
第二步：Agent(subagent_type="worker", name="alice", prompt="重构数据层")
        Agent(subagent_type="worker", name="bob", prompt="重构服务层")
```

`TeamCreate` 是独立的——团队创建会改变 Lead 的运行模式，不应该作为 Agent 工具的副作用偷偷发生。对应还有 `TeamDelete` 负责销毁。

---

## 三种执行后端

系统按优先级自动检测选择，in-process 是兜底：

```
① 已在 tmux 内 → tmux
② 不在 tmux，但在 iTerm2 内 → iTerm2
③ 不在 iTerm2，但装了 tmux → tmux（拉外部 session）
④ 都不满足 → in-process
```

| | Tmux | iTerm2 | In-process |
|--|------|--------|------------|
| 进程 | 独立进程 | 独立进程 | 同进程协程 |
| 隔离性 | 完全隔离 | 完全隔离 | 共享进程 |
| 崩溃影响 | 互不影响 | 互不影响 | Lead 退出全退 |
| 可 spawn 子 Agent | ✅ 同步+后台 | ✅ 同步+后台 | 只能同步 |
| 依赖 | tmux | iTerm2 + it2 CLI | 无 |

所有选择在 spawn 前由 `detectBackend` 一次性决定，没有运行时回退。Pane spawn 失败不会静默切 in-process。

---

## 协调机制：共享工具取代共享文件

### 队员专属协调工具

队员比普通 SubAgent 多一组"协作工具"：

```
TaskCreate     → 创建新任务
TaskGet        → 查看任务详情
TaskList       → 列出所有任务
TaskUpdate     → 更新任务状态（含 addBlocks/addBlockedBy 依赖字段）
SendMessage    → 给其他队员发消息
```

打个比方：SubAgent 像外包（无 Jira/Slack 权限），队员像正式成员（能看看板、认领任务、@同事）。

### SendMessage：队员之间的直接通信

文件系统写入+轮询+并发控制
```text
SendMessage(to="bob",
    summary="接口签名变更通知",       // 5-10 词摘要，UI 预览用
    message="Authenticate() 签名改了，多了一个 ctx 参数")
```

**寻址方式**：
- 队友名称或 Agent ID：`to="bob"` 或 `to="agent-a1b"`，同名
- `"*"` 广播：发给所有队友

**结构化消息类型**：
- `shutdown_request` / `shutdown_response` — 优雅退出协商
- `plan_approval_response` — 计划审批（只有 Lead 可发）

**消息路由**：agentNameRegistry 把名称解析成 agentID → 写入 mailbox → Tmux 后端额外 `send-keys` 唤醒目标 pane

**并发写 mailbox 的安全性**：每个收件箱单独一个 lock file，`O_CREATE|O_EXCL` 抢锁，5-100ms 随机抖动重试最多 10 次。超过 10 秒未释放的锁视为 stale 清掉。写入走 `os.WriteFile` 原子替换。in-process 和 Pane 后端共用同一套文件锁机制。

### 什么时候用 TaskCreate vs SendMessage？

- 需要追踪状态 → TaskCreate（开工单）
- 纯通知/FYI → SendMessage（群里说一声）

---

## 团队生命周期（五阶段）

### 1. 创建

创建 team.json，检测后端，Lead 注册进团队。

### 2. 分解

Lead 拆任务、设依赖、派队员：

- 用 `TaskCreate` 创建任务
- 用 `TaskUpdate` 的 `addBlocks/addBlockedBy` 建立**系统级依赖**
- 对于简单场景，也可以在任务描述里写文本约定（如"需 T1 完成后再开始"）
- spawn 队员，队员从共享任务列表**自己认领**任务（非强制分配——基于自身上下文选择）

队员 spawn 六步：加载定义 → 可选创建 Worktree（命名 `team-{teamName}/{name}`）→ 注入协调工具 → 按后端分流 → 注册到 agentNameRegistry → 记录到 team.members

队员系统提示只需补一段简短附录，核心规则就一条：**纯文本回复对队友不可见，通信必须用 SendMessage。**

### 3. 执行

每个队员在自己的 Agent Loop 里自主决策：查任务列表 → 干活 → 更新状态 → 查消息 → 继续。没有固定调度指令，LLM 自己判断下一步。

**任务认领方式**：队员自己从共享任务列表里选，不是 Lead 强制分配。队员基于自身上下文选择最匹配的任务——比如 alice 刚读完数据层代码，自然倾向于认领数据层相关的任务。

**并发冲突**：文档未专门描述任务认领的防冲突机制。理论上两个队员可能同时认领同一个任务。文档的隐含假设是把协调权交给 LLM——如果 bob 看到 alice 已经认领了，LLM 应推理出"被领走了，我换一个"。但这依赖 LLM 在认领前先 `TaskList` 确认状态，不是系统层面的硬保证。如果需要更可靠的做法，可以给 `TaskUpdate` 加类似 mailbox 那套 `O_CREATE|O_EXCL` 文件锁机制。

### 4. 收敛

所有任务完成后，Lead 合并 Worktree 分支：

```text
git merge worktree-team-refactor-auth+alice --no-ff
```

- 机械性冲突 → Lead 自动解决
- 逻辑矛盾 → 回滚，上报用户

### 5. 清理

确认所有队员已空闲 → 清理 Worktree → 清理团队目录。不留痕迹，只留合并后的代码和 Git 历史。

---

## 队员空闲与续写

队员 `runToCompletion` 结束后，系统两步通知 Lead：标记 `isActive=false` + 发 idle notification 到 Lead 收件箱。

关键能力：**队员空闲或被 TaskStop 后，Lead 可通过 SendMessage 续写**。系统自动从磁盘 transcript 恢复队员，带着完整上下文继续工作。

```
SendMessage(to="alice", message="还需要一个集成测试...")
// alice 已停止 → 自动从磁盘恢复 → 带完整上下文继续
```

vs SubAgent：SubAgent 完成上下文就丢弃了，Team 队员的上下文持久化到磁盘，随时可续写。

---

## 任务分解策略

- **按文件边界分**：不同队员改不同文件，避免合并冲突。避不开同一文件则设依赖强制串行
- **每队员 2-4 个任务**：少了空闲，多了 LLM 选任务纠结
- **依赖要明确**：用 `addBlockedBy` 建系统级依赖 + 描述写清原因，别指望队员"应该知道"顺序
- **留一个验证任务**：依赖所有修改任务，确保全部完成后再跑编译/测试/lint

---

## 三层冲突预防

1. **任务拆分** — Lead 按文件边界切分，只读任务随意并行，写操作按文件集分工
2. **可选 Worktree 隔离** — `isolation: "worktree"`，文件系统层面消除冲突
3. **LLM 智能合并** — 收敛阶段 Lead 用 Bash 操作 git，遇冲突 ReadFile 检查、自行判断

---

## Coordinator Mode：让 Lead 专注调度

复杂多 Agent 任务中，Lead 一边协调一边自己写代码会出问题——改同一批文件产生冲突，上下文被任务列表和消息记录占满。所以可以让 Lead 专注于调度任务【剥夺其写、编辑文件的工具】

Coordinator Mode 是可选的纪律约束：

### 激活条件（双锁）

```
① COORDINATOR_MODE feature flag（开发者控制）
② MEWCODE_COORDINATOR_MODE 环境变量（用户显式 opt-in）
```

两把都开才进入。

### 工具集收窄

保留：Agent、SendMessage、TaskCreate/Get/List/Update、TeamCreate/Delete、ReadFile/Glob/Grep/Bash

剥夺：WriteFile、EditFile（Lead 不直接改代码）

Bash 保留是因为收敛阶段要跑 `git merge`；读类工具保留是因为 Synthesis 阶段要消化队员的研究结果写实施规格。

### 四阶段工作流

| 阶段 | 执行者 | 目的 |
|------|--------|------|
| Research | 队员（并行） | 调查代码库、定位问题 |
| **Synthesis** | **Lead** | 阅读调查结果，撰写实施规格 |
| Implementation | 队员 | 按规格修改代码 |
| Verification | 队员 | 测试改动 |

最关键的是 **Synthesis**——Lead 必须自己理解队员的研究结果，不能把理解委托给队员。

### 结果投递

队员完成后，Lead 收到 `<task-notification>`（含 agentId、status、summary、result、usage），再通过 `SendMessage` 续写队员：

```
spawn → 收 task-notification → synthesis → SendMessage 续写 → 循环
```

---

## 本章小结

核心设计选择：**协调机制是工具，不是基础设施。** AutoGen/CrewAI 的路子是搭调度器决定谁做什么；MewCode 反过来——把 TaskCreate、SendMessage、TaskUpdate 做成工具放进队员的工具集，让 LLM 自己拿主意。没有调度器，没有消息队列，文件邮箱 + 共享任务列表把队员粘起来。

SubAgent → Worktree → Agent Team → Coordinator Mode，引擎层具备了从单 Agent 到多 Agent 团队协作的完整光谱。
