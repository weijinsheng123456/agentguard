#!/usr/bin/env python3
"""Hermes 质量门禁 v5 — CLI 主入口

用法:
    gate run                 完整扫描+修复+提交+审计
    gate run --quick         Pre-commit快速检查
    gate run --fixme         修复当前staged文件
    gate audit               单独运行Agent行为审计
    gate trend [天数]        查看质量趋势仪表盘
    gate install             初始化安装
    gate version             版本信息
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# 确保 qg 包在路径上
QG_HOME = Path(__file__).resolve().parent
sys.path.insert(0, str(QG_HOME))

from qg.auditor import audit_agent, format_audit_report
from qg.committer import auto_commit
from qg.config import QG_HOME as QG_DIR
from qg.config import load_config
from qg.dashboard import format_trend_chart, get_trend, save_metrics
from qg.engine import Engine
from qg.fixer import fix_issues
from qg.models import ScanResult, Severity
from qg.reporter import generate_report, write_log
from qg.scanner import scan_all, update_manifest
from qg.scorer import ScoreCalculator
from qg.suppress import filter_suppressed
from qg.verifier import verify_fixes

VERSION = "6.0.0"


def setup_logging():
    """配置日志"""
    log_dir = Path.home() / ".hermes" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "quality-gate.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler(),
        ],
    )


def run_full_scan(config: dict) -> ScanResult:
    """完整扫描+修复+提交+审计流程"""
    result = ScanResult()
    logger = logging.getLogger(__name__)

    logger.info("━" * 40)
    logger.info(f"  质量门禁 v{VERSION} — 全量扫描")
    logger.info("━" * 40)

    # Phase 1: 扫描
    scan_data = scan_all(config)
    result.total_files = len(scan_data["all_files"])
    result.new_files = scan_data["new_files"]
    result.changed_files = scan_data["changed_files"]
    result.stable_files = scan_data["stable_files"]

    logger.info(f"📦 共 {result.total_files} 个 .py 文件")
    logger.info(f"🆕 新增: {len(result.new_files)}  |  ✏️ 修改: {len(result.changed_files)}  |  ✅ 稳定: {len(result.stable_files)}")

    unstable_files = result.new_files + result.changed_files
    scan_dir_paths = list(scan_data.get("scan_dirs", []))

    if not unstable_files:
        logger.info("   ✅ 无新代码需要处理")
    else:
        # Phase 2: 诊断（目录级+文件级）
        engine = Engine(config)
        result.issues = engine.diagnose_batch(unstable_files, scan_dir_paths)

        logger.info(f"🔴 BLOCKER: {result.blocker_count}  |  🟡 FIXABLE: {result.fixable_count}  |  🔵 INFO: {result.info_count}")

        # Phase 3: 修复
        if result.blocker_count == 0 and result.fixable_count > 0:
            fix_result = fix_issues(result.issues)
            result.fixed_count = fix_result["fixed_count"]
            result.fixed_files = fix_result["fixed_files"]
            result.failed_files = fix_result["failed_files"]

            # Phase 4: 复验
            if result.fixed_files:
                verify_result = verify_fixes(result.fixed_files)
                if not verify_result["passed"]:
                    logger.warning(f"⚠️  复验发现 {len(verify_result['remaining'])} 个残留问题")

            # Phase 5: 提交
            if result.fixed_files:
                commit_result = auto_commit(result.fixed_files)
                result.commit_count = commit_result["commit_count"]
        elif result.blocker_count > 0:
            logger.warning("⚠️  有 BLOCKER 问题，跳过自动修复")

    # 全量关键项扫描（BLOCKER 级别）
    logger.info("🔍 全量关键项扫描...")
    engine = Engine(config)
    all_issues = engine.diagnose_batch(scan_data["all_files"], scan_dir_paths)
    blocker_issues = [i for i in all_issues if i.severity == Severity.BLOCKER]
    existing_blocker_paths = {(i.filepath, i.line, i.code) for i in result.issues}
    for bi in blocker_issues:
        key = (bi.filepath, bi.line, bi.code)
        if key not in existing_blocker_paths:
            result.issues.append(bi)
            existing_blocker_paths.add(key)

    # 更新 manifest
    update_manifest(scan_data["all_files"])
    # Phase 8: 评分 + 抑制 + Agent审计 + 趋势 + 报告
    # 评分
    try:
        scorer = ScoreCalculator()
        score_result = scorer.calculate(result.issues, result)
        score_line = scorer.summary_line(score_result)
        logger.info(f"📊 {score_line}")
    except Exception as e:
        logger.warning(f"评分计算失败: {e}")
        score_line = ""

    # 抑制过滤
    try:
        before = len(result.issues)
        result.issues = filter_suppressed(result.issues)
        filtered = before - len(result.issues)
        if filtered > 0:
            logger.info(f"🛡️ 抑制过滤: 移除了 {filtered} 个被 # gate:ignore 标记的问题")
    except Exception as e:
        logger.warning(f"抑制过滤失败: {e}")

    # Agent审计
    logger.info("📊 运行Agent行为审计...")
    audit_report = audit_agent(days=7)
    result._audit = audit_report

    # 保存趋势（含评分）
    score_val = score_result.score if 'score_result' in locals() and score_result else None
    save_metrics(result, score_val)

    # 测试生成
    if config.get("test_generation", {}).get("enabled", True) and unstable_files:
        try:
            from qg.testgen import generate_batch
            test_results = generate_batch(unstable_files)
            if test_results:
                total = sum(r["test_count"] for r in test_results)
                logger.info(f"🧪 自动生成 {total} 个测试 ({len(test_results)} 个文件)")
                result._test_count = total
        except ImportError:
            pass  # testgen 模块不可用时跳过
        except Exception as e:
            logger.warning(f"测试生成失败: {e}")

    # 报告
    report_lines = generate_report(result, score_line)
    audit_lines = format_audit_report(audit_report)
    full_report = report_lines + [""] + audit_lines
    for line in full_report:
        logger.info(line)
    write_log(full_report)

    return result


def run_quick_check(config: dict) -> bool:
    """快速检查（给 pre-commit 用）"""
    import subprocess

    logger = logging.getLogger(__name__)

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, timeout=10,
        )
        staged_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]
    except subprocess.TimeoutExpired:
        logger.error("git diff 超时")
        return True

    if not staged_files:
        logger.info("✅ 无Python文件变更")
        return True

    logger.info(f"🔍 快速检查 {len(staged_files)} 个 staged Python 文件...")

    engine = Engine(config)
    has_errors = False

    for f in staged_files:
        if not Path(f).exists():
            continue
        issues = engine.diagnose_file(f)
        blockers = [i for i in issues if i.severity == Severity.BLOCKER]

        if blockers:
            for i in blockers:
                logger.error(f"❌ {i.short_path}:L{i.line}  {i.code} — {i.message}")
            has_errors = True

    if has_errors:
        logger.error("❌ 提交被阻止：有质量问题未修复")
        logger.error("💡 运行 'gate run --fixme' 自动修复当前变更")
        return False

    logger.info("✅ 快速检查通过")
    return True


def run_fix_staged(config: dict) -> bool:
    """修复当前 staged 文件"""
    import subprocess

    logger = logging.getLogger(__name__)

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, timeout=10,
        )
        staged_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py") and Path(f).exists()]
    except subprocess.TimeoutExpired:
        logger.error("git diff 超时")
        return False

    if not staged_files:
        logger.info("没有Python文件的变更需要修复")
        return True

    engine = Engine(config)
    issues = engine.diagnose_batch(staged_files)
    fixables = [i for i in issues if i.severity == Severity.FIXABLE and i.fixable]

    if not fixables:
        logger.info("✅ 无可自动修复项")
        return True

    fix_result = fix_issues(issues)
    if fix_result["fixed_count"] > 0:
        for fp, _ in fix_result["fixed_files"]:
            subprocess.run(["git", "add", fp], capture_output=True, timeout=10)
        logger.info(f"✅ 已修复 {fix_result['fixed_count']} 处并重新staged")
    else:
        logger.info("✅ 无可自动修复项")

    return True


def run_audit():
    """单独运行Agent行为审计"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("📊 运行Agent行为审计...")
    report = audit_agent(days=7)
    lines = format_audit_report(report)
    for line in lines:
        print(line)
    return report


