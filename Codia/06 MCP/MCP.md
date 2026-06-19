怎么让 Agent 接入别人的工具，不用自己写一行代码，也不用重新编译，这就是 MCP
在 MCP 之前，Agent 想要接入工具，都要写对应的对接代码。有了 MCP，只要实现一次 MCP 客户端，工具实现一次 MCP 服务端，就能对接了

## MCP 的组成部分
![[Pasted image 20260612160240.png]]
### 为什么要这样拆？![[Pasted image 20260612160317.png]]

	其实可以理解为 USB，只要有一个 USB 接口（即 MCP Client），就能通过 mcp协议对接工具的 MCP。MCP 工具 = MCP Server 暴露出来的能力。所以写 MCP 工具的流程就是写一个 MCP Server
### 再看 mcp 协议
分为数据层、传输层![[Pasted image 20260612162426.png|697]]

####  MCP 是双向的，Client 也有自己的能力，不是只有 Server 提供能力
##### Server 暴露的能力
###### tool
 每个工具的名字、描述、输入输出参数定义，跟 tools 定义一样，只是 tool 在内部，mcp在外部
###### resource
只读数据，给 Agent 补背景知识
###### prompt
预定义的指令模板，引导 Agent 正确使用工具
相当于一份指导手册，告诉Server 怎么拿文本
##### Client 声明的能力
- Roots：告诉 Server 当前项目在哪  Host → Server
- Sampling：如果 Server 需要 LLM帮忙理解 Server → Host
- Elicitation：Server 信息不够，需要问用户  Server → Host → 用户
#### MCP 的传输方式：Client 和 Server 的通信方式
##### Stdio
Host 把 Server 作为一个子进程启动，通过stdin/stdout 管道读写消息，Server 本身可以访问远程消息，管道只管 host 和 Server 之间的通信
##### Streamable Http
把 Server作为一个独立的子进程启动，通过 http 进行通信，Server 可能在本机，也可能在云端![[Pasted image 20260612190927.png|537]]
stdio：本地工具，零配置
适用于 Server 运行在本机同一台机器上的场景。用户装个 npm 包就能用：
github:
  command: "npx"
  args: ["-y", "@modelcontextprotocol/server-github"]
例子：GitHub MCP Server、SQLite MCP Server、本地文件系统 Server。
优点是不需要端口、不需要网络配置、不需要认证、开箱即用。缺点是 Server 必须是可执行程序，而且只能在本机跑。

Streamable HTTP：远程工具，跨机器
适用于 Server 跑在另一台机器上或需要独立部署的场景：
remote-tool:
  url: "https://api.example.com/mcp"
  headers:
    Authorization: "Bearer ${API_TOKEN}"
例子：公司内部的统一 MCP 网关、SaaS 服务提供的 MCP 端点、需要多 Agent 共享的 Server。
优点是 Server 独立部署升级不依赖 Agent 重启、可以跨机器、可以做负载均衡。缺点是需要处理网络超时、TLS、认证刷新。

判断标准：Server 跑在哪

#### JSON-rpc 2.0 消息格式
MCP 不管用 stdio 还是 HTTP，消息格式统一用 JSON-RPC 2.0。文档形容它是"成熟到有些无聊"的协议，但正因简单所以好用。
只有三种消息类型
① 请求（Request） — 有 id，期望响应：

{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search_issues",
    "arguments": { "repo": "golang/go", "query": "generics" }
  }
}
② 响应（Response） — 有相同的 id，带 result 或 error：
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      { "type": "text", "text": "Found 42 issues..." }
    ]
  }
}
③ 通知（Notification） — 没有 id，不需要响应：

{
  "jsonrpc": "2.0",
  "method": "notifications/progress",
  "params": { "progressToken": "abc", "progress": 0.5 }
}

怎么区分
就看有没有 id 字段。有 id = 请求，没 id = 通知。就这么简单。
代码里的定义

JSONRPCMessage:
    jsonrpc: "2.0"
    id:      可选整数    // 请求/响应有，通知无
    method:  字符串       // 请求/通知有
    params:  任意        // 请求/通知的参数
    result:  任意        // 成功响应的结果
    error:   RPCError    // 失败响应的错误

注意 id 是可选的，序列化时如果为空就不输出这个字段。
为什么用它
不需要 .proto 文件，不需要代码生成。Python、Node、Rust、甚至 Bash — 只要能读写 JSON 就能参与。门槛极低，生态才能起来。

### 一次完整的 MCP 会话：初始化、发现、调用
---
整个流程：三类 MCP 方法，一种匹配机制
支持整个会话的 MCP 方法有三类：initialize、tools/list、tools/call，加上通知 notifications/initialized。另有 JSON-RPC id 做异步匹配。

