"""
配置管理模块 (Configuration Manager)
职责：
1. 管理LLM API配置
2. 管理系统参数和旅游知识库
3. 提供配置热加载能力
"""

import json
import os
from typing import Dict, Any, List, Optional


class ConfigManager:
    """配置管理器：统一管理系统配置、LLM参数、旅游知识库"""
    
    def __init__(self, config_path: str = "config/config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 系统配置文件路径
        
        Raises:
            FileNotFoundError: 当必需的配置文件不存在时抛出异常
        """
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.llm_config: Dict[str, Any] = {}
        self.travel_knowledge: Dict[str, Any] = {}
        
        # 检查配置文件是否存在
        self._check_config_files()
        
        self._load_config()
        self._init_travel_knowledge()
    
    def _check_config_files(self) -> None:
        """检查必需的配置文件是否存在"""
        if not os.path.exists(self.config_path):
            error_msg = (
                f"Configuration file missing: {self.config_path}\n\n"
                f"Please create configuration file before starting the application:\n"
                f"  1. Copy config/config.json.example to config/config.json\n"
                f"  2. Update the API key in the llm section\n\n"
                f"Refer to README.md for detailed instructions."
            )
            raise FileNotFoundError(error_msg)
    
    def _load_config(self) -> None:
        """加载配置文件"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        # 提取LLM配置
        self.llm_config = self.config.get('llm', {})
        
        # 验证必需的LLM配置项
        required_keys = ['api_base', 'api_key', 'model']
        missing_keys = [key for key in required_keys if key not in self.llm_config]
        
        if missing_keys:
            raise ValueError(
                f"Missing required LLM config keys: {', '.join(missing_keys)}\n"
                f"Please check the 'llm' section in {self.config_path}."
            )
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认系统配置（移除LLM配置）"""
        return {
            "agent_name": "TravelAssistantAgent",
            "version": "1.0.0",
            
            # 记忆管理配置
            "memory": {
                "max_working_memory": 10,
                "max_long_term_memory": 50,
                "memory_decay_rate": 0.95
            },
            
            # 系统参数
            "system": {
                "max_context_turns": 5,
                "enable_streaming": False,
                "log_level": "INFO"
            },
            
            # Web服务配置
            "web": {
                "host": "0.0.0.0",
                "port": 8000,
                "debug": True
            }
        }
    
    def _init_travel_knowledge(self) -> None:
        """初始化旅游知识库（城市、景点、特色）"""
        self.travel_knowledge = {
            "cities": {
                "北京": {
                    "region": "华北",
                    "tags": ["历史文化", "首都", "古建筑"],
                    "best_season": ["春季", "秋季"],
                    "avg_budget_per_day": 500,
                    "recommended_days": 4,
                    "attractions": [
                        {"name": "故宫", "type": "历史遗迹", "duration": 4, "ticket": 60},
                        {"name": "长城", "type": "历史遗迹", "duration": 6, "ticket": 40},
                        {"name": "天坛", "type": "历史遗迹", "duration": 3, "ticket": 15},
                        {"name": "颐和园", "type": "园林", "duration": 4, "ticket": 30}
                    ]
                },
                "上海": {
                    "region": "华东",
                    "tags": ["现代都市", "购物", "美食"],
                    "best_season": ["春季", "秋季"],
                    "avg_budget_per_day": 600,
                    "recommended_days": 3,
                    "attractions": [
                        {"name": "外滩", "type": "城市景观", "duration": 3, "ticket": 0},
                        {"name": "东方明珠", "type": "地标建筑", "duration": 2, "ticket": 180},
                        {"name": "迪士尼乐园", "type": "主题乐园", "duration": 8, "ticket": 399},
                        {"name": "豫园", "type": "园林", "duration": 2, "ticket": 40}
                    ]
                },
                "杭州": {
                    "region": "华东",
                    "tags": ["自然风光", "人文历史", "休闲"],
                    "best_season": ["春季", "秋季"],
                    "avg_budget_per_day": 400,
                    "recommended_days": 3,
                    "attractions": [
                        {"name": "西湖", "type": "自然风光", "duration": 4, "ticket": 0},
                        {"name": "灵隐寺", "type": "宗教文化", "duration": 3, "ticket": 45},
                        {"name": "千岛湖", "type": "自然风光", "duration": 6, "ticket": 150},
                        {"name": "宋城", "type": "主题乐园", "duration": 4, "ticket": 310}
                    ]
                },
                "成都": {
                    "region": "西南",
                    "tags": ["美食", "休闲", "熊猫"],
                    "best_season": ["春季", "秋季"],
                    "avg_budget_per_day": 350,
                    "recommended_days": 4,
                    "attractions": [
                        {"name": "大熊猫繁育研究基地", "type": "动物园", "duration": 4, "ticket": 55},
                        {"name": "宽窄巷子", "type": "历史街区", "duration": 3, "ticket": 0},
                        {"name": "武侯祠", "type": "历史遗迹", "duration": 2, "ticket": 50},
                        {"name": "都江堰", "type": "历史遗迹", "duration": 5, "ticket": 80}
                    ]
                },
                "西安": {
                    "region": "西北",
                    "tags": ["历史文化", "古都", "美食"],
                    "best_season": ["春季", "秋季"],
                    "avg_budget_per_day": 400,
                    "recommended_days": 4,
                    "attractions": [
                        {"name": "兵马俑", "type": "历史遗迹", "duration": 4, "ticket": 120},
                        {"name": "大雁塔", "type": "历史遗迹", "duration": 2, "ticket": 50},
                        {"name": "古城墙", "type": "历史遗迹", "duration": 3, "ticket": 54},
                        {"name": "华清宫", "type": "历史遗迹", "duration": 3, "ticket": 120}
                    ]
                },
                "厦门": {
                    "region": "华南",
                    "tags": ["海滨", "休闲", "文艺"],
                    "best_season": ["春季", "秋季", "冬季"],
                    "avg_budget_per_day": 450,
                    "recommended_days": 3,
                    "attractions": [
                        {"name": "鼓浪屿", "type": "海岛", "duration": 6, "ticket": 0},
                        {"name": "南普陀寺", "type": "宗教文化", "duration": 2, "ticket": 0},
                        {"name": "曾厝垵", "type": "历史街区", "duration": 3, "ticket": 0},
                        {"name": "环岛路", "type": "城市景观", "duration": 3, "ticket": 0}
                    ]
                }
            },
            
            "interest_tags": {
                "历史文化": ["北京", "西安", "洛阳", "南京"],
                "自然风光": ["杭州", "桂林", "张家界", "九寨沟"],
                "现代都市": ["上海", "深圳", "广州", "香港"],
                "美食": ["成都", "重庆", "广州", "西安"],
                "海滨度假": ["三亚", "厦门", "青岛", "大连"],
                "休闲养生": ["杭州", "成都", "丽江", "大理"]
            }
        }
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置项（支持嵌套键，如 'llm.api_key'）
        
        Args:
            key: 配置键（支持点分隔的嵌套键）
            default: 默认值
            
        Returns:
            配置值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set_config(self, key: str, value: Any) -> None:
        """
        设置配置项（支持嵌套键）
        
        Args:
            key: 配置键
            value: 配置值
        """
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def save_config(self) -> None:
        """保存配置到文件"""
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def get_city_info(self, city_name: str) -> Optional[Dict[str, Any]]:
        """
        获取城市信息
        
        Args:
            city_name: 城市名称
            
        Returns:
            城市信息字典，若不存在则返回None
        """
        return self.travel_knowledge['cities'].get(city_name)
    
    def search_cities_by_tag(self, tag: str) -> List[str]:
        """
        根据兴趣标签搜索城市
        
        Args:
            tag: 兴趣标签
            
        Returns:
            城市名称列表
        """
        return self.travel_knowledge['interest_tags'].get(tag, [])
    
    def get_all_cities(self) -> List[str]:
        """获取所有城市列表"""
        return list(self.travel_knowledge['cities'].keys())
    
    def get_llm_config(self) -> Dict[str, Any]:
        """获取LLM配置"""
        return self.llm_config
