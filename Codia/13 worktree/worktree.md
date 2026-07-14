# Git Worktree 并行隔离 总结

Worktree 补上了 SubAgent 缺失的最后一块拼图：**文件系统级隔离**。SubAgent 隔离了上下文（消息、权限、缓存），Worktree 隔离了文件——两者结合，子 Agent 才拥有真正独立的工作环境。

---

## 为什么需要 Worktree

### 问题：并行 Agent 的文件冲突

前台子 Agent 没这个问题（主 Agent 等它跑完），但**后台子 Agent**和下一章的 **Agent Team 队员**是并行的，共享同一个文件系统。

两个 Agent 同时改 `server.py`：

- 可能读到对方写了一半的文件
- 可能互相覆盖修改
- 最终文件变成拼接怪物

这和两个程序员同时改同一个文件完全一样。

### 为什么分支不够？

分支提供的是**【时间】维度**的隔离（不同时间点的代码快照），一个时刻只有一个工作目录。切分支时工作目录跟着变，两个 Agent 没法同时在不同分支工作。而且切分支会刷新文件 mtime，触发增量构建工具大规模重编。

需要的是**【空间】维度**的隔离：同一时间存在多个独立工作目录。

---

## Git Worktree 原理

`git worktree add ../my-project-feature feature-a` 之后，文件系统里有**两个独立的工作目录**，共享同一个 `.git` 仓库：

```
./project/             → main 分支，server.py = A
./project-feature/     → feature 分支，server.py = B
```

两个 Agent 同时在各自目录工作，互不影响。版本历史统一——一个 Worktree 的 commit 在另一个里 `git log --all` 也能看到。

**共享仓库，隔离文件。** 这正是并行 Agent 需要的。

---

## Codia 的 Worktree 管理

### WorktreeManager 状态

```
WorktreeManager:
    repoRoot        → 主仓库路径
    worktreeDir     → Worktree 统一放在 .codia/worktrees/
    active          → name → Worktree 的映射
    currentSession  → 当前活跃的 Worktree 会话
·```

Session 的结构会记录进入前的状态，退出时才能恢复：

```
WorktreeSession:
    originalCwd         → 进入前的工作目录
    worktreePath        → Worktree 路径
    worktreeName        → Slug 名称
    originalBranch      → 进入前所在的分支
    originalHeadCommit  → 进入时的 HEAD commit SHA
    sessionId           → 会话 ID
    hookBased           → 是否由 Hook 创建
```

Session 持久化到 `.mewcode/worktree_session.json`，进程意外退出后 `--resume` 可直接恢复，不用重建。

### Slug 安全验证
slug 是一种规范，全部小写，并用-连接。

Worktree 名称会被用作目录名和分支名。LLM 生成的输入不可信——`../../etc/passwd` 这样的名称会导致经典的路径遍历攻击。

验证规则：
- 只允许 `[a-zA-Z0-9._-]`
- 总长度 ≤ 64
- 支持 `/` 作嵌套分隔（如 `team-refactor/alice`），每段独立校验
- `.` 和 `..` 显式拒绝

Slug 中的 `/` 转换为分支名时替换为 `+`，避开 Git D/F 命名冲突：`team-refactor/alice` → `worktree-team-refactor+alice`

### 创建 Worktree — 六步流程

创建一个 Worktree 从验证名称到持久化状态，一共六步。下面用伪代码逐步展开：

---

**① 验证名称**

防止 LLM 生成的不可信输入导致路径遍历攻击：

```text
function createWorktree(manager, name, baseBranch):
    err = validateSlug(name)     // 只允许 [a-zA-Z0-9._-]，≤64 字符，拒绝 . 和 ..
    if err: return err
```

---

**② 检查重复**

加锁后在 active 映射里查是否已有同名 Worktree，有就直接返回：

```text
    if name in manager.active:
        return error("worktree already exists: " + name)
```

---

**③ 构建路径和分支名**

把 slug 转换为文件系统路径和 Git 分支名：

```text
    flatSlug   = replace(name, "/", "+")              // team-refactor/alice → team-refactor+alice
    wtPath     = joinPath(manager.worktreeDir, flatSlug)  // .mewcode/worktrees/team-refactor+alice
    branchName = "worktree-" + flatSlug               // worktree-team-refactor+alice
```

