# 小帅旅游助手 - 智能AI旅游推荐系统

## 项目概述

基于自定义 ReAct Agent 架构的智能旅游助手系统，提供城市推荐、景点查询、路线规划等功能。采用 **Agent + Web + Frontend** 三层模块化架构，通过 gRPC 实现模块间通信。

### 核心特性

- **自定义 ReAct Agent 架构** - 无第三方 AI 框架依赖
- **深度思考展示** - 可折叠的思考过程框，实时展示 AI 推理过程
- **SSE 流式响应** - Token 级别实时输出，用户体验大幅提升
- **多协议 LLM 支持** - OpenAI、Claude、Gemini、Ollama 等
- **多会话管理** - 独立对话历史，会话隔离
- **模块化架构** - Agent/Web/Frontend 三层分离

### 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 16 + React 19 + TypeScript + Zustand + antd 6 |
| 后端 Web | FastAPI + Python 3.10+ |
| Agent | 自定义 ReAct 引擎 + gRPC |
| 部署 | 前后端分离 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端 (Frontend)                          │
│  Next.js 16 + React 19 + TypeScript + Zustand + antd 6          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ ChatArea    │  │ MessageList │  │ TaskSteps (思考展示)    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP SSE
┌─────────────────────────────────────────────────────────────────┐
│                       Web API (端口 8000)                        │
│  FastAPI + Python                                                │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────────┐  │
│  │ /chat/    │ │ /session/ │ │ /model/   │ │ /city/          │  │
│  │ stream    │ │           │ │           │ │                 │  │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────────┘  │
│                              │                                  │
│                              ▼ gRPC                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Agent Service (端口 50051)                    │
│  gRPC + 自定义 ReAct 引擎                                        │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ ReAct Agent                                                 │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐  │ │
│  │  │ Thought  │ │ Action   │ │ Observe  │ │ Memory       │  │ │
│  │  │ Engine   │ │ Executor │ │ Evaluator│ │ Manager      │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ LLM Client (支持多协议)                                     │ │
│  │  OpenAI / Anthropic / Google / Ollama / OpenAI-Compatible  │ │
│  └────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
ShuaiTravelAgent/
├── agent/                      # AI Agent 模块 (gRPC 服务, 端口 50051)
│   ├── src/
│   │   ├── core/               # ReAct 引擎核心
│   │   │   ├── react_agent.py  # ReAct Agent 实现
│   │   │   └── travel_agent.py # 旅游助手 Agent
│   │   ├── llm/                # 多协议 LLM 客户端
│   │   │   └── client.py       # LLM 客户端工厂
│   │   ├── tools/              # 工具模块
│   │   ├── environment/        # 环境数据
│   │   └── server.py           # gRPC 服务器
│   └── proto/
│       ├── agent.proto         # gRPC 服务定义
│       ├── agent_pb2.py        # 生成的消息类型
│       └── agent_pb2_grpc.py   # 生成的 gRPC 存根
│
├── web/                        # Web API 模块 (FastAPI, 端口 8000)
│   └── src/
│       ├── main.py             # FastAPI 应用入口
│       ├── routes/             # API 路由
│       │   ├── chat.py         # 流式聊天接口
│       │   ├── session.py      # 会话管理
│       │   ├── model.py        # 模型配置
│       │   ├── city.py         # 城市信息
│       │   └── health.py       # 健康检查
│       ├── services/           # 业务服务
│       │   ├── chat_service.py
│       │   └── session_service.py
│       ├── grpc_client/        # gRPC 客户端
│       ├── dependencies/       # 依赖注入
│       └── config/             # 配置管理
│
├── frontend/                   # Next.js 16 前端
│   └── src/
│       ├── app/                # App Router
│       │   └── page.tsx        # 主页面
│       ├── components/         # React 组件
│       │   ├── ChatArea.tsx    # 聊天区域
│       │   ├── MessageList.tsx # 消息列表
│       │   ├── Sidebar.tsx     # 侧边栏
│       │   └── TaskSteps.tsx   # 思考步骤展示
│       └── stores/             # Zustand 状态管理
│
├── config/                     # 配置文件
│   ├── llm_config.yaml         # 实际配置 (被 git 忽略)
│   └── llm_config.yaml.example # 配置模板
│
├── tests/                      # 测试用例
│   ├── test_sse_streaming.py   # SSE 流式传输测试
│   ├── test_e2e_streaming.py   # 端到端集成测试
│   ├── conftest.py             # pytest 配置
│   └── README.md               # 测试说明文档
│
├── docs/                       # 文档
│   ├── ARCHITECTURE.md         # 系统架构设计
│   ├── API.md                  # API 接口文档
│   ├── DEVELOP.md              # 开发指南
│   └── DEPLOY.md               # 部署指南
│
├── run_api.py                  # Web API 启动脚本
├── run_agent.py                # Agent 启动脚本
└── requirements.txt            # Python 依赖
```

---

## 快速开始

### 前置条件

- Python 3.10+
- Node.js 18+
- npm 9+

### 安装依赖

**后端依赖**：

```bash
pip install -r requirements.txt
```

**前端依赖**：

```bash
cd frontend
npm install
```

### 配置

1. 复制配置模板：

```bash
cp config/llm_config.yaml.example config/llm_config.yaml
```

2. 编辑配置文件，填入你的 API Key：

```bash
vim config/llm_config.yaml
```

### 启动服务

| 服务 | 命令 |
|------|------|
| Agent | `python run_agent.py` |
| Web API | `python run_api.py` |
| Frontend | `cd frontend && npm run dev` |

### 访问应用

- 前端：**http://localhost:3000**
- API 文档：**http://localhost:8000/docs**

---

## API 接口文档

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/ready` | 就绪检查 |
| GET | `/api/live` | 存活检查 |

