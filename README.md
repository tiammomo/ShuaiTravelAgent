# 小帅旅游助手 - 智能AI旅游推荐系统

## 项目概述

一个基于自定义ReAct Agent架构的智能旅游助手系统，集成GPT-4o-mini大模型，提供城市推荐、景点查询、路线规划等功能。

项目采用**Python后端（FastAPI）+ React前端**的现代技术栈，支持SSE流式响应、多会话管理、深度思考过程展示等功能。

### 核心特性

- ✅ **自定义ReAct Agent架构** - 无第三方AI框架依赖，完整的推理-行动循环
- ✅ **深度思考展示** - 可折叠的思考过程框，类似DeepSeek的展示方式
- ✅ **流式响应处理** - SSE实时流式输出，支持停止控制
- ✅ **多协议LLM支持** - OpenAI、Claude、Gemini、本地模型等
- ✅ **多会话管理** - 独立的对话历史和Agent实例，会话隔离
- ✅ **现代化前端** - React 18 + TypeScript + Ant Design + Vite
- ✅ **完整API接口** - FastAPI Swagger文档

---

## 项目结构

```
ShuaiTravelAgent/
├── src/shuai_travel_agent/              # 后端核心包
│   ├── agent.py                         # ReAct Agent主体（推理-行动循环）
│   ├── config_manager.py                # 配置和知识库管理
│   ├── llm_client.py                    # LLM多协议客户端
│   ├── memory_manager.py                # 记忆系统
│   ├── reasoner.py                      # 推理和规划引擎
│   ├── environment.py                   # 环境交互和工具调用
│   ├── io_handler.py                    # 输入输出处理和日志
│   ├── logger_manager.py                # 日志管理系统
│   └── app.py                           # FastAPI Web服务
│
├── frontend/                            # React前端
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatArea.tsx             # 主聊天区域
│   │   │   ├── MessageList.tsx          # 消息列表组件
│   │   │   └── Sidebar.tsx              # 侧边栏（会话管理）
│   │   ├── context/
│   │   │   └── AppContext.tsx           # 全局状态管理
│   │   ├── services/
│   │   │   └── api.ts                   # API服务
│   │   ├── types/
│   │   │   └── index.ts                 # TypeScript类型定义
│   │   ├── App.tsx                      # 主应用组件
│   │   └── main.tsx                     # 入口文件
│   ├── package.json                     # npm依赖配置
│   ├── vite.config.ts                   # Vite构建配置
│   └── index.html                       # HTML模板
│
├── config/
│   ├── config.json                      # 项目配置（需自行创建）
│   └── llm_config_examples.json         # 多协议配置示例
│
├── run_api.py                           # 后端启动脚本
├── requirements.txt                     # Python依赖
└── README.md                            # 本文档
```

---

## 快速开始（5分钟）

### 前置条件

- Python 3.8+
- Node.js 16+
- npm 8+

### 第1步：安装依赖

**后端依赖**：
```bash
pip install -r requirements.txt
```

**前端依赖**（首次运行）：
```bash
cd frontend
npm install
cd ..
```

### 第2步：配置API密钥

