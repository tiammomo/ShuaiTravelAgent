# 小帅旅游助手 - 智能AI旅游推荐系统

## 项目概述

一个基于自定义单智能体架构的智能旅游助手系统，集成GPT-4o-mini大模型，提供城市推荐、景点查询、路线规划等功能。

项目采用**Python后端（FastAPI）+ React前端**的现代技术栈，支持流式SSE响应、多会话管理、双层记忆系统等功能。

### 核心特性
- ✅ **自定义Agent架构** - 无第三方AI框架依赖，完整的感知-推理-行动循环
- ✅ **多协议LLM支持** - OpenAI、Claude、Gemini、本地模型等
- ✅ **流式响应处理** - SSE实时流式输出 + 停止控制
- ✅ **双层记忆管理** - 工作记忆（短期） + 长期记忆 + 用户偏好
- ✅ **现代化前端** - React 18 + TypeScript + Vite
- ✅ **完整API接口** - FastAPI Swagger文档
- ✅ **多会话管理** - 独立的对话历史和Agent实例

---

## 项目结构

```
ShuaiTravelAgent/
├── src/shuai_travel_agent/              # 后端核心包
│   ├── agent.py                         # Agent主体（感知-推理-行动）
│   ├── config_manager.py                # 配置和知识库管理
│   ├── llm_client.py                    # LLM多协议客户端
│   ├── memory_manager.py                # 双层记忆系统
│   ├── reasoner.py                      # 推理和规划引擎
│   ├── environment.py                   # 环境交互和工具调用
│   ├── app.py                           # FastAPI Web服务
│   └── streamlit_app.py                 # Streamlit界面（可选）
│
├── frontend/                             # React前端
│   ├── src/
│   │   ├── components/                  # React组件（ChatArea、Sidebar等）
│   │   ├── context/                     # 全局状态管理（Context API）
│   │   ├── services/                    # API服务层
│   │   ├── types/                       # TypeScript类型定义
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
├── run_streamlit.py                     # Streamlit启动脚本（可选）
├── requirements.txt                     # Python依赖
└── QUICK_DEPLOY_REACT.md                # 快速部署指南
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
| **Agent** | 核心推理 | 感知→推理→行动循环 |
| **Reasoner** | 意图识别 | 识别用户意图并生成执行计划 |
| **MemoryManager** | 记忆管理 | 工作记忆、长期记忆、用户偏好 |
| **LLMClient** | 模型调用 | 支持OpenAI/Claude/Gemini等多种模型 |
| **Environment** | 工具调用 | 城市查询、景点推荐、路线规划 |
| **ConfigManager** | 配置管理 | 内置旅游知识库（6城市24景点） |

### 前端功能

- **✅ 会话管理** - 创建、切换、删除、重命名多个对话会话
- **✅ 智能会话命名** - 首次发送消息时自动使用问题前缀作为会话标题
- **✅ 消息缓存保留** - 切换会话时完整保留原会话的对话历史
- **✅ 实时聊天** - 流式SSE响应，逐字显示AI回复
- **✅ 停止控制** - 随时中断长文本生成
- **✅ 消息显示优化** - 紧凑排版、优化间距、Markdown富文本渲染
- **✅ 响应式设计** - 适配各种屏幕尺寸
- **✅ 状态管理** - Context API全局状态 + 会话消息缓存

---

## 会话管理详解

### 工作流程

```
1. 新建会话
   └─ 创建空会话（暂不显示在历史列表）

2. 首次发送消息
   └─ 自动将问题前15个字符作为会话名称
   └─ 会话添加到历史列表

3. 会话切换
   └─ 完整保留原会话的所有消息
   └─ 加载目标会话的历史消息

4. 会话重命名
   └─ 点击铅笔图标
   └─ 修改会话名称后保存
```

### 内存管理

- **会话消息缓存** - 每个会话的消息在内存中独立存储
- **自动同步** - 添加/删除/切换消息时自动更新缓存
- **会话隔离** - 不同会话之间消息完全独立

---

## 支持的用户意图

```
city_recommendation  - 城市推荐
attractive_query     - 景点查询
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
  "version": "1.0.0",
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

**1. 普通聊天**
```bash
POST /api/chat
Content-Type: application/json

{
  "message": "推荐适合春天旅游的城市",
  "session_id": "optional-session-id"
}

Response: {"success": true, "response": "...", "session_id": "xxx"}
```

**2. 流式聊天（SSE）**
```bash
POST /api/chat/stream
内容自动流式输出，支持停止控制
```

**3. 会话管理**
```bash
POST /api/session/new           # 创建新会话
GET /api/sessions               # 获取会话列表
DELETE /api/session/{id}        # 删除会话
PUT /api/session/{id}/name      # 重命名会话
POST /api/clear                 # 清空对话
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

3. **Docker容器化**
   - 构建Docker镜像
   - 支持编排部署

详见 `QUICK_DEPLOY_REACT.md` 了解完整部署步骤。

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

**Q5: 会话切换后原会话的消息不见了？**
```
A: 这是正常的。消息保存在内存中，需要添加 localStorage 或数据库持久化功能。
   注意：刷新页面会丢失消息
```

**Q6: 新建会话为什么不需要手动添加？**
```
A: 会话消息数为 0 条时，会话不显示在历史列表。
   首次发送消息后，会话自动添加到列表。
```

**Q7: 如何获取更详细的帮助？**
```
A: 查看 QUICK_DEPLOY_REACT.md 中的完整部署和常见问题章节
```

---

## 许可证

MIT License
