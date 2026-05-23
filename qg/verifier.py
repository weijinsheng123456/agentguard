"""修复后复验模块。

职责：对已修复文件重新诊断 → 确认修复成功 → 报告残留
"""

from __future__ import annotations

import logging

from .engine import Engine

logger = logging.getLogger(__name__)


def verify_fixes(fixed_files: list[tuple[str, str]]) -> dict:
    """对已修复文件重新诊断，确认修复是否彻底。

    Args:
        fixed_files: list of (filepath, description)

    Returns:
        dict with keys: passed (bool), remaining (list of Issue)
    """
    if not fixed_files:
        return {"passed": True, "remaining": []}

    engine = Engine()
    filepaths = [f[0] for f in fixed_files]
    issues = engine.diagnose_batch(filepaths)

    # 只关心之前修过的规则类型
    relevant_codes = {"F401", "F841", "E711", "E712", "E722", "HARDCODE"}
    remaining = [i for i in issues if i.code in relevant_codes]

    if remaining:
        logger.warning(f"Verification: {len(remaining)} remaining issues")
        for i in remaining:
            logger.warning(f"  {i.short_path}:L{i.line} {i.code}")
        return {"passed": False, "remaining": remaining}
    else:
        logger.info(f"✅ All fixes verified ({len(filepaths)} files)")
        return {"passed": True, "remaining": []}
