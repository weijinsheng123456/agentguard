"""质量门禁数据模型"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    BLOCKER = "BLOCKER"  # 阻止提交，需人工介入
    FIXABLE = "FIXABLE"  # 可自动修复
    INFO = "INFO"        # 仅记录


@dataclass
class Issue:
    """单个问题"""
    filepath: str
    line: int
    code: str            # e.g. "F821", "E722", "SYNTAX"
    message: str
    severity: Severity
    rule_name: str       # 发现此问题的规则名
    fixable: bool = True

    @property
    def short_path(self) -> str:
        """相对于 HERMES_HOME 的短路径"""
        home = Path.home() / ".hermes"
        try:
            return str(Path(self.filepath).relative_to(home))
        except ValueError:
            return self.filepath


@dataclass
class ScanResult:
    """一次扫描的结果"""
    total_files: int = 0
    new_files: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    stable_files: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    fixed_count: int = 0
    fixed_files: list[tuple[str, str]] = field(default_factory=list)  # [(path, desc)]
    failed_files: list[str] = field(default_factory=list)
    commit_count: int = 0

    @property
    def blockers(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.BLOCKER]

    @property
    def fixables(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.FIXABLE]

    @property
    def infos(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == Severity.INFO]

    @property
    def blocker_count(self) -> int:
        return len(self.blockers)

    @property
    def fixable_count(self) -> int:
        return len(self.fixables)

    @property
    def info_count(self) -> int:
        return len(self.infos)

    @property
    def total_issues(self) -> int:
        return len(self.issues)
