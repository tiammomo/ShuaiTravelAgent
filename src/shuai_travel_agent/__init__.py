"""
ShuaiTravelAgent - AI Travel Recommendation System

A custom single-agent architecture based travel assistant system integrated with GPT-4o-mini.
Provides city recommendations, attraction queries, and route planning.
"""

__version__ = "1.0.0"
__author__ = "Shuai"

from .agent import TravelAgent
from .config_manager import ConfigManager
from .memory_manager import MemoryManager
from .llm_client import LLMClient
from .reasoner import Reasoner, IntentType
from .environment import Environment

__all__ = [
    "TravelAgent",
    "ConfigManager",
    "MemoryManager",
    "LLMClient",
    "Reasoner",
    "IntentType",
    "Environment",
]
