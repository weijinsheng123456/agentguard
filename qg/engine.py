"""诊断引擎 — 加载规则 → 调度到文件/目录 → 收集问题。

支持双模式：
- 文件级规则：逐文件运行（语法检查、AST分析等）
- 目录级规则：对整个目录批量运行（ruff 批量扫描更快）
"""

from __future__ import annotations
import logging
from typing import Optional

from .models import Issue, Severity
from .rules.base import discover_rules, get_all_rules, Rule, BatchRule
from .config import load_config


logger = logging.getLogger(__name__)


class Engine:
    """诊断引擎。负责加载规则、调度到文件/目录、收集结果。"""

    def __init__(self, config: Optional[dict] = None):
        self.config = config or load_config()
        # 自动发现并加载规则
        discover_rules()
        all_rule_classes = get_all_rules()
        self.file_rules: list[Rule] = []
        self.batch_rules: list[BatchRule] = []
        for cls in all_rule_classes:
            instance = cls()
            if isinstance(instance, BatchRule):
                self.batch_rules.append(instance)
            else:
                self.file_rules.append(instance)
        logger.info(f"引擎加载 {len(all_rule_classes)} 条规则: "
                     f"({len(self.file_rules)} 文件级 + {len(self.batch_rules)} 目录级)")

    def diagnose_batch(self, files: list[str], scan_dirs: Optional[list[str]] = None) -> list[Issue]:
        """对一批文件/目录运行所有适用规则。
        
        目录级规则在 scan_dirs 上运行（更快），
        文件级规则在 files 上逐文件运行（更精确）。
        """
        all_issues: list[Issue] = []

        # Phase 1: 目录级规则（批量，快）
        if scan_dirs and self.batch_rules:
            dir_issues: list[Issue] = []
            for rule in self.batch_rules:
                try:
                    found = rule.diagnose_batch(scan_dirs)
                    dir_issues.extend(found)
                except Exception as e:
                    logger.warning(f"目录级规则 {rule.name} 异常: {e}")
            all_issues.extend(dir_issues)
            logger.info(f"  目录级规则: {len(dir_issues)} 个问题")

        # Phase 2: 文件级规则（逐文件，慢）
        if files and self.file_rules:
            file_issues: list[Issue] = []
            for f in files:
                for rule in self.file_rules:
                    try:
                        if rule.should_check(f):
                            found = rule.diagnose(f)
                            file_issues.extend(found)
                    except Exception as e:
                        logger.warning(f"规则 {rule.name} 检查 {f} 异常: {e}")
            all_issues.extend(file_issues)
            logger.info(f"  文件级规则: {len(file_issues)} 个问题")

        return all_issues

    def diagnose_file(self, filepath: str) -> list[Issue]:
        """对单个文件运行所有适用规则（pre-commit 用）"""
        issues: list[Issue] = []
        for rule in self.file_rules:
            try:
                if rule.should_check(filepath):
                    found = rule.diagnose(filepath)
                    issues.extend(found)
            except Exception as e:
                logger.warning(f"规则 {rule.name} 检查 {filepath} 异常: {e}")
        return issues

    def get_blockers(self, issues: list[Issue]) -> list[Issue]:
        return [i for i in issues if i.severity == Severity.BLOCKER]

    def get_fixables(self, issues: list[Issue]) -> list[Issue]:
        return [i for i in issues if i.severity == Severity.FIXABLE]

    def get_infos(self, issues: list[Issue]) -> list[Issue]:
        return [i for i in issues if i.severity == Severity.INFO]
