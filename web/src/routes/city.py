"""城市API路由模块 (City API Routes)

提供城市信息查询的RESTful API接口。
支持城市的列表查询、详情获取、景点查询等功能。

主要组件:
- router: API路由路由器
- CITIES: 城市数据静态列表

API端点:
- GET /cities - 列出所有城市（支持地区和标签筛选）
- GET /cities/{city_id} - 获取城市详细信息
- GET /cities/{city_id}/attractions - 获取城市景点列表
- GET /regions - 列出所有地区
- GET /tags - 列出所有标签

使用示例:
    # 列出所有城市
    GET /cities

    # 按地区筛选
    GET /cities?region=华东

    # 按标签筛选
    GET /cities?tags=美食,历史文化

    # 获取城市详情
    GET /cities/beijing

    # 获取城市景点
    GET /cities/beijing/attractions

    # 列出所有地区
    GET /regions

    # 列出所有标签
    GET /tags

数据说明:
    城市数据模型:
        {
            "id": str,        // 城市ID（英文标识）
            "name": str,      // 城市名称（中文）
            "region": str,    // 所在地区
            "tags": List[str] // 旅游标签列表
        }

    扩展详情模型:
        {
            // 基础信息
            "id": str,
            "name": str,
            "region": str,
            "tags": [...],

            // 扩展信息
            "description": str,            // 城市描述
            "attractions": [...],          // 景点列表
            "avg_budget_per_day": int,     // 日均预算
            "best_seasons": [...]          // 最佳旅游季节
        }

注意事项:
    - 当前城市数据为静态示例数据
    - 生产环境应从数据库或配置文件动态获取
    - 景点信息为占位数据，实际应从数据源查询
"""

from fastapi import APIRouter
from typing import List

router = APIRouter()


# 城市数据静态列表
# 注意：生产环境应从数据库或配置文件动态获取
CITIES = [
    {"id": "beijing", "name": "北京", "region": "华北", "tags": ["历史文化", "首都", "古建筑"]},
    {"id": "shanghai", "name": "上海", "region": "华东", "tags": ["现代都市", "购物", "美食"]},
    {"id": "hangzhou", "name": "杭州", "region": "华东", "tags": ["自然风光", "人文历史", "休闲"]},
    {"id": "chengdu", "name": "成都", "region": "西南", "tags": ["美食", "休闲", "熊猫"]},
    {"id": "xian", "name": "西安", "region": "西北", "tags": ["历史文化", "古都", "美食"]},
    {"id": "xiamen", "name": "厦门", "region": "华南", "tags": ["海滨", "休闲", "文艺"]},
]


@router.get(
    "/cities",
    responses={
        200: {"description": "获取成功", "content": {"application/json": {"example": {"cities": [{"id": "beijing", "name": "北京", "region": "华北", "tags": ["历史文化", "首都"]}]}}}},
        400: {"description": "请求参数错误", "content": {"application/json": {"example": {"detail": "无效的地区名称"}}}}
    }
)
async def list_cities(region: str = None, tags: str = None):
    """
    列出所有城市

    支持按地区和标签进行筛选。

    Query参数:
        region: str 可选，按地区名称筛选（如"华东"、"华北"）
        tags: str 可选，按标签筛选，多个标签用逗号分隔

    返回:
        {"cities": [...]} 符合条件的城市列表
    """
    result = CITIES

    # 按地区筛选
    if region:
        result = [c for c in result if c.get("region") == region]

    # 按标签筛选
    if tags:
        tag_list = tags.split(",")
        result = [c for c in result if any(t in c.get("tags", []) for t in tag_list)]

    return {"cities": result}


@router.get(
    "/cities/{city_id}",
    responses={
        200: {
            "description": "获取成功",
            "content": {
                "application/json": {
                    "example": {
                        "id": "beijing",
                        "name": "北京",
                        "region": "华北",
                        "tags": ["历史文化", "首都", "古建筑"],
                        "description": "北京是华北的热门旅游城市，以历史文化著称。",
                        "attractions": [{"name": "故宫", "type": "景点", "duration": "3小时", "ticket": 60}],
                        "avg_budget_per_day": 400,
                        "best_seasons": ["春季", "秋季"]
                    }
                }
            }
        },
        404: {"description": "城市不存在", "content": {"application/json": {"example": {"error": "City not found"}}}}
    }
)
async def get_city(city_id: str):
    """
    获取城市详细信息

    路径参数:
        city_id: str 城市ID（如"beijing"）

    返回:
        城市详细信息，包含描述、景点、日均预算、最佳旅游季节等

    错误:
        {"error": "City not found"} 城市不存在
    """
    city = next((c for c in CITIES if c["id"] == city_id), None)
    if not city:
        return {"error": "City not found"}

    # 构建扩展详情
    city_details = {
        **city,
        "description": f"{city['name']}是{city['region']}的热门旅游城市，以{city['tags'][0]}著称。",
        "attractions": [
            {"name": f"{city['name']}著名景点1", "type": "景点", "duration": "3小时", "ticket": 50},
            {"name": f"{city['name']}著名景点2", "type": "景点", "duration": "4小时", "ticket": 60},
        ],
        "avg_budget_per_day": 400,
        "best_seasons": ["春季", "秋季"],
    }

    return city_details


@router.get(
    "/cities/{city_id}/attractions",
    responses={
        200: {
            "description": "获取成功",
            "content": {"application/json": {"example": {"city": "北京", "attractions": [{"name": "故宫", "type": "景点", "duration": "3小时", "ticket": 60}, {"name": "长城", "type": "景点", "duration": "5小时", "ticket": 40}]}}}
        },
        404: {"description": "城市不存在", "content": {"application/json": {"example": {"error": "City not found"}}}}
    }
)
async def get_city_attractions(city_id: str):
    """
    获取城市景点列表

    路径参数:
        city_id: str 城市ID

    返回:
        {"city": str, "attractions": [...]} 城市名称和景点列表

    错误:
        {"error": "City not found"} 城市不存在
    """
    city = next((c for c in CITIES if c["id"] == city_id), None)
    if not city:
        return {"error": "City not found"}

    return {
        "city": city["name"],
        "attractions": [
            {"name": f"{city['name']}著名景点1", "type": "景点", "duration": "3小时", "ticket": 50},
            {"name": f"{city['name']}著名景点2", "type": "景点", "duration": "4小时", "ticket": 60},
        ]
    }


@router.get(
    "/regions",
    responses={
        200: {"description": "获取成功", "content": {"application/json": {"example": {"regions": ["华北", "华东", "西南", "西北", "华南"]}}}}
    }
)
async def list_regions():
    """
    列出所有地区

    返回:
        {"regions": [...]} 所有地区名称列表
    """
    regions = list(set(c["region"] for c in CITIES))
    return {"regions": regions}


@router.get(
    "/tags",
    responses={
        200: {"description": "获取成功", "content": {"application/json": {"example": {"tags": ["历史文化", "现代都市", "自然风光", "美食", "海滨"]}}}}
    }
)
async def list_tags():
    """
    列出所有标签

    返回:
        {"tags": [...]} 所有标签列表（去重）
    """
    all_tags = set()
    for city in CITIES:
        all_tags.update(city.get("tags", []))
    return {"tags": list(all_tags)}