def show_trend(days: int = 14):
    """显示质量趋势仪表盘"""
    data = get_trend(days)
    lines = format_trend_chart(data)
    for line in lines:
        print(line)


def install():
    """初始化安装"""

    logger = logging.getLogger(__name__)
    qg_dir = QG_DIR

    logger.info("📁 创建目录结构...")
    for d in ["modules", "hooks", "lib", "backups"]:
        (qg_dir / d).mkdir(parents=True, exist_ok=True)

    logger.info("🔐 设置执行权限...")
    gate_script = Path(__file__)
    gate_script.chmod(0o755)

    hook_src = qg_dir / "hooks" / "pre-commit"
    if hook_src.exists():
        hook_src.chmod(0o755)

    scan_dirs = load_config().get("scan_dirs", [])
    for d in scan_dirs:
        expanded = Path(d).expanduser().resolve()
        if not expanded.exists():
            continue
        for parent in expanded.parents:
            if (parent / ".git").exists():
                hook_dst = parent / ".git" / "hooks" / "pre-commit"
                if hook_src.exists():
                    import shutil
                    shutil.copy2(str(hook_src), str(hook_dst))
                    hook_dst.chmod(0o755)
                    logger.info(f"  ✅ 钩子已安装: {parent.name}")
                break

    logger.info("🗂️  初始化文件清单...")
    config = load_config()
    scan_data = scan_all(config)
    update_manifest(scan_data["all_files"])
    logger.info(f"  ✅ 已记录 {len(scan_data['all_files'])} 个文件")

    logger.info("✅ 安装完成！")
    logger.info("用法:")
    logger.info("  gate run             完整扫描+修复+提交+审计")
    logger.info("  gate run --quick     快速检查")
    logger.info("  gate run --fixme     修复当前变更")
    logger.info("  gate audit           单独审计")
    logger.info("  gate trend [天数]    趋势仪表盘")


