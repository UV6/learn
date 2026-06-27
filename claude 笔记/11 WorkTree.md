用 git 的 worktree 来隔离不同 agent 做的事情，在同一仓库中创建不同的目录

和 branch 的区别
- branch 是一个指针，切换 branch 会覆盖源码，单目录，切分支必须提交
- worktree 是物理隔离，会创建独立的文件夹。多目录，可以跑不同分支。
- Branch = 代码版本指针（逻辑）；Worktree = 代码落地文件夹（物理）。
- 一个分支可以没有 worktree，一个 worktree 必绑定一个分支。