创建 `config/config.json`：
```json
{
  "agent_name": "TravelAssistantAgent",
  "llm": {
    "provider_type": "openai",
    "api_key": "YOUR_API_KEY_HERE",
    "model": "gpt-4o-mini"
  },
  "web": {
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

### 第3步：启动服务

**终端1 - 启动后端API**：
```bash
python run_api.py
```

**终端2 - 启动React前端**：
```bash
cd frontend
npm run dev
```

### 第4步：访问应用

打开浏览器访问：**http://localhost:3000**

---

## 功能说明

### 后端功能

| 模块 | 功能 | 说明 |
|------|------|------|
| **Agent** | 核心推理 | ReAct推理→行动循环 |
| **Reasoner** | 意图识别 | 识别用户意图并生成执行计划 |
| **MemoryManager** | 记忆管理 | 工作记忆、长期记忆 |
| **LLMClient** | 模型调用 | 支持OpenAI/Claude/Gemini等多种模型 |
| **Environment** | 工具调用 | 城市查询、景点推荐、路线规划 |
| **ConfigManager** | 配置管理 | 内置旅游知识库（多城市多景点） |
| **LoggerManager** | 日志管理 | 结构化日志、trace ID追踪 |
| **IOHandler** | 输入输出 | 格式化处理、日志记录 |

### 前端功能

- **✅ 深度思考展示** - 可折叠的思考过程框，默认折叠只显示加载动画
- **✅ 流式回答** - AI回答逐字流式显示
- **✅ 停止控制** - 随时中断生成
- **✅ 会话管理** - 创建、切换、删除、重命名对话
- **✅ 智能会话命名** - 首次发送自动命名
- **✅ 会话隔离** - 不同会话消息完全独立
- **✅ 消息缓存** - 切换会话保留原会话历史
- **✅ 响应式设计** - 适配各种屏幕尺寸
- **✅ Markdown渲染** - 支持富文本格式显示

---

## 深度思考功能

### 交互流程

```
用户提问
    ↓
显示"深度思考中"加载动画（默认折叠）
    ↓
用户可点击展开查看思考过程
    ↓
思考过程流式实时显示
    ↓
思考完成，显示正式回答
    ↓
思考框可继续展开/折叠查看
```

### 界面特点

- **默认状态**：只显示紫色加载动画圆圈
- **点击展开**：显示完整的思考过程内容
- **实时流式**：思考内容边生成边显示
- **完成状态**：显示"深度思考"标签，可继续查看

---

## 会话管理详解

### 工作流程

```
1. 新建会话
   └─ 创建空会话

2. 首次发送消息
   └─ 自动将问题前15个字符作为会话名称
   └─ 会话添加到历史列表

3. 会话切换
   └─ 完整保留原会话的所有消息和思考过程
   └─ 加载目标会话的历史消息
   └─ 清空当前流式状态

4. 会话删除
   └─ 从列表移除，不会显示"No Data"

5. 会话重命名
   └─ 点击铅笔图标修改
