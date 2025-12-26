"""
Streamlit前端界面 - 小帅旅游助手

核心功能：
1. 多会话管理 - 支持创建、切换、删除会话
2. 实时聊天 - 支持流式输出，实时显示AI回复
3. 会话历史 - 显示对话历史和会话列表
4. 系统配置 - API配置和健康检查

性能优化：
- 使用@st.fragment装饰器实现局部刷新
- 避免全页面重新加载，提升用户体验
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime

# 页面配置（必须在应用开始）
st.set_page_config(
    page_title="小帅旅游助手",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        font-weight: 600;
    }
    .stButton>button:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
    }
    .chat-message {
        padding: 1rem;
        border-radius: 1rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: row;
        align-items: flex-start;
        gap: 0.75rem;
    }
    .user-message {
        background-color: #667eea;
        color: white;
        flex-direction: row-reverse;
    }
    .assistant-message {
        background-color: #f0f2f6;
        color: #262730;
    }
    .message-avatar {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        flex-shrink: 0;
    }
    .user-avatar {
        background-color: #ffffff;
    }
    .assistant-avatar {
        background-color: #667eea;
    }
    .message-content {
        flex: 1;
        display: flex;
        flex-direction: column;
    }
    .message-time {
        font-size: 0.75rem;
        opacity: 0.7;
        margin-top: 0.5rem;
    }
    .sidebar .element-container {
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# 初始化session state
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """你好！我是你的AI旅游助手 🎒

我可以帮你：
• 推荐适合的旅游城市
• 查询城市景点信息
• 制定详细的旅游路线
• 根据预算和兴趣提供建议