def main():
    parser = argparse.ArgumentParser(description=f"Hermes 质量门禁 v{VERSION}")
    parser.add_argument("command", nargs="?", default="run",
                        help="命令: run/install/version/audit/trend (default: run)")
    parser.add_argument("--quick", action="store_true", help="快速检查 staged 文件")
    parser.add_argument("--fixme", action="store_true", help="修复当前 staged 文件")
    parser.add_argument("--full", action="store_true", help="强制全量扫描")

    args = parser.parse_args()

    if args.command == "version":
        print(f"Hermes 质量门禁 v{VERSION}")
        return

    if args.command == "install":
        setup_logging()
        install()
        return

    if args.command == "audit":
        run_audit()
        return

    if args.command == "trend":
        show_trend()
        return

    # run
    setup_logging()
    config = load_config()

    if args.quick:
        success = run_quick_check(config)
        sys.exit(0 if success else 1)
    elif args.fixme:
        run_fix_staged(config)
    else:
        result = run_full_scan(config)

        # 输出报告+审计
        report_lines = generate_report(result)
        audit_report = getattr(result, '_audit', None)
        if audit_report:
            audit_lines = format_audit_report(audit_report)
            combined = report_lines + [""] + audit_lines
        else:
            combined = report_lines

        print("\n" + "\n".join(combined))

        if result.blocker_count > 0:
            sys.exit(2)
        elif result.total_issues > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