- `/` 替换为 `+`，避开 Git D/F 命名冲突
- 目录统一放 `.codia/worktrees/` 下（已在 `.gitignore` 中，不会被 Git 追踪）
- 分支名加 `worktree-` 前缀，在 `git branch` 输出里一眼能认出是 MewCode 创建的

---

**③.5 快速恢复**

当SubAgent 反复进出同一个 Worktree，就需要快速验证
在真正调 `git worktree add` 之前，先检查目标目录是否已经存在且可用。如果存在，直接复用，省掉数秒的 git 全量检出：

```text
    headSha = readWorktreeHeadSha(wtPath)   // 纯文件系统读取，不调 git 子进程
    if headSha is not null:
        return existingWorktree(wtPath, branchName, headSha)
```

具体做法：
1. 读 Worktree 目录下的 `.git` 指针文件 → 得到真实 `gitdir` 路径
2. 读 `gitdir/HEAD` → 如果是符号引用 `ref: refs/heads/...`，继续读 `refs/` 目录 → 还原出 commit SHA
3. 整个过程只有几次文件读取，约 **3ms**。而 `git worktree add` 在大仓库上需要数秒（检出全量文件树 + 写入工作目录）

Agent 反复进出同一个 Worktree 的场景下，这个优化省下的时间非常可观。

---

**④ 执行 `git worktree add`**

快速恢复没命中，才真正走 git 创建：

```text
    env = {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": ""}
    run("git", "worktree", "add", "-B", branchName, wtPath, baseBranch,
        workDir=manager.repoRoot, env=env, stdin="ignore")
```

几个关键细节：

- `-B` 而不是 `-b`：**不存在则创建分支，已存在则强制重置分支到指定节点**。如果上次没清理干净留下孤儿分支，`-b` 会报错，`-B` 直接覆盖
- `GIT_TERMINAL_PROMPT=0`：防止 Git 需要输入凭证时进程挂起等待用户输入
- `GIT_ASKPASS=''` + `stdin: "ignore"`：双重保险，确保不会阻塞

---

**⑤ 创建后设置（四项初始化）**

`git worktree add` 只创建了干净的工作目录，缺少主仓库已有的运行时依赖。四项初始化补上：

- **A. 复制本地配置** — `settings.local.json`（密钥等不入库配置）从主仓库复制过来
- **B. 配置 Git Hooks** — 显式检测主仓库 hooks 路径（优先 `.husky/`，回退 `.git/hooks/`）并设置到 Worktree 的 git config，否则 `git commit` 不会触发 pre-commit/lint/格式化
- **C. 软链接大目录** — `node_modules`、`.venv`、`vendor` 共享到主仓库，避免每个 Worktree 复制几百 MB。需链接的目录列表从配置读取。⚠️ 不万能：Node 默认解析 symlink 到真实路径，`__dirname` 可能拿到主仓库路径
	- **D. 复制被忽略但需要的文件** — `.env` 等被 `.gitignore` 忽略的文件通过 `.worktreeinclude` 文件（gitignore 语法）指定复制。此步骤 best-effort，失败只记警告

---

**⑥ 记录状态并持久化**

```text
    wt = new Worktree(name, wtPath, branchName, baseBranch, resolveHead(wtPath), now())
    manager.active[name] = wt
    saveWorktreeSession(manager.currentSession)
    return wt
```

把 Worktree 加入 active 映射，同时持久化 session 到 `.mewcode/worktree_session.json`，进程意外退出后 `--resume` 可直接恢复。

#### 创建后设置（⑤）— 四项初始化

**A. 复制本地配置** — `settings.local.json`（密钥等不入库配置）从主仓库复制过来

**B. 配置 Git Hooks** — Worktree 不自动继承 `core.hooksPath`，需显式检测（优先 `.husky/`，回退 `.git/hooks/`）并设置，否则 `git commit` 不会触发 pre-commit/lint/格式化

**C. 软链接大目录** — `node_modules`、`.venv`、`vendor` 占几百 MB，每个 Worktree 复制迅速耗尽磁盘。软链接到主仓库，共享依赖。需链接的目录列表从配置读取，不能写死

⚠️ 软链接不万能：Node 默认解析 symlink 到真实路径，`__dirname` 可能拿到主仓库路径。遇到问题开 `--preserve-symlinks`

**D. 复制被忽略但需要的文件** — `.env` 被 `.gitignore` 忽略，`git worktree add` 不复制。通过 `.worktreeinclude` 文件（gitignore 语法）定义哪些被忽略的文件要复制。此步骤是 best-effort，失败只记警告