```

### 内存管理

- **会话消息缓存** - 每个会话的消息在内存中独立存储
- **自动同步** - 添加/删除/切换消息时自动更新
- **会话隔离** - 不同会话之间消息完全独立，无干扰
- **状态重置** - 切换会话时自动清空流式状态

---

## 支持的用户意图

```
city_recommendation  - 城市推荐
attraction_query     - 景点查询
route_planning       - 路线规划
preference_update    - 偏好更新
general_chat         - 一般对话
```

---

## 配置说明

### config.json 配置

**基础配置**（必需）：
```json
{
  "agent_name": "TravelAssistantAgent",
  "version": "2.0.0",
  "llm": {
    "provider_type": "openai",
    "api_key": "YOUR_API_KEY_HERE",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "web": {
    "host": "0.0.0.0",
    "port": 8000
  }
}
```

### 多协议LLM支持

项目支持多种大语言模型API协议：

**1. OpenAI**
```json
{
  "provider_type": "openai",
  "api_base": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "model": "gpt-4o-mini"
}
```

**2. Anthropic Claude**
```json
{
  "provider_type": "anthropic",
  "api_key": "sk-ant-...",
  "model": "claude-3-haiku-20240307"
}
```

**3. Google Gemini**
```json
{
  "provider_type": "google",
  "api_key": "AIzaSy...",
  "model": "gemini-pro"
}
```

**4. 本地模型（Ollama/LM Studio）**
```json
{
  "provider_type": "openai-compatible",
  "api_base": "http://localhost:11434/v1",
  "api_key": "not-needed",
  "model": "llama2"
}
```

详见 `config/llm_config_examples.json` 了解更多配置选项。

---

## API接口

### 基础URL

```
http://localhost:8000
API文档：http://localhost:8000/docs
```

### 核心接口

**1. 流式聊天（SSE）**
```bash
POST /api/chat/stream
Content-Type: application/json

{
  "message": "推荐适合春天旅游的城市",
  "session_id": "optional-session-id"
}

Response: SSE流式输出
- type: session_id      - 会话ID
- type: reasoning_start - 思考开始
- type: reasoning_chunk - 思考过程内容
- type: reasoning_end   - 思考结束
- type: answer_start    - 回答开始
- type: chunk           - 回答内容
- type: done            - 完成
```

**2. 会话管理**
```bash
POST /api/session/new           # 创建新会话
GET /api/sessions               # 获取会话列表（过滤空会话）
DELETE /api/session/{id}        # 删除会话
PUT /api/session/{id}/name      # 重命名会话
POST /api/clear                 # 清空对话
GET /api/session/{id}/model     # 获取会话模型
PUT /api/session/{id}/model     # 设置会话模型
```

**3. 模型管理**
```bash
GET /api/models                 # 获取可用模型列表
```

**4. 系统接口**
```bash
GET /api/health                 # 健康检查
GET /api/cities                 # 获取城市列表
GET /api/city/{city_name}       # 获取城市详情
```

---

## 使用方法

### 开发模式

1. **启动后端开发服务**
   ```bash
   python run_api.py
   ```
   - 支持热重载
   - API文档：http://localhost:8000/docs

2. **启动前端开发服务器**
   ```bash
   cd frontend
   npm run dev
   ```
   - 支持热更新（HMR）
   - 自动重新加载

3. **调试技巧**
   - 查看后端日志：console输出
   - 查看前端日志：浏览器开发者工具（F12）
   - 测试API：http://localhost:8000/docs

### 生产部署

**构建前端**：
```bash
cd frontend
npm run build
```

**部署选项**：

1. **Nginx反向代理**（推荐）
   - 托管前端静态文件
   - 代理API请求到后端

2. **FastAPI直接托管**
   - 将`dist`文件夹集成到后端
   - 单进程部署

---

## 常见问题

**Q1: 如何切换LLM模型？**
```
A: 修改 config/config.json 中的：
   - provider_type: openai/anthropic/google/openai-compatible
   - api_key: 对应API密钥
   - model: 模型名称
```

**Q2: React前端无法连接后端？**
```
A: 检查：
   1. 后端是否运行在 http://localhost:8000
   2. CORS是否已配置（app.py已默认配置）
   3. 浏览器控制台（F12）查看具体错误
```

**Q3: 如何添加新城市和景点？**
```
A: 编辑 src/shuai_travel_agent/config_manager.py
   在 _init_travel_knowledge() 方法中添加新的城市和景点数据
```

**Q4: 支持多用户并发吗？**
```
A: 是的。每个用户会话有独立的Agent实例和对话历史
   通过 session_id 进行隔离
```

**Q5: 思考过程不显示怎么办？**
```
A: 思考过程默认折叠，点击"深度思考中"的加载框即可展开查看
   如果完全没有显示，检查后端是否正常返回 reasoning_chunk 事件
```

**Q6: 新建会话为什么在历史列表看不到？**
```
A: 这是设计如此。消息数为0条时会话不显示在历史列表
   首次发送消息后，会话自动添加到列表
```

**Q7: 会话切换后消息会丢失吗？**
```
A: 不会。切换会话时：
   - 原会话消息保存在内存缓存中
   - 目标会话消息加载到界面
   - 流式状态会被清空
   注意：刷新页面会丢失消息（暂未持久化）
```

---

## 更新日志

### v2.0.0
- 新增深度思考展示功能（可折叠思考过程框）
- 优化会话隔离机制
- 改进流式响应稳定性
- 添加结构化日志系统
- 优化前端UI/UX

### v1.2.0
- 支持多协议LLM（OpenAI/Claude/Gemini/本地模型）
- 完善会话管理功能
- 添加停止生成控制
- 优化Markdown渲染

---

## 许可证

MIT License
