"""规则插件基类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from qg.models import Issue, Severity


class Rule(ABC):
    """文件级规则基类。对每个文件逐一运行。"""

    name: str = ""
    severity: Severity = Severity.INFO
    description: str = ""
    languages: list[str] = ["python"]

    def should_check(self, filepath: str) -> bool:
        """判断是否应该检查此文件"""
        return filepath.endswith(".py")

    @abstractmethod
    def diagnose(self, filepath: str) -> list[Issue]:
        """检查文件，返回发现的问题列表"""
        ...

    def fix(self, filepath: str, issue: Issue) -> bool:
        """尝试自动修复一个问题，返回是否成功。
        默认不可修复，子类按需重写。
        """
        return False


class BatchRule(ABC):
    """目录级规则基类。对整个目录批量运行（更快，适合 ruff/scalable 工具）。"""

    name: str = ""
    severity: Severity = Severity.INFO
    description: str = ""
    languages: list[str] = ["python"]

    @abstractmethod
    def diagnose_batch(self, scan_dirs: list[str]) -> list[Issue]:
        """批量检查多个目录，返回发现的问题列表"""
        ...

    def fix(self, filepath: str, issue: Issue) -> bool:
        """尝试自动修复"""
        return False


# ── 规则注册表 ──

_RULES: dict[str, type] = {}


def register_rule(rule_cls: type):
    """注册规则到全局注册表"""
    name = rule_cls.name
    if not name:
        raise ValueError(f"Rule class {rule_cls.__name__} must have a 'name' attribute")
    if name in _RULES:
        raise ValueError(f"Rule '{name}' already registered")
    _RULES[name] = rule_cls
    return rule_cls  # keep decorator chainable


def get_all_rules() -> list[type]:
    """获取所有已注册的规则类"""
    return list(_RULES.values())


def get_rule(name: str) -> Optional[type]:
    """按名称获取规则"""
    return _RULES.get(name)


# ── 自动发现 rules 目录下所有规则 ──

def discover_rules(package_path: Optional[str] = None):
    """自动发现并注册所有规则模块"""
    import importlib
    import pkgutil

    try:
        pkg = importlib.import_module("qg.rules")
    except ImportError:
        return

    for importer, modname, ispkg in pkgutil.iter_modules(pkg.__path__):
        if modname.startswith("_") or modname == "base":
            continue
        try:
            importlib.import_module(f"qg.rules.{modname}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"加载规则模块 {modname} 失败: {e}")