**响应示例**：

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "agent": "connected",
  "services": {
    "api": "healthy",
    "database": "healthy",
    "agent": "healthy"
  }
}
```

### 流式聊天

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat/stream` | SSE 流式聊天 |

**请求参数**：

```json
{
  "message": "云南丽江旅游攻略",
  "session_id": "user-session-001"
}
```

**响应格式** (SSE)：

```
data: {"type": "session_id", "session_id": "user-session-001"}

data: {"type": "reasoning_start"}

data: {"type": "reasoning_chunk", "content": "[已思考 0.5秒]\n\n分析用户需求..."}

data: {"type": "reasoning_end"}

data: {"type": "answer_start"}

data: {"type": "chunk", "content": "云南"}

data: {"type": "chunk", "content": "丽江"}

data: {"type": "chunk", "content": "是"}

...

data: {"type": "done", "stats": {"tokens": 482, "duration": 17.087}}
```

### 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/session/new` | 创建新会话 |
| GET | `/api/sessions` | 列出所有会话 |
| DELETE | `/api/session/{session_id}` | 删除会话 |
| PUT | `/api/session/{session_id}/name` | 更新会话名称 |
| PUT | `/api/session/{session_id}/model` | 设置会话模型 |
| GET | `/api/session/{session_id}/model` | 获取会话模型 |
| POST | `/api/clear/{session_id}` | 清除聊天记录 |

### 模型管理

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models` | 列出可用模型 |
| GET | `/api/models/{model_id}` | 获取模型详情 |

### 城市信息

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/cities` | 列出城市（支持过滤） |
| GET | `/api/cities/{city_id}` | 获取城市详情 |
| GET | `/api/cities/{city_id}/attractions` | 获取城市景点 |
| GET | `/api/regions` | 列出地区 |
| GET | `/api/tags` | 列出标签 |

---

## SSE 流式接口

### SSE 事件类型

