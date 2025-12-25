# 旅游助手 - 基于单智能体的AI旅游推荐系统

## 项目概述

基于自定义单智能体架构的智能旅游助手系统，集成GPT-4o-mini大模型，提供城市推荐、景点查询、路线规划等功能。

**核心特性**：
- ✅ 自定义Agent架构（无第三方AI框架依赖）
- ✅ GPT-4o-mini大模型集成
- ✅ 完整的感知-推理-行动循环
- ✅ 双层记忆管理（工作记忆+长期记忆）
- ✅ FastAPI Web服务 + Streamlit前端
- ✅ 标准化Python项目结构

---

## 项目结构

```
ShuaiTravelAgent/
├── src/shuai_travel_agent/     # 核心包
│   ├── agent.py                 # Agent主体
│   ├── config_manager.py        # 配置管理
│   ├── environment.py           # 环境交互
│   ├── llm_client.py            # LLM客户端
│   ├── memory_manager.py        # 记忆管理
│   ├── reasoner.py              # 推理引擎
│   ├── app.py                   # FastAPI服务
│   └── streamlit_app.py         # Streamlit界面
├── config/
│   └── config.json.example      # 配置模板
├── run_api.py                   # API启动脚本
├── run_streamlit.py             # Streamlit启动脚本
├── setup.py
└── requirements.txt
```

---

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置API密钥
```bash
cd config
cp config.json.example config.json
# 编辑 config.json，填入您的OpenAI API密钥
```

### 3. 启动服务
```bash
# 终端1：API服务（http://localhost:8000）
python run_api.py

# 终端2：Streamlit前端（http://localhost:8501）
python run_streamlit.py
```

---

## 核心模块

| 模块 | 职责 | 关键功能 |
|------|------|--------|
| **ConfigManager** | 配置管理 | 加载配置、内置知识库（6城市24景点） |
| **MemoryManager** | 记忆管理 | 工作记忆（10条）、用户偏好、会话状态 |
| **LLMClient** | 模型调用 | OpenAI兼容API、重试机制（3次）、流式输出 |
| **Reasoner** | 推理引擎 | 意图识别、参数提取、执行计划生成 |
| **Environment** | 环境交互 | 知识库查询、工具调用、预算计算 |
| **TravelAgent** | Agent主体 | 协调各模块、感知→推理→行动循环 |

---

## 配置说明

### config.json
```json
{
  "agent_name": "TravelAssistantAgent",
  "llm": {
    "api_base": "https://api.openai.com/v1",
    "api_key": "YOUR_API_KEY_HERE",
    "model": "gpt-4o-mini",
    "temperature": 0.7,
    "max_tokens": 2000
  },
  "memory": {
    "max_working_memory": 10,
    "max_long_term_memory": 50
  },
  "web": {
    "host": "0.0.0.0",
    "port": 8000,
    "debug": true
  }
}
```

---

## API接口

### POST /api/chat
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"推荐适合春天旅游的城市"}'
```

**Response**:
```json
{
  "success": true,
  "response": "推荐结果...",
  "intent": "city_recommendation",
  "session_id": "xxx"
}
```

### POST /api/chat/stream
服务器发送事件（SSE）流式响应

### GET /api/health
健康检查

### GET /api/cities
获取支持的城市列表

---

## 支持的意图

- `city_recommendation` - 城市推荐
- `attraction_query` - 景点查询
- `route_planning` - 路线规划
- `preference_update` - 偏好更新
- `general_chat` - 一般对话

---

## 常见问题

**Q: 如何切换到其他LLM模型？**  
A: 修改 `config.json` 中的 `llm.model` 和 `llm.api_base`

**Q: 如何添加新城市？**  
A: 修改 `src/shuai_travel_agent/config_manager.py` 中的 `_init_travel_knowledge()` 方法

**Q: 支持多用户并发吗？**  
A: 支持。每个会话有独立的Agent实例和会话ID

---

## 许可证

MIT License
