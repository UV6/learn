# Anthropic 与 OpenAI Provider 接口对比

## 一句话理解

Anthropic 和 OpenAI 都能完成“对话、流式输出、调用工具、接收工具结果”，但它们使用不同的 HTTP 接口和消息协议。Codia 把这些差异封装在 Provider 层，对 Agent Loop 暴露统一的 `Message`、`Chunk` 和 `ToolCall`。

> 本文比较的是 Codia 当前实现使用的 Anthropic Messages API 与 OpenAI Chat Completions API，不代表两家公司全部最新 API 的完整能力。

## 整体对比

| 方面 | Anthropic | OpenAI |
|---|---|---|
| 请求地址 | `/v1/messages` | `/v1/chat/completions` |
| 鉴权 | `x-api-key` | `Authorization: Bearer` |
| 协议版本 | `anthropic-version` 请求头 | 当前实现没有对应请求头 |
| System Prompt | 请求体顶层 `system` | `messages` 中的 `system` 角色 |
| 工具定义 | `name/description/input_schema` | `type: function` + `function.parameters` |
| 工具调用 | `tool_use` 内容块 | `tool_calls[].function` |
| 工具参数 | JSON 对象 `input` | JSON 字符串 `arguments` |
| 工具结果 | user 消息中的 `tool_result` 内容块 | 独立的 `role: tool` 消息 |
| 文本增量 | `text_delta` | `choices[0].delta.content` |
| 工具参数增量 | `input_json_delta` | `delta.tool_calls[].function.arguments` |
| 并行工具区分 | 内容块顺序 | `tool_calls[].index` |
| Thinking | 当前实现支持 `thinking_delta` | 当前实现没有适配 reasoning/thinking |
| 用量字段 | `input_tokens/output_tokens` | `prompt_tokens/completion_tokens` |
| 结束 | `message_stop` | `finish_reason` 或 `[DONE]` |

## 请求与鉴权

### Anthropic

```http
POST /v1/messages
content-type: application/json
x-api-key: <apiKey>
anthropic-version: 2023-06-01
```

### OpenAI

```http
POST /v1/chat/completions
content-type: application/json
Authorization: Bearer <apiKey>
```

Codia 的 `ChatConfig` 统一保存 `protocol`、`model`、`baseUrl` 和 `apiKey`，Provider 再把相同配置转换成各自的 URL 和请求头。

## System Prompt 的位置

Anthropic 把 System Prompt 放在请求体顶层：

```json
{
  "system": [
    { "type": "text", "text": "你是一个编程助手" }
  ],
  "messages": []
}
```

OpenAI Chat Completions 把它插入消息数组：

```json
{
  "messages": [
    { "role": "system", "content": "你是一个编程助手" }
  ]
}
```

因此 Agent Loop 可以统一传入 `systemPrompt`，但两个 Provider 的 `buildRequestBody()` 必须分别处理。

## 工具定义

Codia 的 `ToolMeta` 采用接近 Anthropic 的格式：

```ts
{
  name: "read_file",
  description: "读取文件",
  input_schema: {
    type: "object",
    properties: {}
  }
}
```

Anthropic 可以基本直接使用。OpenAI 需要转换为 function tool：

```json
{
  "type": "function",
  "function": {
    "name": "read_file",
    "description": "读取文件",
    "parameters": {
      "type": "object",
      "properties": {}
    }
  }
}
```

这里的关键差异是 `input_schema` 被放进了 `function.parameters`。

## 模型发起工具调用

假设模型要调用：

```ts
read_file({ filePath: "src/app.ts" });
```

### Anthropic：结构化内容块

```json
{
  "role": "assistant",
  "content": [
    {
      "type": "tool_use",
      "id": "tool_123",
      "name": "read_file",
      "input": {
        "filePath": "src/app.ts"
      }
    }
  ]
}
```

`input` 已经是 JSON 对象。

### OpenAI：消息上的 function call

```json
{
  "role": "assistant",
  "tool_calls": [
    {
      "id": "call_123",
      "type": "function",
      "function": {
        "name": "read_file",
        "arguments": "{\"filePath\":\"src/app.ts\"}"
      }
    }
  ]
}
```

`arguments` 是包含 JSON 的字符串，因此 OpenAI Provider 需要累积字符串后执行 `JSON.parse()`。

## 工具结果回传

工具执行结果假设为：

```text
文件内容：console.log("hello")
```

### Anthropic