---
① 初始化握手
**Client** 启动 Server 子进程后，先发 initialize 自我介绍：
// Client → Server
{
  "jsonrpc": "2.0", "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-11-25",
    "capabilities": { "roots": {} },
    "clientInfo": { "name": "MewCode", "version": "0.1.0" }
  }
}

Server 回自己的身份和能力：
// Client ← Server
{
  "jsonrpc": "2.0", "id": 1,
  "result": {
    "protocolVersion": "2025-11-25",
    "capabilities": { "tools": {}, "resources": {} },
    "serverInfo": { "name": "github-mcp", "version": "1.0.0" }
  }
}

Client 从 capabilities 字段知道这个 Server 支持 tools 和 resources，但不支持 prompts。
握手完成后，Client 再发一个通知（无 id，不等响应）：
// Client → Server
{ "jsonrpc": "2.0", "method": "notifications/initialized" }
两条规则：初始化完成前不能发业务请求；HTTP transport 下后续请求要带 MCP-Protocol-Version 头。

---
② 工具发现

Client 发 tools/list，无参数
// Client → Server
{ "jsonrpc": "2.0", "id": 2, "method": "tools/list" }

Server 返回所有工具定义：
// Client ← Server
{
  "jsonrpc": "2.0", "id": 2,
  "result": {
    "tools": [
      { "name": "search_issues", "description": "搜索 GitHub Issue", "inputSchema": {...} },
      { "name": "create_issue",  "description": "创建 GitHub Issue", "inputSchema": {...} }
    ]
  }
}

Codia 拿到后包装成 MCPToolWrapper 注册到 ToolRegistry。

---
③ 工具调用（可重复 N 次）
// Client → Server
{
  "jsonrpc": "2.0", "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search_issues",
    "arguments": { "repo": "golang/go", "query": "generics" }
  }
}

// Client ← Server
{
  "jsonrpc": "2.0", "id": 3,
  "result": {
    "content": [
      { "type": "text", "text": "Found 42 issues matching 'generics'..." }
    ]
  }
}
content 是数组，可含多个文本块，MCPToolWrapper 里的 extractText 把所有 text 类型块拼接成字符串返回。

---
异步匹配：id 怎么用
stdio 管道是单通道，Client 连续发 id=1 和 id=2，Server 可能先处理完 id=2 再回 id=1。靠 id 字段配对：

发送端：                         接收端（readLoop）：
id = nextID++                    msg = deserialize(line)
pending[id] = responseChan        if msg.id != null:
writeLine(stdin, msg)                pending[msg.id].send(msg)
response = responseChan.wait()

一个 pending 字典搞定所有异步匹配。通知无 id，直接跳过不匹配。

---
一句话概括
initialize → notifications/initialized → tools/list → (tools/call) × N
    │              │                          │                │
  只做一次       只做一次                    只做一次         重复 N 次

### 工具包装器
怎么让 Agent 调用 mcp 跟调用 tool 一样？用装饰器模式：如果两个接口不兼容，就用一个中间层做转化。用一个tool 接口来调用mcp 和 tool。
tool 里的参数有 name、description、参数、是否只读、破坏性、并发安全性、分类
而 mcp 里不一定有
就让工具类和 mcp 分别继承 tool 接口，mcp 没有的参数就留空，然后留出统一的 excute 执行方法来执行。
### 配置
让 codia 知道 mcp 在哪，分为项目级和用户级，项目级放在项目里，用户级放在对应的用户目录里，项目级可以覆盖用户级

### 从配置到调用
1. 读取配置文件 ，拿到 mcp server 列表
2. 选传输方式：stdio 还是 http
3. 后台连接 （启动时连接所有 Server，而不是 Agent 调用的时候才连接）
4. 握手初始化
5. 工具发现 tool/list 拿到每个 Server 的工具定义
6. 包装注册
7. Agent 看到工具
8. Agent 调用工具
9. 结果返回
注意点：启动时就要建立所有连接，让 Agent 知道有哪些 mcp

### 工具延迟加载
一个mcp 里有很多个工具，全交个 Agent 的话会分散注意力，所以在配置的时候要配置所有 mcp，但是加载（组装 prompt 的时候）的时候只加载 name，不用展示完整的工具结构
mcp 中的工具在经过包装后会有一个字段来表示是否是mcp中的工具，通过这个字段来区分始终加载和延迟加载
如果是有标记的，就只加载名字
模型看到名字之后按需拉取
拉取之后就返回完整的工具结构，并且这个工具下一轮就完整出现在工具列表里，不用再收