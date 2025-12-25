"""
记忆/状态管理模块 (Memory Manager)
职责：
1. 管理用户会话上下文（短期记忆）
2. 管理用户偏好和历史记录（长期记忆）
3. 提供记忆检索和更新接口
"""

import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import deque


class Message:
    """对话消息"""
    
    def __init__(self, role: str, content: str, timestamp: Optional[str] = None):
        """
        初始化消息
        
        Args:
            role: 角色（user/assistant/system）
            content: 消息内容
            timestamp: 时间戳
        """
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, str]:
        """转换为字典"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'Message':
        """从字典创建消息"""
        return cls(data['role'], data['content'], data.get('timestamp'))


class UserPreference:
    """用户偏好"""
    
    def __init__(self):
        self.budget_range: Optional[tuple] = None  # 预算范围（最小，最大）
        self.travel_days: Optional[int] = None  # 旅行天数
        self.interest_tags: List[str] = []  # 兴趣标签
        self.preferred_cities: List[str] = []  # 偏好城市
        self.season_preference: Optional[str] = None  # 季节偏好
        self.travel_companions: Optional[str] = None  # 同行人员（独自/家人/朋友/情侣）
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "budget_range": self.budget_range,
            "travel_days": self.travel_days,
            "interest_tags": self.interest_tags,
            "preferred_cities": self.preferred_cities,
            "season_preference": self.season_preference,
            "travel_companions": self.travel_companions
        }
    
    def from_dict(self, data: Dict[str, Any]) -> None:
        """从字典加载"""
        self.budget_range = tuple(data['budget_range']) if data.get('budget_range') else None
        self.travel_days = data.get('travel_days')
        self.interest_tags = data.get('interest_tags', [])
        self.preferred_cities = data.get('preferred_cities', [])
        self.season_preference = data.get('season_preference')
        self.travel_companions = data.get('travel_companions')
    
    def update_from_text(self, text: str) -> None:
        """从用户输入文本中提取偏好（简单规则匹配）"""
        text_lower = text.lower()
        
        # 提取预算信息
        if '预算' in text or '元' in text or '块' in text:
            import re
            numbers = re.findall(r'\d+', text)
            if numbers:
                nums = [int(n) for n in numbers]
                if len(nums) >= 2:
                    self.budget_range = (min(nums), max(nums))
                elif len(nums) == 1:
                    self.budget_range = (0, nums[0])
        
        # 提取天数信息
        if '天' in text:
            import re
            match = re.search(r'(\d+)\s*天', text)
            if match:
                self.travel_days = int(match.group(1))
        
        # 提取兴趣标签
        interest_keywords = {
            '历史': '历史文化',
            '文化': '历史文化',
            '自然': '自然风光',
            '风景': '自然风光',
            '美食': '美食',
            '海边': '海滨度假',
            '海滨': '海滨度假',
            '购物': '现代都市',
            '休闲': '休闲养生'
        }
        for keyword, tag in interest_keywords.items():
            if keyword in text and tag not in self.interest_tags:
                self.interest_tags.append(tag)


class MemoryManager:
    """记忆管理器：管理对话历史、用户偏好、会话状态"""
    
    def __init__(self, max_working_memory: int = 10, max_long_term_memory: int = 50):
        """
        初始化记忆管理器
        
        Args:
            max_working_memory: 最大工作记忆数量（对话轮数）
            max_long_term_memory: 最大长期记忆数量
        """
        self.max_working_memory = max_working_memory
        self.max_long_term_memory = max_long_term_memory
        
        # 工作记忆：存储当前会话的对话历史
        self.conversation_history: deque = deque(maxlen=max_working_memory)
        
        # 用户偏好
        self.user_preference = UserPreference()
        
        # 会话状态
        self.session_state: Dict[str, Any] = {
            "session_id": f"session_{int(time.time())}",
            "start_time": datetime.now().isoformat(),
            "last_recommended_cities": [],  # 最后推荐的城市
            "last_recommended_attractions": [],  # 最后推荐的景点
            "current_plan": None  # 当前路线规划
        }
        
        # 长期记忆：存储历史会话摘要
        self.long_term_memory: List[Dict[str, Any]] = []
    
    def add_message(self, role: str, content: str) -> None:
        """
        添加对话消息到工作记忆
        
        Args:
            role: 角色（user/assistant/system）
            content: 消息内容
        """
        message = Message(role, content)
        self.conversation_history.append(message)
        
        # 如果是用户消息，尝试提取偏好
        if role == 'user':
            self.user_preference.update_from_text(content)
    
    def get_conversation_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        获取对话历史
        
        Args:
            limit: 限制返回数量（从最新开始）
            
        Returns:
            消息字典列表
        """
        history = list(self.conversation_history)
        if limit:
            history = history[-limit:]
        return [msg.to_dict() for msg in history]
    
    def get_messages_for_llm(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        获取适用于LLM的消息格式（仅role和content）
        
        Args:
            limit: 限制返回数量
            
        Returns:
            消息列表 [{"role": "user", "content": "..."}]
        """
        history = self.get_conversation_history(limit)
        return [{"role": msg['role'], "content": msg['content']} for msg in history]
    
    def update_session_state(self, key: str, value: Any) -> None:
        """
        更新会话状态
        
        Args:
            key: 状态键
            value: 状态值
        """
        self.session_state[key] = value
    
    def get_session_state(self, key: str, default: Any = None) -> Any:
        """
        获取会话状态
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值
        """
        return self.session_state.get(key, default)
    
    def clear_conversation(self) -> None:
        """清空当前会话的对话历史"""
        self.conversation_history.clear()
        self.session_state['session_id'] = f"session_{int(time.time())}"
        self.session_state['start_time'] = datetime.now().isoformat()
    
    def get_user_preference(self) -> Dict[str, Any]:
        """获取用户偏好"""
        return self.user_preference.to_dict()
    
    def set_user_preference(self, preference_data: Dict[str, Any]) -> None:
        """设置用户偏好"""
        self.user_preference.from_dict(preference_data)
    
    def save_to_file(self, filepath: str) -> None:
        """
        保存记忆到文件
        
        Args:
            filepath: 文件路径
        """
        data = {
            "session_state": self.session_state,
            "conversation_history": self.get_conversation_history(),
            "user_preference": self.user_preference.to_dict(),
            "long_term_memory": self.long_term_memory
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_from_file(self, filepath: str) -> bool:
        """
        从文件加载记忆
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否加载成功
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.session_state = data.get('session_state', {})
            
            # 加载对话历史
            self.conversation_history.clear()
            for msg_data in data.get('conversation_history', []):
                msg = Message.from_dict(msg_data)
                self.conversation_history.append(msg)
            
            # 加载用户偏好
            self.user_preference.from_dict(data.get('user_preference', {}))
            
            # 加载长期记忆
            self.long_term_memory = data.get('long_term_memory', [])
            
            return True
        except Exception as e:
            print(f"加载记忆失败: {e}")
            return False
    
    def get_context_summary(self) -> str:
        """
        生成当前上下文摘要（用于Prompt）
        
        Returns:
            上下文摘要文本
        """
        summary_parts = []
        
        # 用户偏好摘要
        pref = self.user_preference
        if pref.budget_range:
            summary_parts.append(f"预算范围：{pref.budget_range[0]}-{pref.budget_range[1]}元/天")
        if pref.travel_days:
            summary_parts.append(f"旅行天数：{pref.travel_days}天")
        if pref.interest_tags:
            summary_parts.append(f"兴趣偏好：{', '.join(pref.interest_tags)}")
        if pref.preferred_cities:
            summary_parts.append(f"偏好城市：{', '.join(pref.preferred_cities)}")
        
        # 会话状态
        if self.session_state.get('last_recommended_cities'):
            summary_parts.append(f"已推荐城市：{', '.join(self.session_state['last_recommended_cities'])}")
        
        return "\n".join(summary_parts) if summary_parts else "暂无用户偏好信息"