| 事件类型 | 说明 | 数据结构 |
|----------|------|----------|
| `session_id` | 会话标识 | `{"type": "session_id", "session_id": "..."}` |
| `reasoning_start` | 思考过程开始 | `{"type": "reasoning_start"}` |
| `reasoning_chunk` | 思考内容片段 | `{"type": "reasoning_chunk", "content": "..."}` |
| `reasoning_end` | 思考过程结束 | `{"type": "reasoning_end"}` |
| `answer_start` | 答案开始生成 | `{"type": "answer_start"}` |
| `chunk` | 答案内容片段 | `{"type": "chunk", "content": "..."}` |
| `error` | 错误信息 | `{"type": "error", "content": "..."}` |
| `heartbeat` | 心跳保活 | `{"type": "heartbeat", "timestamp": "..."}` |
| `done` | 传输完成 | `{"type": "done", "stats": {...}}` |

### 前端集成示例

```typescript
import { useState, useCallback } from 'react';

interface SSEEvent {
  type: string;
  content?: string;
  session_id?: string;
  stats?: { tokens: number; duration: number };
}

export function useChatStream() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  const sendMessage = useCallback(async (message: string, sessionId?: string) => {
    setIsStreaming(true);
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId }),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) return;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const text = decoder.decode(value);
      const lines = text.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const event: SSEEvent = JSON.parse(line.slice(6));

            switch (event.type) {
              case 'chunk':
                // 更新消息内容
                setMessages(prev => {
                  const last = prev[prev.length - 1];
                  if (last?.role === 'assistant') {
                    return [...prev.slice(0, -1), {
                      ...last,
                      content: last.content + (event.content || '')
                    }];
                  }
                  return [...prev, { role: 'assistant', content: event.content || '' }];
                });
                break;

              case 'done':
                setIsStreaming(false);
                console.log('完成:', event.stats);
                break;
            }
          } catch (e) {
            // 忽略解析错误
          }
        }
      }
    }
  }, []);

  return { sendMessage, isStreaming, messages };
}
```

---

## gRPC 服务定义

### 服务接口

```protobuf
service AgentService {
  // 处理用户消息
  rpc ProcessMessage (MessageRequest) returns (MessageResponse);

  // 流式处理用户消息
  rpc StreamMessage (MessageRequest) returns (stream StreamChunk);

  // 健康检查
  rpc HealthCheck (HealthRequest) returns (HealthResponse);
}
```

### 消息类型

```protobuf
message MessageRequest {
  string session_id = 1;
  string user_input = 2;
  string model_id = 3;
  bool stream = 4;
}

message MessageResponse {
  bool success = 1;
  string answer = 2;
  ReasoningInfo reasoning = 3;
  string error = 4;
  repeated HistoryStep history = 5;
}

message StreamChunk {
  string chunk_type = 1;  // "thinking_start", "thinking_chunk", "thinking_end", "answer_start", "answer", "done", "error"
  string content = 2;
  bool is_last = 3;
}
```

---

## 配置说明

### 配置文件

```
config/
├── llm_config.yaml         # 实际使用的配置文件
└── llm_config.yaml.example # 配置模板
```

### 支持的 Provider

| provider | 说明 |
|----------|------|
| `openai` | OpenAI GPT 系列 |
| `anthropic` | Anthropic Claude 系列 |
| `google` | Google Gemini 系列 |
| `ollama` | Ollama 本地模型 |
| `openai-compatible` | 兼容 OpenAI API 的自定义服务 |

### 配置示例