### 进入 Worktree — 不改进程 cwd

cwd 当前工作目录，chdir 修改当前工作目录

**关键设计决策：不 `chdir`，而是把 Worktree 路径【记到】会话状态，让每次工具调用显式取 cwd。**

为什么不 `chdir`？进程级 cwd 是全局可变状态，Bash 工具偶尔 `cd`、后台子 Agent 并发——时序问题会让 cwd 变成所有并发组件的同步点。

显式 cwd 的做法：

```
enterWorktree → 记录 session（不 chdir，不清缓存）
    ↓
工具调用时 → 从 session 取 Worktree 路径作为 cwd
```

好处：
- 并发调多个工具？每次都从 session 单独取，互不干扰
- 子 Agent 又开新 Worktree？有自己的 session
- 文件缓存？key 用绝对路径，主目录和 Worktree 里的同名文件 key 不同，**天然不冲突，不需要清缓存**

### 退出 Worktree — 变更保护

退出时有一个选择：保留还是删除。如果选删除且 Worktree 里有**未提交的修改**或**新增 commit**，`discardChanges` 参数要求调用方显式确认。

```
exitWorktree:
    ① 变更检查 → 有变更且未设 discardChanges → 拒绝
    ② chdir 回 originalCwd（兜底，防止某个 Bash 改过进程 cwd）
    ③ 清 session + 持久化为 null（--resume 正确工作的前提）
    ④ 如 action=remove → git worktree remove + git branch -D
```

两条 git 命令之间 `sleep(100ms)`，防止 lockfile 未释放。生产环境更稳妥的做法是带重试的指数退避。

### 自动清理

子 Agent 场景不需要手动决定保留/删除。逻辑很简单：

```
autoCleanup:
    有未提交修改或有新 commit → 保留
    没有 → 自动删除
```

`hasWorktreeChanges` 的实现是 fail-closed 的：如果 `git status --porcelain` 或 `git rev-list` 命令本身执行失败，默认返回 true（有变更），宁可多保留一个目录也不误删。

用户手动 `/worktree create` 的不走自动清理。

### 过期 Worktree 的后台清理

子 Agent 异常退出（崩溃、被强制终止），Worktree 会变成孤儿堆积在磁盘上。通过**命名模式**区分临时和手动：

- `agent-a[0-9a-f]{7}` — SubAgent 创建的，过期可清理
- `wf_[0-9a-f]{8}-...` — 工作流创建的，过期可清理
- 手动命名的 — 永不清理

三层过滤漏斗：

```
① 匹配临时命名模式（只清理 agent-a*/wf_*）
    → ② 跳过当前使用中和未过期的
    → ③ fail-closed：有变更或有未推送 commit → 不删
    → 安全删除
```

宁可多占磁盘，也不丢失可能有价值的工作成果。

---

## 与 SubAgent 的配合

通过 Agent 定义的 `isolation` 字段串联：

```yaml
# .mewcode/agents/refactor-worker.md
---
name: refactor-worker
isolation: worktree
---
```

`isolation: worktree` 时，完整的执行流程：

```
① 创建 Worktree（agent- 前缀 + 随机 ID）
② 注入上下文通知（告知子 Agent 在隔离副本中，路径需翻译，编辑前重新读取文件）
③ 创建子 Agent，工作目录 = Worktree 路径
④ runToCompletion 执行
⑤ autoCleanup：无修改删除，有修改保留并返回路径/分支名给主 Agent
⑥ 返回结果给主 Agent review
```

**上下文通知**是关键——没有它，子 Agent 不知道自己在隔离副本，可能直接用父 Agent 传来的主目录路径去读写文件。

可以在 Worktree 里放心用 `git add -A`，因为里面只有子 Agent 的改动，不存在主仓库敏感文件混入问题。

---

## 本章小结

- **分支 = 时间隔离，Worktree = 空间隔离**，后者才是并行 Agent 需要的
- **显式 cwd 代替 chdir**：避免进程级全局状态引发的并发问题
- **快速恢复**：不调 git 子进程，直接读文件系统，3ms vs 数秒
- **变更保护**：退出时默认拒绝丢弃未提交的修改
- **自动清理 + 过期清理**：命名模式区分临时/手动，fail-closed 不误删
- **与 SubAgent 配合**：`isolation: worktree` 让子 Agent 拥有物理隔离的工作目录

有了 SubAgent + Worktree，下一章就可以让多个子 Agent 真正并行工作了。