工具结果仍然是内容块，并放在 user 消息中：

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "tool_123",
      "content": "文件内容：console.log(\"hello\")"
    }
  ]
}
```

### OpenAI

工具结果是一条独立的 `tool` 角色消息：

```json
{
  "role": "tool",
  "tool_call_id": "call_123",
  "content": "文件内容：console.log(\"hello\")"
}
```

Codia 内部统一保留 `toolUseId`，交给各 Provider 转成 `tool_use_id` 或 `tool_call_id`。

## 流式事件

### 文本增量

Anthropic：

```json
{
  "type": "content_block_delta",
  "delta": {
    "type": "text_delta",
    "text": "你好"
  }
}
```

OpenAI：

```json
{
  "choices": [
    {
      "delta": {
        "content": "你好"
      }
    }
  ]
}
```

二者最后都映射为：

```ts
{ type: "text", content: "你好" }
```

### 工具参数增量

Anthropic 的流提供明确的工具内容块开始和参数增量：

```text
content_block_start(tool_use)
input_json_delta
input_json_delta
```

Codia 转成 `tool_use_start` 和 `tool_input_delta`，使用一个 `pendingTool` 累积。

OpenAI 把增量放在 `choices[0].delta.tool_calls[]` 中，每一段可能携带 `index`、`id`、`name` 或 `arguments`。Codia 转成 `openai_tool_delta`，再通过 `Map<number, PendingTool>` 按 `index` 分组，支持多个工具调用交错输出。

最终两个 Provider 都只向 Agent Loop提交统一事件：

```ts
{
  type: "tool_use",
  call: {
    id: "...",
    name: "read_file",
    input: { filePath: "src/app.ts" }
  }
}
```

## Thinking 和用量

Anthropic Provider 当前可以把 `thinking_delta` 映射为 Codia 的 `thinking` 事件，但只有没有工具列表时才启用 extended thinking：

```ts
body.thinking = {
  type: "enabled",
  budget_tokens: 4000
};
```

OpenAI Provider 当前没有处理 reasoning/thinking 事件。

用量字段也不同：

```text
Anthropic: input_tokens / output_tokens
OpenAI:    prompt_tokens / completion_tokens
```

Provider 最终统一转换成：

```ts
{
  inputTokens: number,
  outputTokens: number,
  model: string
}
```

## Codia 的统一层

```text
Codia Message / ToolMeta
          ↓
    Provider 适配层
    ┌──────┴──────┐
AnthropicProvider OpenAIProvider
    ↓               ↓
各自请求体、工具协议、SSE 事件
    └──────┬──────┘
           ↓
统一 Chunk / ToolCall / ToolResult
           ↓
        AgentLoop
```

统一接口是：

```ts
interface LLMProvider {
  readonly name: string;

  streamChat(
    messages: Message[],
    config: ChatConfig,
    signal: AbortSignal,
    tools?: Record<string, unknown>[],
    systemPrompt?: string,
  ): AsyncIterable<Chunk>;
}
```

Provider 层的价值是吸收厂商差异，使 Agent Loop、工具调度器和 TUI 不依赖具体 API。

## Codia 中的实现

- `src/provider/types.ts:3`：定义统一的 `ChatConfig`，通过 `protocol` 区分厂商。
- `src/provider/types.ts:12`：定义 Codia 内部统一的消息结构。
- `src/provider/types.ts:35`：定义 Provider 对外输出的统一 `Chunk`。
- `src/provider/types.ts:55`：定义 `LLMProvider.streamChat()`。
- `src/provider/factory.ts:6`：根据 `protocol` 创建 Anthropic 或 OpenAI Provider。
- `src/provider/anthropic.ts:9`：调用 Anthropic Messages API。
- `src/provider/anthropic.ts:56`：累积 Anthropic 工具参数增量。
- `src/provider/anthropic.ts:114`：构建 Anthropic 消息、工具结果和请求体。
- `src/provider/openai.ts:10`：调用 OpenAI Chat Completions API。
- `src/provider/openai.ts:56`：按 `index` 累积 OpenAI 工具调用。
- `src/provider/openai.ts:104`：构建 OpenAI 消息和请求体。
- `src/provider/openai.ts:174`：把 Codia 工具定义转换成 OpenAI function tool。
- `src/provider/openai.ts:185`：解析并提交完整 OpenAI 工具调用。
- `src/provider/sse.ts:102`：识别两种厂商的 SSE 数据并转换成 Codia 事件。

## 易错点

### 1. Codia 当前用的是 Chat Completions

OpenAI Provider 的路径是 `/v1/chat/completions`。本文不能直接套用到其他 OpenAI API 形态。

### 2. 两边的 `input` 表现不同

Anthropic 的工具 `input` 是对象，OpenAI 的 `function.arguments` 是 JSON 字符串。漏掉 `JSON.parse()` 会导致工具无法取得结构化参数。

### 3. System Prompt 不在同一位置

Anthropic 使用顶层 `system`，OpenAI Chat Completions 使用 `messages` 中的 `system` 角色。不能把同一个请求体直接发送给两家。

### 4. 内容块和消息角色是两种建模方式

Anthropic 更偏向用结构化内容块表达文本、工具调用和工具结果；OpenAI Chat Completions 更偏向用消息角色及 `tool_calls` 字段表达。

### 5. 统一 `Chunk` 仍含厂商中间事件

当前公共 `Chunk` 里还存在 `tool_use_start`、`tool_input_delta` 和 `openai_tool_delta`。它们是 Provider 拼接工具参数时的中间事件，而不是最终可执行的工具调用。

## 小结

- 两家提供相似能力，但 HTTP、鉴权、消息和工具协议不同。
- Anthropic 使用结构化内容块；OpenAI Chat Completions 使用消息角色和 function/tool calls。
- Anthropic 工具输入是对象；OpenAI 工具参数是 JSON 字符串。
- Provider 层负责双向翻译，并统一输出 `Chunk` 和 `ToolCall`。
- Agent Loop 因此不需要知道当前使用的是 Anthropic 还是 OpenAI。
