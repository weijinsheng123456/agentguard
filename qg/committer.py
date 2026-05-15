"""Git 精准提交模块。

职责：找到修复文件的 git 仓库 → 分组 → git add + commit
"""

from __future__ import annotations
import subprocess
import logging
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


def find_git_repo(filepath: str) -> Optional[str]:
    """找到文件所属的 git 仓库根目录"""
    p = Path(filepath).resolve()
    for parent in p.parents:
        if (parent / ".git").exists():
            return str(parent)
    return None


def auto_commit(fixed_files: list[tuple[str, str]]) -> dict:
    """自动提交修复后的文件。

    Args:
        fixed_files: list of (filepath, description)

    Returns:
        dict with keys: commit_count (int), details (list[str])
    """
    if not fixed_files:
        return {"commit_count": 0, "details": []}

    # 按仓库分组
    from collections import defaultdict
    repo_files: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for fp, desc in fixed_files:
        repo = find_git_repo(fp)
        if repo:
            repo_files[repo].append((fp, desc))
        else:
            logger.info(f"  ℹ️  不在git仓库中，跳过: {fp}")

    details = []
    commit_count = 0

    for repo, files in repo_files.items():
        repo_path = Path(repo)
        repo_name = repo_path.name

        # git add 修复文件
        for fp, _ in files:
            try:
                subprocess.run(
                    ["git", "add", fp],
                    cwd=repo, capture_output=True, text=True, timeout=10,
                )
            except subprocess.TimeoutExpired:
                pass

        # 检查是否有变更
        try:
            status = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=repo, capture_output=True, text=True, timeout=10,
            )
            if not status.stdout.strip():
                logger.info(f"  ✅ {repo_name}: 无变更需要提交")
                details.append(f"{repo_name}: 无变更")
                continue
        except subprocess.TimeoutExpired:
            continue

        # 构建提交信息
        desc_lines = []
        for fp, desc in files:
            short = Path(fp).relative_to(repo_path) if Path(fp).is_relative_to(repo_path) else fp
            desc_lines.append(f"  - {short}: {desc}")

        msg = "🤖 [质量门禁] 自动修复代码质量\n" + "\n".join(desc_lines)

        try:
            result = subprocess.run(
                ["git", "commit", "-F", "-"],
                cwd=repo, input=msg, capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                commit_count += 1
                logger.info(f"  ✅ {repo_name}: 已自动提交")
                details.append(f"{repo_name}: ✅ 已提交")
            else:
                logger.warning(f"  ⚠️  提交失败 {repo_name}: {result.stderr[:100]}")
                details.append(f"{repo_name}: ❌ {result.stderr[:50]}")
        except subprocess.TimeoutExpired:
            logger.warning(f"  ⚠️  提交超时 {repo_name}")
            details.append(f"{repo_name}: ⏰ 超时")

    return {"commit_count": commit_count, "details": details}
