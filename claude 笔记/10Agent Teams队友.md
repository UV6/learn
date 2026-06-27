子 agent 没有通信能力，队友有，可以长期存活；通信方式，上下文共享不同
分为：
- 怎么进行通信（怎么读写）
- 怎么启动队友（Leader 启动队友，队友有自己的daemon 后台线程，有自己的基础工具集）。
- 执行流程：队友看自己的信箱，有消息就执行，完成后发送summary 到 Lead 信箱。
### 核心问题

"重构整个后端"涉及认证模块、数据库层、API 路由、测试。单个 Agent 的上下文窗口就那么大，修 API 路由时认证模块的细节早被压缩掉了。

s06 的子 Agent 是临时工——叫来干一件事，干完就走，没有通信能力。但有些任务需要能持续通信、能协作的队友。

### 子 Agent vs 队友

|      | s06 子 Agent            | s15 队友                           |
| ---- | ---------------------- | -------------------------------- |
| 生命周期 | 一次性，完成销毁               | 长期存活（教学版 10 轮，真实 CC 用 idle loop） |
| 通信   | 只回传最终结论                | 异步收件箱，随时收发                       |
| 上下文  | 完全隔离                   | 通过消息共享信息                         |
| 数量   | 1 个主 Agent + 偶尔子 Agent | 1 个 Lead + 多个并行队友                |

---

### MessageBus：文件收件箱

每个 Agent 有一个 `.jsonl` 邮箱文件。通信模型是**消费式**的——发消息就是 append 一行 JSON 到**对方**文件，读消息就是读整个文件然后删除：

```
Lead 发给 alice：  → .mailboxes/alice.jsonl 追加一行 {"from":"lead","to":"alice","content":"...","type":"message","ts":...}

alice 收消息：  → 读 .mailboxes/alice.jsonl → 获取所有消息 → 删除文件
```

为什么用文件而不是内存队列？**跨线程可观察、跨线程简单**。真实 CC 也用文件收件箱（`~/.claude/teams/{team}/inboxes/`），但加了 `proper-lockfile` **文件锁**防止并发写冲突。

---

### spawn_teammate_thread：**启动**队友

Lead 调用 `spawn_teammate` 启动一个队友。队友跑在自己的 daemon 线程里，拥有独立的 system prompt、独立的 messages、**简化但够用的工具集**（bash、read、write、send_message）：

```
spawn_teammate("alice", "backend dev", "创建数据库 schema 和迁移脚本")
```

每个队友的循环：

1. 检查收件箱，有消息就注入
2. 调用 LLM 决定下一步
3. 执行工具
4. 重复，最多 10 轮（教学版限流，真实 CC 用 idle loop）
5. 完成后自动发 summary 到 Lead 收件箱

**关键**：队友并行运行。Alice 在写 schema，Bob 同时在写客户端代码——互不阻塞。

---

### Lead 的收件箱注入

Lead 在每轮主循环结束后检查自己的收件箱。队友发来的消息注入到 history：

```
[Inbox]
From alice: Schema done: users, orders, products tables
From bob: Client written with TypeScript types
```

LLM 看到这些消息后可以决定下一步：合并、审查、或者分配新任务。

---

### 完整执行序列

```
1. Lead: "搭建后端，需要组队"
2. Lead → spawn_teammate("alice", "backend dev", "创建数据库 schema")
3. Lead → spawn_teammate("bob", "frontend dev", "写 API 客户端")
4. alice 线程 → LLM → bash "python manage.py migrate"      ← 并行
5. bob  线程 → LLM → write_file("client.ts", ...)           ← 并行
6. alice 完成 → BUS.send → "Schema done"
7. bob   完成 → BUS.send → "Client written"
8. Lead 下次循环 → inbox 注入 history → LLM 看到两个队友的结果
```

---

### real Claude Code 的额外机制

**15 种消息类型**：不只是简单的文本通信。真实 CC 有 `idle_notification`（队友完成一轮、进入空闲）、`permission_request/response`（权限冒泡）、`plan_approval_request/response`（计划审批）、`shutdown_request/approved/rejected`（体面关机）、`task_assignment`（任务分配）等结构化消息类型。

**权限冒泡**：队友遇到需要审批的操作时，不是自己弹窗——它发 `permission_request` 给 Lead 的收件箱，Lead 的 UI 显示审批对话框，用户审批后 Lead 回复 `permission_response` 给队友。审批通过文件系统而非进程内传递。

**团队配置**：`~/.claude/teams/{teamName}/config.json` 注册所有成员信息，包括 agentId、name、agentType、color（UI 颜色区分）。

**不能嵌套**：队友不能再 spawn 队友——CC 明确禁止"teammates spawning other teammates"。