请告诉我你的需求，让我为你规划一次完美的旅行！""",
            "timestamp": datetime.now().strftime("%H:%M")
        }
    ]

if 'api_base' not in st.session_state:
    st.session_state.api_base = "http://localhost:8000"

# 会话管理
if 'current_session_id' not in st.session_state:
    st.session_state.current_session_id = None

# 分页状态
if 'session_page' not in st.session_state:
    st.session_state.session_page = 0

# 会话列表缓存（避免频繁调用API）
if 'sessions_cache' not in st.session_state:
    st.session_state.sessions_cache = []
    st.session_state.sessions_cache_time = None

# 流式输出控制状态
if 'is_streaming' not in st.session_state:
    st.session_state.is_streaming = False

if 'stop_streaming' not in st.session_state:
    st.session_state.stop_streaming = False

# 自动创建首个会话
if 'auto_created' not in st.session_state:
    st.session_state.auto_created = False
    try:
        response = requests.get(f"{st.session_state.api_base}/api/sessions", timeout=3)
        if response.status_code == 200:
            data = response.json()
            sessions_list = data.get('sessions', [])
            if not sessions_list:
                # 无历史会话，自动创建
                create_response = requests.post(f"{st.session_state.api_base}/api/session/new")
                if create_response.status_code == 200:
                    session_data = create_response.json()
                    st.session_state.current_session_id = session_data['session_id']
                    st.session_state.auto_created = True
    except:
        pass

# 侧边栏
with st.sidebar:
    st.title("🌍 AI旅游助手")
    st.markdown("---")
    
    # ========== API配置 (局部刷新) ==========
    @st.fragment
    def api_config_section():
        """
        API配置区域（局部刷新）
        
        功能：
        - 显示API地址输入框
        - 执行健康检查
        """
        st.subheader("⚙️ 系统配置")
        api_base = st.text_input(
            "API地址",
            value=st.session_state.api_base,
            help="后端API服务地址"
        )
        st.session_state.api_base = api_base
        
        # 健康检查按钮（局部刷新，不影响其他区域）
        if st.button("🔍 检查连接"):
            try:
                response = requests.get(f"{api_base}/api/health", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"✅ 连接成功\n\nAgent: {data['agent']}\n版本: {data['version']}")
                else:
                    st.error(f"❌ 连接失败: {response.status_code}")
            except Exception as e:
                st.error(f"❌ 无法连接到服务器: {str(e)}")
    
    api_config_section()
    st.markdown("---")
    
    # ========== 会话管理 (局部刷新) ==========
    @st.fragment
    def session_control_section():
        """
        会话控制区域（局部刷新）
        
        功能：
        - 显示当前会话信息
        - 创建新会话
        - 清空对话
        """
        st.subheader("📝 会话管理")
        
        # 显示当前会话ID
        if st.session_state.current_session_id:
            st.caption(f"🔑 当前会话: {st.session_state.current_session_id[:8]}...")
            st.caption(f"💬 消息数: {len(st.session_state.messages) - 1}")
        else:
            st.caption("⚠️ 尚未创建会话")
        
        # 会话操作按钮
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ 新建会话", key="new_session_btn", use_container_width=True):
                st.session_state.trigger_new_session = True
        
        with col2:
            if st.button("🗑️ 清空对话", key="clear_conv_btn", use_container_width=True):
                if st.session_state.current_session_id:
                    st.session_state.trigger_clear = True
                else:
                    st.warning("⚠️ 请先创建会话")
    
    session_control_section()
    st.markdown("---")
    
    # ========== 会话列表 (局部刷新) ==========
    @st.fragment
    def session_list_section():
        """
        会话列表区域（局部刷新）

        功能：
        - 显示历史会话列表
        - 支持分页浏览
        - 支持切换和删除会话
        - 使用缓存避免频繁调用API

        设计原则：
        - 被动刷新：只在用户操作后刷新
        - 缓存机制：减少不必要的API调用
        - 无定时刷新：不设置任何定时器
        """
        st.subheader("📊 历史会话")

        # 刷新按钮（手动触发）
        col_refresh, col_clear = st.columns([3, 1])
        with col_refresh:
            if st.button("🔄 刷新列表", use_container_width=True):
                st.session_state.sessions_cache = []
                st.session_state.sessions_cache_time = None
                st.rerun()

        # 尝试从缓存获取
        cache_valid = (
            st.session_state.sessions_cache and
            st.session_state.sessions_cache_time and
            (time.time() - st.session_state.sessions_cache_time) < 300  # 缓存5分钟
        )

        if not cache_valid:
            try:
                response = requests.get(f"{st.session_state.api_base}/api/sessions", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.sessions_cache = data.get('sessions', [])
                    st.session_state.sessions_cache_time = time.time()
            except Exception as e:
                st.error(f"加载失败: {str(e)}")
                return

        sessions_list = st.session_state.sessions_cache

        if sessions_list:
            # 分页设置
            items_per_page = 10
            total_pages = (len(sessions_list) + items_per_page - 1) // items_per_page
            current_page = st.session_state.session_page

            # 确保页码合法
            if current_page >= total_pages:
                current_page = total_pages - 1
                st.session_state.session_page = current_page

            # 分页按钮（仅在多页时显示）
            if total_pages > 1:
                col_prev, col_info, col_next = st.columns([1, 2, 1])
                with col_prev:
                    if st.button("◀ 上页", disabled=(current_page == 0), use_container_width=True):
                        st.session_state.session_page = max(0, current_page - 1)
                        st.rerun()
                with col_info:
                    st.caption(f"📊 第 {current_page + 1}/{total_pages} 页 · 共 {len(sessions_list)} 个会话")
                with col_next:
                    if st.button("下页 ▶", disabled=(current_page >= total_pages - 1), use_container_width=True):
                        st.session_state.session_page = min(total_pages - 1, current_page + 1)
                        st.rerun()
                st.markdown("---")

            # 显示当前页会话
            start_idx = current_page * items_per_page
            end_idx = min(start_idx + items_per_page, len(sessions_list))

            for session in sessions_list[start_idx:end_idx]:
                session_id = session['session_id']
                msg_count = session['message_count']
                last_active = session['last_active'][:19]

                is_current = session_id == st.session_state.current_session_id

                col_a, col_b = st.columns([3, 1])
                with col_a:
                    button_label = f"{'✅' if is_current else '📌'} {session_id[:8]}... ({msg_count}条)"
                    if st.button(button_label, key=f"switch_{session_id}", disabled=is_current, use_container_width=True):
                        st.session_state.trigger_switch = session_id
                        st.session_state.sessions_cache = []  # 清除缓存，刷新列表

                with col_b:
                    if st.button("🗑️", key=f"del_{session_id}", use_container_width=True):
                        st.session_state.trigger_delete = session_id
                        st.session_state.sessions_cache = []  # 清除缓存，刷新列表

                st.caption(f"🕒 {last_active}")
                st.markdown("---")
        else:
            st.info("📂 暂无历史会话")
    
    session_list_section()
    st.markdown("---")
    st.caption("Powered by GPT-4o-mini")

# 主界面
st.title("🌍 小帅旅游助手")
st.markdown("为您提供个性化的旅游推荐和路线规划")
st.markdown("---")

# 清空上一次的想定义回调前置
if 'chat_container' not in st.session_state:
    st.session_state.chat_container = st.container()

chat_container = st.session_state.chat_container

# ========== 消息渲染函数 ==========
def render_message(role: str, content: str, timestamp: str) -> str:
    """
    渲染单条消息（HTML格式）
    
    Args:
        role: 消息得分（user或assistant）
        content: 消息内容
        timestamp: 消息时间戳
    
    Returns:
        HTML消息堆代码
    """
    if role == "user":
        return f"""
        <div class="chat-message user-message">
            <div class="message-avatar user-avatar">👤</div>
            <div class="message-content">
                <div>{content}</div>
                <div class="message-time">{timestamp}</div>
            </div>
        </div>
        """
    else:
        return f"""
        <div class="chat-message assistant-message">
            <div class="message-avatar assistant-avatar">🤖</div>
            <div class="message-content">
                <div>{content}</div>
                <div class="message-time">{timestamp}</div>
            </div>
        </div>
        """

# ========== 消息展示区域 (局部刷新) ==========
@st.fragment
def chat_display_section():
    """
    消息展示区域（局部刷新）
    
    功能：
    - 显示所有对话消息
    - 支持Markdown和HTML渲染
    - 体验优化：使用@st.fragment局部刷新，新消息仅刷新此区域
    
    注：
    - 每次渲染每一条消息，确保治理消息顺序
    - 使用HTML自定义样式优化消息显示效果
    """
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")
        st.markdown(render_message(role, content, timestamp), unsafe_allow_html=True)

chat_display_section()

# 处理快捷消息（已移除快捷操作，保留兼容性）
if 'quick_message' in st.session_state:
    del st.session_state.quick_message

# 处理触发器（避免在按钮回调中rerun）
if 'trigger_new_session' in st.session_state and st.session_state.trigger_new_session:
    st.session_state.trigger_new_session = False
    try:
        response = requests.post(f"{st.session_state.api_base}/api/session/new")
        if response.status_code == 200:
            data = response.json()
            st.session_state.current_session_id = data['session_id']
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "🎉 新会话已创建！有什么旅游计划需要帮助吗？",
                    "timestamp": datetime.now().strftime("%H:%M")
                }
            ]
            # 清除会话列表缓存，确保新会话出现在列表中
            st.session_state.sessions_cache = []
            st.session_state.sessions_cache_time = None
            st.rerun()
    except Exception as e:
        st.error(f"创建失败: {str(e)}")

if 'trigger_clear' in st.session_state and st.session_state.trigger_clear:
    st.session_state.trigger_clear = False
    try:
        response = requests.post(
            f"{st.session_state.api_base}/api/clear",
            params={"session_id": st.session_state.current_session_id}
        )
        if response.status_code == 200:
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": "🧹 对话已清空，让我们重新开始吧！",
                    "timestamp": datetime.now().strftime("%H:%M")
                }
            ]
            st.rerun()
    except Exception as e:
        st.error(f"清空失败: {str(e)}")

if 'trigger_switch' in st.session_state and st.session_state.trigger_switch:
    switch_id = st.session_state.trigger_switch
    st.session_state.trigger_switch = None
    st.session_state.current_session_id = switch_id
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "🔄 已切换到该会话",
            "timestamp": datetime.now().strftime("%H:%M")
        }
    ]
    st.rerun()

if 'trigger_delete' in st.session_state and st.session_state.trigger_delete:
    delete_id = st.session_state.trigger_delete
    st.session_state.trigger_delete = None
    try:
        response = requests.delete(f"{st.session_state.api_base}/api/session/{delete_id}")
        if response.status_code == 200:
            if delete_id == st.session_state.current_session_id:
                st.session_state.current_session_id = None
                st.session_state.messages = [
                    {
                        "role": "assistant",
                        "content": "🔑 请创建新会话开始对话",
                        "timestamp": datetime.now().strftime("%H:%M")
                    }
                ]
            st.rerun()
    except Exception as e:
        st.error(f"删除失败: {str(e)}")

# 输入框
st.markdown("---")

# 如果正在流式输出，显示停止按钮
if st.session_state.is_streaming:
    col_input, col_stop = st.columns([5, 1])
    with col_input:
        st.chat_input("正在生成回答中...", disabled=True)
    with col_stop:
        if st.button("🛑 停止", key="stop_btn", use_container_width=True):
            st.session_state.stop_streaming = True
            st.session_state.is_streaming = False
else:
    user_input = st.chat_input("输入你的旅游需求...")

if user_input:
    # 检查是否有会话 ID
    if not st.session_state.current_session_id:
        st.warning("⚠️ 请先点击左侧侧边栏的'➕ 新建会话'开始对话")
        st.stop()
    
    # ==== 第1步：立即显示用户消息（无感刷新） ====
    user_timestamp = datetime.now().strftime("%H:%M")
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": user_timestamp
    })
    
    # 立即刷新消息显示区，显示用户消息
    st.rerun()

# ==== 第2步：显示“正在思考...”并处理AI流式响应 ====
# 检查是否需要获取AI回复（最后一条消息是用户消息）
if (len(st.session_state.messages) > 0 and 
    st.session_state.messages[-1]["role"] == "user" and
    not st.session_state.is_streaming):
    
    # 设置流式状态
    st.session_state.is_streaming = True
    st.session_state.stop_streaming = False
    
    # 创建为 AI 回复的占位符
    assistant_placeholder = st.empty()
    assistant_message = "🤔 正在思考中..."
    assistant_timestamp = datetime.now().strftime("%H:%M")
    
    # 显示初始思考状态
    assistant_placeholder.markdown(
        render_message("assistant", assistant_message, assistant_timestamp),
        unsafe_allow_html=True
    )
    
    # 获取用户输入（最后一条用户消息）
    user_message_content = st.session_state.messages[-1]["content"]
    
    try:
        # 发起 SSE 流式请求
        response = requests.post(
            f"{st.session_state.api_base}/api/chat/stream",
            json={
                "message": user_message_content,
                "session_id": st.session_state.current_session_id
            },
            stream=True,
            timeout=120
        )
        
        if response.status_code == 200:
            assistant_message = ""  # 清空思考状态，开始显示AI回答
            
            # 逐块读取 SSE 数据
            for line in response.iter_lines(decode_unicode=True):
                # 检查停止信号
                if st.session_state.stop_streaming:
                    assistant_message += "\n\n⚠️ 已停止生成"
                    break
                
                if line.startswith('data: '):
                    data_str = line[6:]
                    
                    try:
                        chunk_data = json.loads(data_str)
                        
                        # 接收 session_id
                        if 'session_id' in chunk_data:
                            continue
                        
                        # 处理文本块 - 实时更新
                        if 'chunk' in chunk_data:
                            assistant_message += chunk_data['chunk']
                            # 使用占位符实时更新 AI 回复
                            assistant_placeholder.markdown(
                                render_message("assistant", assistant_message, assistant_timestamp),
                                unsafe_allow_html=True
                            )
                        
                        # 处理错误
                        elif 'error' in chunk_data:
                            assistant_message = f"抱歉，处理出错：{chunk_data['error']}"
                            break
                        
                        # 处理结束信号
                        elif chunk_data.get('done'):
                            break
                    
                    except json.JSONDecodeError:
                        continue
        else:
            assistant_message = f"请求失败：HTTP {response.status_code}"
    
    except requests.exceptions.Timeout:
        assistant_message = "请求超时，请稍后重试"
    except Exception as e:
        assistant_message = f"网络错误：{str(e)}"
    
    # 如果没有内容，显示错误信息
    if not assistant_message:
        assistant_message = "未收到回复"
    
    # 添加助手回复到消息历史
    st.session_state.messages.append({
        "role": "assistant",
        "content": assistant_message,
        "timestamp": assistant_timestamp
    })
    
    # 重置流式状态
    st.session_state.is_streaming = False
    st.session_state.stop_streaming = False
    
    # 刷新页面，显示完整的对话历史
    st.rerun()
