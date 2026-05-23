"""智能修复引擎。

职责：接收问题列表 → 按文件分组 → 备份 → 调用规则修复 → 验证语法
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from .config import QG_HOME
from .models import Issue, Severity
from .rules.base import discover_rules, get_all_rules

logger = logging.getLogger(__name__)


def backup_file(filepath: str) -> Optional[Path]:
    """备份文件到 backups/ 目录"""
    src = Path(filepath)
    if not src.exists():
        return None
    backup_dir = QG_HOME / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    content = src.read_bytes()
    md5 = hashlib.md5(content).hexdigest()
    backup_path = backup_dir / f"{md5}.bak"
    if not backup_path.exists():
        backup_path.write_bytes(content)
    return backup_path


def restore_file(backup_path: Path, filepath: str):
    """从备份恢复"""
    dst = Path(filepath)
    dst.write_bytes(backup_path.read_bytes())


def fix_issues(issues: list[Issue]) -> dict:
    """尝试自动修复所有 FIXABLE 问题。

    Returns:
        dict with keys: fixed_count, fixed_files (list of (path, desc)),
                        failed_files (list of paths)
    """
    # 只处理 FIXABLE 的问题
    fixable = [i for i in issues if i.severity == Severity.FIXABLE and i.fixable]
    if not fixable:
        return {"fixed_count": 0, "fixed_files": [], "failed_files": []}

    # 发现规则实例
    discover_rules()
    rule_instances = {cls().name: cls() for cls in get_all_rules()}

    # 按文件分组
    from collections import defaultdict
    file_issues: dict[str, list[Issue]] = defaultdict(list)
    for issue in fixable:
        file_issues[issue.filepath].append(issue)

    fixed_files: list[tuple[str, str]] = []
    failed_files: list[str] = []
    total_fixed = 0

    for filepath, file_issue_list in file_issues.items():
        src = Path(filepath)
        if not src.exists():
            continue

        # 备份
        backup = backup_file(filepath)
        before_hash = hashlib.md5(src.read_bytes()).hexdigest()
        file_fixed = 0

        # 按规则分组修复
        from collections import defaultdict as dd
        by_rule: dict[str, list[Issue]] = dd(list)
        for i in file_issue_list:
            by_rule[i.rule_name].append(i)

        for rule_name, rule_issues in by_rule.items():
            rule = rule_instances.get(rule_name)
            if rule is None:
                continue
            # 先全局修复（ruff_fixable 对整个文件跑 ruff --fix）
            # 如果是 ruff_fixable 用全局修复，否则逐个问题修
            if rule_name == "ruff_fixable":
                if rule.fix(filepath, rule_issues[0]):
                    file_fixed += len(rule_issues)
            else:
                for issue in rule_issues:
                    try:
                        if rule.fix(filepath, issue):
                            file_fixed += 1
                    except Exception as e:
                        logger.warning(f"Fix {filepath}:L{issue.line} failed: {e}")

        # 验证语法
        if file_fixed > 0:
            import py_compile
            try:
                py_compile.compile(filepath, doraise=True)
                total_fixed += file_fixed
                desc = f"修复 {file_fixed} 处: "
                codes = sorted(set(i.code for i in file_issue_list))
                desc += ", ".join(codes)
                fixed_files.append((filepath, desc))
                logger.info(f"✅ {filepath}: {desc}")
            except py_compile.PyCompileError:
                # 修坏了，回滚
                if backup:
                    restore_file(backup, filepath)
                failed_files.append(filepath)
                logger.warning(f"❌ Fix caused syntax error, rolled back: {filepath}")
        else:
            # 没变化，不用管
            pass

    return {
        "fixed_count": total_fixed,
        "fixed_files": fixed_files,
        "failed_files": failed_files,
    }