```yaml
# 默认使用的模型ID
default_model: gpt-4o-mini

# 模型配置列表
models:
  gpt-4o-mini:
    name: "GPT-4o Mini"
    provider: openai
    model: "gpt-4o-mini"
    api_base: "https://api.openai.com/v1"
    api_key: "sk-xxx"
    temperature: 0.7
    max_tokens: 2000
    timeout: 30
    max_retries: 3

  claude-3-5-sonnet:
    name: "Claude 3.5 Sonnet"
    provider: anthropic
    model: "claude-sonnet-4-20250514"
    api_base: "https://api.anthropic.com/v1"
    api_key: "sk-ant-xxx"
    temperature: 0.7
    max_tokens: 2000
    timeout: 60
    max_retries: 3

  ollama-llama3:
    name: "Llama 3 (Ollama)"
    provider: openai-compatible
    model: "llama3"
    api_base: "http://localhost:11434/v1"
    api_key: ""
    temperature: 0.7
    max_tokens: 2000
    timeout: 120
    max_retries: 2

# Agent 配置
agent:
  name: "TravelAssistantAgent"
  max_steps: 10
  max_reasoning_depth: 5
  max_working_memory: 10
  max_long_term_memory: 50

# Web 服务配置
web:
  host: "0.0.0.0"
  port: 8000
  debug: true

# gRPC 服务配置
grpc:
  host: "0.0.0.0"
  port: 50051
```

---

## v3.0.0 功能特性

### SSE 流式响应

- **真正的流式传输**，非批量处理
- **Token 级别实时输出**，平均间隔 80-90ms
- **流畅的逐字显示效果**
- **支持停止控制**，用户可随时中断生成

### v3.0.0 流式性能测试结果

| 指标 | 测试值 | 说明 |
|------|--------|------|
| 总 Chunk 数 | 482 | 单次请求输出的 Token 块数 |
| 传输时长 | 17.087s | 从首 Token 到完成的总耗时 |
| 平均间隔 | 80-90ms | 相邻 Token 之间的等待时间 |
| 传输效率 | 约 28 tokens/s | 稳定的数据流输出 |

### 深度思考展示

- 可折叠的思考过程框
- 实时展示 AI 推理过程
- 透明化的决策流程

### 自定义 ReAct Agent

- 无第三方 AI 框架依赖
- 完整的状态机实现
- 灵活的工具注册机制
- 思考/行动/观察/评估循环

---

## 测试

### 运行测试

```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_sse_streaming.py -v

# 运行特定测试类
pytest tests/test_sse_streaming.py::TestSSEStreaming -v

# 运行特定测试方法
pytest tests/test_sse_streaming.py::TestSSEStreaming::test_token_streaming -v

# 生成测试报告
pytest tests/ --html=report.html
```

### 测试要求

- Web API 服务器运行在端口 8000
- gRPC 服务器运行在端口 50051
- Python 3.10+
- pytest-asyncio
- httpx

### 测试文件说明

| 文件 | 说明 |
|------|------|
| `tests/test_sse_streaming.py` | SSE 流式传输核心测试用例 |
| `tests/test_e2e_streaming.py` | 端到端集成测试和性能测试 |
| `tests/conftest.py` | Pytest 配置和共享 fixtures |
| `tests/README.md` | 测试详细说明文档 |

---

## 文档

详细文档请参阅 `docs/` 目录：

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统架构设计 |
| [API.md](docs/API.md) | API 接口文档 |
| [DEVELOP.md](docs/DEVELOP.md) | 开发指南 |
| [DEPLOY.md](docs/DEPLOY.md) | 部署指南 |

---

## 更新日志

### v3.0.0

- **SSE 流式响应** - Token 级别实时输出，用户体验大幅提升
  - 真正的流式传输，非批量处理
  - 平均 Token 间隔 80-90ms，流畅的逐字显示效果
  - 支持停止控制，用户可随时中断生成
- **深度思考展示** - 可折叠的思考过程框
- 自定义 ReAct Agent 架构 - 无第三方 AI 框架依赖
- **Agent/Web/Frontend 三层分离** - gRPC 模块间通信
- 多协议 LLM 支持 - OpenAI、Claude、Gemini、Ollama 等
- 多会话管理 - 独立对话历史，会话隔离

---

## 许可证

MIT License
