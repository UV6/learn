# SWE-bench-Live 批量评测记录

> 评估时间: 2026-07-07  
> 使用模型: kimi-for-coding (默认配置)  
> Agent: Codia (本地终端 AI 编程助手)

---

## 概览

| # | Instance ID | 仓库 | 状态 | 轮次 | 工具调用 |
|---|------------|------|------|------|----------|
| 1 | `jhlywa__chess.js-546` | jhlywa/chess.js | ✅ 通过 (437/437) | - | - |
| 2 | `gpbl__react-day-picker-2816` | gpbl/react-day-picker | 待跑 | - | - |

---

## 任务 1: jhlywa__chess.js-546

### 任务详情

| 字段 | 值 |
|------|-----|
| **仓库** | [jhlywa/chess.js](https://github.com/jhlywa/chess.js) |
| **Base Commit** | `c57231d` |
| **编程语言** | TypeScript |
| **测试框架** | vitest |
| **FAIL_TO_PASS** | 1 个测试 |
| **PASS_TO_PASS** | 419 个测试 |

### 问题描述

调用 `chess.fen({ forceEnpassantSquare: true })` 时，即使上一步走了双步进兵（兵从第 2 行冲到第 4 行），FEN 字符串也不包含吃过路兵格。

```typescript
import { Chess } from 'chess.js'

const chess = new Chess()
chess.move("h2h4");   // 白方 h 兵双步进兵

console.log(chess.fen({ forceEnpassantSquare: true }));
// 实际输出 (bug):
// rnbqkbnr/pppppppp/8/8/7P/8/PPPPPPP1/RNBQKBNR b KQkq - 0 1
//                                                      ↑ ep 格缺失

// 期望输出:
// rnbqkbnr/pppppppp/8/8/7P/8/PPPPPPP1/RNBQKBNR b KQkq h3 0 1
//                                                      ↑ h3
```

**根因**：`forceEnpassantSquare` 为 true 的分支只在 `this._epSquare` 有效时才执行。但双步进兵后如果没有捕获者，`_epSquare` 就是空的，导致该分支被跳过。

### Codia 修复方案

Codia 在 `fen()` 方法中新增了一个 `else if (forceEnpassantSquare)` 分支：当没有合法的 `_epSquare` 时，从历史记录中找到最后一次 `BIG_PAWN` 移动（双步进兵的标志位），计算出吃过路兵格。

```diff
@@ -908,6 +908,20 @@ export class Chess {
+    } else if (forceEnpassantSquare) {
+      /*
+       * if there is no stored en passant square, check whether the last move
+       * was a double pawn push, so we can still show the ep square when the
+       * user explicitly requests it.
+       */
+      const lastHist = this._history[this._history.length - 1]
+      if (lastHist?.move.flags & BITS.BIG_PAWN) {
+        const epSq =
+          lastHist.move.color === 'b'
+            ? lastHist.move.to - 16
+            : lastHist.move.to + 16
+        epSquare = algebraic(epSq)
+      }
     }
```

**修复思路**：
1. 当 `forceEnpassantSquare` 为 true 但 `_epSquare` 为空时进入新分支
2. 检查最后一步是否是双步进兵（`BITS.BIG_PAWN` 标志）
3. 如果是，根据移动方颜色计算 ep 格：白方向下 16（e6 → e5），黑方向右 16
4. 将计算结果转换为代数表示法（如 "h3"）

### 与 Gold Patch 对比

| 对比维度 | Gold Patch | Codia Patch |
|----------|-----------|-------------|
| 新增内部字段 | `_fenEpSquare`（需在多处维护） | 无 |
| 修改行数 | ~30 行（改 7 处） | ~14 行（改 1 处） |
| 方案思路 | 在 fen 解析、走子、undo、reset 等多处维护新字段 | 从历史记录推导 ep 格 |
| 复杂度 | 较高，需要理解整个状态管理流程 | 较简洁，只在输出时计算 |
| 测试通过 | ✅ | ✅ |

### 测试结果

```
Test Files  37 passed (37)
     Tests  437 passed (437)
  Duration  1.64s
```

| 指标 | 值 |
|------|-----|
| FAIL_TO_PASS 测试 | ✅ 1/1 通过 |
| PASS_TO_PASS 测试 | ✅ 436/436 通过 |
| 新引入回归 bug | 0 |

---

## 工具调用统计

> 注：chess.js 使用旧版 runner 运行，未捕获详细 trace。以下为后续任务提供的信息结构。

每个任务的 `report.json` 将包含：

```json
{
  "instance_id": "xxx__xxx-000",
  "repo": "owner/repo",
  "model": "kimi-for-coding",
  "total_rounds": 5,
  "tool_calls": {
    "read_file": 3,
    "grep": 1,
    "edit_file": 1,
    "run_command": 1
  },
  "tool_call_count": 6,
  "patch_size_chars": 500,
  "patch_size_lines": 14
}
```

`trace.json` 将包含每一步的完整记录：
- 每一轮的思考内容（`type: "thinking"`）
- 每次工具调用的名称、参数、结果（`type: "tool_use"`, `"tool_result"`）
- Token 用量（`type: "usage"`）
- 停止原因（`type: "stopped"`）

---

## 待完成任务

### gpbl__react-day-picker-2816

| 字段 | 值 |
|------|-----|
| **仓库** | [gpbl/react-day-picker](https://github.com/gpbl/react-day-picker) |
| **Base Commit** | `9c7b2c6c` |
| **问题** | 日期范围模式下点击同一天会取消选择，而非完成范围选择 |
| **FAIL_TO_PASS** | 3 个测试 |
| **PASS_TO_PASS** | 569 个测试 |
| **安装命令** | `pnpm install ; pnpm build` |
| **测试命令** | `pnpm test -- --json --outputFile=jest-results.json` |

testbed 已就绪：`/tmp/swe-batch/gpbl__react-day-picker-2816/testbed/`

运行命令：
```bash
pnpm swe-bench:run \
  /tmp/swe-batch/gpbl__react-day-picker-2816/task.json \
  /tmp/swe-batch/gpbl__react-day-picker-2816/testbed \
  /tmp/swe-batch/gpbl__react-day-picker-2816
```
