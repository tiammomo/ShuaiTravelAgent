"""
配置管理模块 (Configuration Manager) - Web层配置管理

本模块提供Web层的配置管理功能，支持JSON和YAML两种配置文件格式。
采用代理模式，优先使用agent模块的统一ConfigManager实现。

设计说明:
    - 代理模式：优先尝试从agent模块导入统一的ConfigManager
    - 回退机制：如果agent模块不可用，使用本地简化实现
    - 这样既避免了代码重复，又保持了模块的独立性

配置来源:
    1. agent/config/config_manager.py (优先)
    2. 本地回退实现

使用示例:
    from src.config.config_manager import ConfigManager

    config = ConfigManager("config/llm_config.yaml")
    models = config.get_available_models()
"""

import json
import os
import sys
import re
import yaml
from typing import Dict, Any, List, Optional

# 尝试从 agent 模块导入统一的 ConfigManager
_config_manager_class = None
try:
    # 添加 agent 目录到路径
    agent_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'agent', 'src'))
    if agent_path not in sys.path:
        sys.path.insert(0, agent_path)
    from config.config_manager import ConfigManager as AgentConfigManager
    _config_manager_class = AgentConfigManager
except (ImportError, ValueError):
    pass


class ConfigManager:
    """
    配置管理器 (Web版本 - 代理到agent的统一实现)

    采用代理模式，将请求转发给agent的ConfigManager处理。
    如果agent模块不可用，则使用本地简化实现。

    属性:
        config_path: str 配置文件路径
        config: Dict[str, Any] 原始配置数据
        models_config: Dict[str, Dict] 模型配置字典
        default_model_id: str 默认模型ID
        travel_knowledge: Dict[str, Any] 旅游知识数据
        _delegate: Optional[ConfigManager] 代理的agent ConfigManager实例
    """

    def __init__(self, config_path: str = "config/llm_config.yaml"):
        """
        初始化配置管理器

        优先使用agent的ConfigManager，如果不可用则使用本地实现。

        Args:
            config_path: str 配置文件路径
        """
        # 如果有 agent 的 ConfigManager，使用它
        if _config_manager_class is not None:
            self._delegate = _config_manager_class(config_path)
            # 复制所有属性
            self.config_path = self._delegate.config_path
            self.config = self._delegate.config
            self.models_config = self._delegate.models_config
            self.default_model_id = self._delegate.default_model_id
            self.travel_knowledge = getattr(self._delegate, 'travel_knowledge', {})
        else:
            # 回退到本地实现
            self._delegate = None
            self.config_path = config_path
            self.config: Dict[str, Any] = {}
            self.models_config: Dict[str, Dict[str, Any]] = {}
            self.default_model_id: str = "gpt-4o-mini"
            self.travel_knowledge: Dict[str, Any] = {}
            self._load_config()

    def _load_config(self) -> None:
        """加载配置文件，支持 YAML 和 JSON 格式 (本地回退实现)"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file missing: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        content = self._replace_env_vars(content)

        if self.config_path.endswith(('.yaml', '.yml')):
            self.config = yaml.safe_load(content)
        else:
            self.config = json.loads(content)

        self.models_config = self.config.get('models', {})
        self.default_model_id = self.config.get('default_model', 'gpt-4o-mini')

    def _replace_env_vars(self, content: str) -> str:
        """替换环境变量占位符 ${VAR_NAME}"""
        pattern = r'\$\{([^}]+)\}'

        def replace(match):
            var_name = match.group(1)
            env_value = os.environ.get(var_name, '')
            return env_value if env_value else match.group(0)

        return re.sub(pattern, replace, content)

    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持嵌套键如 'web.port'"""
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_city_info(self, city_name: str) -> Optional[Dict[str, Any]]:
        """获取城市信息"""
        return self.travel_knowledge.get('cities', {}).get(city_name) or \
               self.config.get('travel_knowledge', {}).get('cities', {}).get(city_name)

    def get_all_cities(self) -> List[str]:
        """获取所有城市列表"""
        cities = self.travel_knowledge.get('cities', {})
        if cities:
            return list(cities.keys())
        return list(self.config.get('travel_knowledge', {}).get('cities', {}).keys())

    def _is_model_active(self, config: Dict[str, Any]) -> bool:
        """检查模型配置是否已激活（拥有有效的API密钥）"""
        api_key = config.get('api_key', '')

        if not api_key:
            return False

        if api_key.startswith('${') and api_key.endswith('}'):
            var_name = api_key[2:-1]
            return bool(os.environ.get(var_name))

        if 'YOUR_' in api_key.upper():
            return False

        return True

    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        获取已激活的模型列表

        仅返回已配置有效API密钥的模型，过滤掉占位符配置。
        用于前端模型选择器，确保只显示可用的模型选项。
        """
        models = []
        for model_id, config in self.models_config.items():
            if not self._is_model_active(config):
                continue

            provider_type = config.get('provider', 'openai')
            model_name = config.get('model', model_id)
            display_name = config.get('name', model_id)
            models.append({
                'model_id': model_id,
                'name': display_name,
                'provider': provider_type,
                'model': model_name
            })
        return models

    def get_model_config(self, model_id: Optional[str] = None) -> Dict[str, Any]:
        """获取模型配置"""
        if model_id is None:
            model_id = self.default_model_id

        if model_id not in self.models_config:
            raise ValueError(f"模型不存在: {model_id}")

        return self.models_config[model_id]

    def get_default_model_id(self) -> str:
        """获取默认模型ID"""
        return self.default_model_id

    def get_default_model_config(self) -> Dict[str, Any]:
        """获取默认模型配置"""
        return self.get_model_config(self.default_model_id)

    @property
    def agent_config(self) -> Dict[str, Any]:
        """获取 Agent 配置"""
        return self.config.get('agent', {})

    @property
    def web_config(self) -> Dict[str, Any]:
        """获取 Web 服务配置"""
        return self.config.get('web', {})

    @property
    def grpc_config(self) -> Dict[str, Any]:
        """获取 gRPC 服务配置"""
        return self.config.get('grpc', {})
