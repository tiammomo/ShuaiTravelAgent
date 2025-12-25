"""
大模型调用模块 (LLM Client)
职责：
1. 封装OpenAI兼容API调用
2. 处理请求重试和错误处理
3. 管理Prompt构建和响应解析
"""

import json
import time
from typing import Dict, Any, List, Optional, Iterator
import urllib.request
import urllib.error


class LLMClient:
    """大模型客户端：封装GPT-4o-mini API调用"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM客户端
        
        Args:
            config: LLM配置字典
        """
        self.api_base = config.get('api_base', '')
        self.api_key = config.get('api_key', '')
        self.model = config.get('model', 'gpt-4o-mini')
        self.temperature = config.get('temperature', 0.7)
        self.max_tokens = config.get('max_tokens', 2000)
        self.timeout = config.get('timeout', 30)
        self.max_retries = config.get('max_retries', 3)
        self.stream = config.get('stream', False)  # 流式输出开关
        
        self.chat_url = f"{self.api_base}/chat/completions"
    
    def chat_stream(self, messages: List[Dict[str, str]], 
                    temperature: Optional[float] = None,
                    max_tokens: Optional[int] = None) -> Iterator[str]:
        """
        流式调用Chat Completion API（SSE模式）
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Yields:
            流式生成的文本块
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens,
            "stream": True  # 启用流式
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.chat_url,
                data=data,
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                # 读取SSE流
                for line in response:
                    line = line.decode('utf-8').strip()
                    
                    # SSE格式: data: {...}
                    if line.startswith('data: '):
                        data_str = line[6:]  # 移除 'data: ' 前缀
                        
                        # 结束标记
                        if data_str == '[DONE]':
                            break
                        
                        try:
                            chunk = json.loads(data_str)
                            delta = chunk.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield content
                        
                        except json.JSONDecodeError:
                            continue
        
        except urllib.error.HTTPError as e:
            error_msg = e.read().decode('utf-8')
            yield f"\n\n[错误: HTTP {e.code}]\n"
        
        except urllib.error.URLError as e:
            yield f"\n\n[错误: 网络连接失败]\n"
        
        except Exception as e:
            yield f"\n\n[错误: {str(e)}]\n"
    
    def chat(self, messages: List[Dict[str, str]], 
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        调用Chat Completion API
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            temperature: 温度参数（可选，覆盖默认值）
            max_tokens: 最大token数（可选，覆盖默认值）
            
        Returns:
            API响应字典
        """
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self.max_tokens
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        # 重试逻辑
        for attempt in range(self.max_retries):
            try:
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(
                    self.chat_url,
                    data=data,
                    headers=headers,
                    method='POST'
                )
                
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    return {
                        "success": True,
                        "content": result['choices'][0]['message']['content'],
                        "usage": result.get('usage', {}),
                        "model": result.get('model', self.model)
                    }
            
            except urllib.error.HTTPError as e:
                error_msg = e.read().decode('utf-8')
                print(f"HTTP错误 (尝试 {attempt + 1}/{self.max_retries}): {e.code} - {error_msg}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)  # 指数退避
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {e.code}: {error_msg}"
                    }
            
            except urllib.error.URLError as e:
                print(f"网络错误 (尝试 {attempt + 1}/{self.max_retries}): {e.reason}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return {
                        "success": False,
                        "error": f"网络错误: {e.reason}"
                    }
            
            except Exception as e:
                print(f"未知错误 (尝试 {attempt + 1}/{self.max_retries}): {str(e)}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    return {
                        "success": False,
                        "error": f"未知错误: {str(e)}"
                    }
        
        return {
            "success": False,
            "error": "超过最大重试次数"
        }
    
    def generate_travel_recommendation(self, user_query: str, 
                                       context: str,
                                       available_cities: List[str]) -> Dict[str, Any]:
        """
        生成旅游推荐（城市推荐）
        
        Args:
            user_query: 用户查询
            context: 上下文摘要
            available_cities: 可用城市列表
            
        Returns:
            推荐结果
        """
        system_prompt = f"""你是一个专业的旅游助手，负责根据用户需求推荐合适的旅游城市。

可推荐城市列表：{', '.join(available_cities)}

当前用户偏好：
{context}

请基于用户需求，从可推荐城市中选择3-5个最合适的城市，并以JSON格式返回：
{{
    "recommendations": [
        {{
            "city": "城市名",
            "reason": "推荐理由（50字以内）",
            "match_score": 90
        }}
    ],
    "explanation": "整体推荐说明（100字以内）"
}}

注意：
1. 只推荐列表中存在的城市
2. match_score为匹配度评分（0-100）
3. 推荐理由需结合用户偏好和城市特色
4. 按匹配度从高到低排序"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ]
        
        response = self.chat(messages, temperature=0.7)
        
        if not response['success']:
            return response
        
        # 解析JSON响应
        try:
            content = response['content']
            # 尝试提取JSON（可能包含在markdown代码块中）
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            recommendations = json.loads(content)
            response['recommendations'] = recommendations
            return response
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {str(e)}",
                "raw_content": response['content']
            }
    
    def generate_route_plan(self, city: str, 
                           days: int,
                           attractions: List[Dict[str, Any]],
                           user_preference: str) -> Dict[str, Any]:
        """
        生成旅游路线规划
        
        Args:
            city: 城市名称
            days: 旅行天数
            attractions: 景点列表
            user_preference: 用户偏好
            
        Returns:
            路线规划
        """
        attractions_info = "\n".join([
            f"- {a['name']}：{a['type']}，建议游玩{a['duration']}小时，门票{a['ticket']}元"
            for a in attractions
        ])
        
        system_prompt = f"""你是一个专业的旅游规划师，负责为用户制定详细的旅游路线。

目标城市：{city}
旅行天数：{days}天
可选景点：
{attractions_info}

用户偏好：
{user_preference}

请制定一个{days}天的详细旅游路线，以JSON格式返回：
{{
    "route_plan": [
        {{
            "day": 1,
            "attractions": ["景点1", "景点2"],
            "schedule": "上午游览景点1（3小时），下午游览景点2（4小时）",
            "tips": "建议事项"
        }}
    ],
    "total_cost_estimate": {{
        "tickets": 500,
        "meals": 300,
        "transportation": 200,
        "total": 1000
    }},
    "travel_tips": ["tip1", "tip2", "tip3"]
}}

注意：
1. 合理安排每天行程，避免过于紧凑
2. 考虑景点间的地理位置和交通时间
3. 提供实用的旅行建议
4. 估算各项费用"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"帮我规划{city}{days}天的旅游路线"}
        ]
        
        response = self.chat(messages, temperature=0.6)
        
        if not response['success']:
            return response
        
        # 解析JSON响应
        try:
            content = response['content']
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            
            route_plan = json.loads(content)
            response['route_plan'] = route_plan
            return response
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON解析失败: {str(e)}",
                "raw_content": response['content']
            }
    
    def chat_with_context(self, conversation_history: List[Dict[str, str]],
                          system_context: str) -> Dict[str, Any]:
        """
        带上下文的对话
        
        Args:
            conversation_history: 对话历史
            system_context: 系统上下文
            
        Returns:
            对话响应
        """
        messages = [
            {"role": "system", "content": f"""你是一个专业的旅游助手，负责回答用户关于旅游的各类问题。

当前上下文：
{system_context}

请友好、专业地回答用户问题，提供实用的旅游建议。"""}
        ]
        
        messages.extend(conversation_history)
        
        return self.chat(messages)
