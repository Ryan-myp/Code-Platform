
"""
类型注解支持模块
"""

from typing import (
    Any, Optional, Union, List, Dict, Tuple, Callable, Set, 
    TypeVar, Generic, Iterator, Sequence, Mapping, Iterable,
    Awaitable, Coroutine, Type, TypeVar, Protocol
)
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import asyncio
import json
import os
from pathlib import Path as PathLib

# 泛型类型变量
T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

# 常用类型别名
JsonValue = Union[str, int, float, bool, None, List['JsonValue'], Dict[str, 'JsonValue']]
AnyDict = Dict[str, Any]
AnyList = List[Any]
StringOrPath = Union[str, PathLib]


@dataclass
class TypeInfo:
    """类型信息数据类"""
    name: str
    type: type
    default: Any = None
    required: bool = True
    
    def __post_init__(self):
        if self.default is None and self.required:
            raise ValueError(f"Required field {self.name} has no default")


def validate_type(value: Any, expected_type: type, field_name: str = "") -> bool:
    """验证值的类型"""
    if not isinstance(value, expected_type):
        return False
    return True


def safe_cast(value: Any, target_type: type, default: Any = None) -> Any:
    """安全类型转换"""
    try:
        return target_type(value)
    except (ValueError, TypeError):
        return default


def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """合并字典"""
    result = base.copy()
    result.update(override)
    return result


def filter_dict(data: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    """过滤字典"""
    return {k: v for k, v in data.items() if k in keys}


def ensure_list(value: Any) -> List[Any]:
    """确保值为列表"""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """列表分块"""
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_list(nested: List[List[Any]]) -> List[Any]:
    """展平嵌套列表"""
    return [item for sublist in nested for item in sublist]


def dict_to_object(data: Dict[str, Any], class_type: Type[T]) -> T:
    """字典转对象"""
    return class_type(**data)


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """格式化时间戳"""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")
