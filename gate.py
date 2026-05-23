#!/usr/bin/env python3
"""AgentGuard v6 — CLI entry point

Usage:
    gate run                 Full scan + fix + commit + audit
    gate run --quick         Pre-commit quick check (staged files only)
    gate run --fixme         Fix currently staged files
    gate audit               Run Agent behavior audit
    gate trend [days]        View quality trend dashboard
    gate install             Initialize installation
    gate version             Version info
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure qg package is on path
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
    """Configure logging"""
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
    """Full scan + fix + commit + audit pipeline"""
    result = ScanResult()
    logger = logging.getLogger(__name__)

    logger.info("━" * 40)
    logger.info(f"  AgentGuard v{VERSION} — Full scan")
    logger.info("━" * 40)

    # Phase 1: 扫描
    scan_data = scan_all(config)
    result.total_files = len(scan_data["all_files"])
    result.new_files = scan_data["new_files"]
    result.changed_files = scan_data["changed_files"]
    result.stable_files = scan_data["stable_files"]

    logger.info(f"📦 {result.total_files} .py files")
    logger.info(f"🆕 New: {len(result.new_files)}  |  ✏️ Changed: {len(result.changed_files)}  |  ✅ Stable: {len(result.stable_files)}")

    unstable_files = result.new_files + result.changed_files
    scan_dir_paths = list(scan_data.get("scan_dirs", []))

    if not unstable_files:
        logger.info("   ✅ No changes to process")
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
                    logger.warning(f"⚠️  Verification: {len(verify_result['remaining'])} remaining issues")

            # Phase 5: 提交
            if result.fixed_files:
                commit_result = auto_commit(result.fixed_files)
                result.commit_count = commit_result["commit_count"]
        elif result.blocker_count > 0:
            logger.warning("⚠️  BLOCKER issues found, skipping auto-fix")

    # 全量关键项扫描（BLOCKER 级别）
    logger.info("🔍 Full scan for critical issues...")
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
        logger.warning(f"Score calculation failed: {e}")
        score_line = ""

    # 抑制过滤
    try:
        before = len(result.issues)
        result.issues = filter_suppressed(result.issues)
        filtered = before - len(result.issues)
        if filtered > 0:
            logger.info(f"🛡️ Suppressed: {filtered} #gate:ignore issues")
    except Exception as e:
        logger.warning(f"Suppression failed: {e}")

    # Agent审计
    logger.info("📊 Running Agent behavior audit...")
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
                logger.info(f"🧪 Generated {total} tests ({len(test_results)} files)")
                result._test_count = total
        except ImportError:
            pass  # testgen 模块不可用时跳过
        except Exception as e:
            logger.warning(f"Test generation failed: {e}")

    # 报告
    report_lines = generate_report(result, score_line)
    audit_lines = format_audit_report(audit_report)
    full_report = report_lines + [""] + audit_lines
    for line in full_report:
        logger.info(line)
    write_log(full_report)

    return result


def run_quick_check(config: dict) -> bool:
    """Quick check (for pre-commit hook)"""
    import subprocess

    logger = logging.getLogger(__name__)

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, timeout=10,
        )
        staged_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py")]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git not available, skipping quick check")
        return True

    if not staged_files:
        logger.info("✅ No Python files changed")
        return True

    logger.info(f"🔍 Quick check {len(staged_files)} staged Python files...")

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
        logger.error("❌ Commit blocked: quality issues remain")
        logger.error("💡 Run 'gate run --fixme' to auto-fix staged changes")
        return False

    logger.info("✅ Quick check passed")
    return True


def run_fix_staged(config: dict) -> bool:
    """Fix currently staged files"""
    import subprocess

    logger = logging.getLogger(__name__)

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True, text=True, timeout=10,
        )
        staged_files = [f for f in result.stdout.strip().split("\n") if f.endswith(".py") and Path(f).exists()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("git not available, skipping fixme")
        return False

    if not staged_files:
        logger.info("No Python file changes to fix")
        return True

    engine = Engine(config)
    issues = engine.diagnose_batch(staged_files)
    fixables = [i for i in issues if i.severity == Severity.FIXABLE and i.fixable]

    if not fixables:
        logger.info("✅ Nothing to auto-fix")
        return True

    fix_result = fix_issues(issues)
    if fix_result["fixed_count"] > 0:
        for fp, _ in fix_result["fixed_files"]:
            subprocess.run(["git", "add", fp], capture_output=True, timeout=10)
        logger.info(f"✅ Fixed {fix_result['fixed_count']} issues, re-staged")
    else:
        logger.info("✅ Nothing to auto-fix")

    return True


def run_audit():
    """Run Agent behavior audit only"""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("📊 Running Agent behavior audit...")
    report = audit_agent(days=7)
    lines = format_audit_report(report)
    for line in lines:
        print(line)
    return report


def show_trend(days: int = 14):
    """Display quality trend dashboard"""
    data = get_trend(days)
    lines = format_trend_chart(data)
    for line in lines:
        print(line)


def install():
    """Initialize installation"""

    logger = logging.getLogger(__name__)
    qg_dir = QG_DIR

    logger.info("📁 Creating directory structure...")
    for d in ["modules", "hooks", "lib", "backups"]:
        (qg_dir / d).mkdir(parents=True, exist_ok=True)

    logger.info("🔐 Setting execute permissions...")
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
                    logger.info(f"  ✅ Hook installed: {parent.name}")
                break

    logger.info("🗂️  Initializing file manifest...")
    config = load_config()
    scan_data = scan_all(config)
    update_manifest(scan_data["all_files"])
    logger.info(f"  ✅ Recorded {len(scan_data['all_files'])} files")

    logger.info("✅ Installation complete!")
    logger.info("Usage:")
    logger.info("  gate run             Full scan + fix + commit + audit")
    logger.info("  gate run --quick     Quick check staged files")
    logger.info("  gate run --fixme     Auto-fix staged files")
    logger.info("  gate audit           Agent behavior audit only")
    logger.info("  gate trend [days]    View trend dashboard")


def main():
    parser = argparse.ArgumentParser(description=f"AgentGuard v{VERSION} — AI-native quality gate")
    parser.add_argument("command", nargs="?", default="run",
                        help="Command: run/install/version/audit/trend (default: run)")
    parser.add_argument("--quick", action="store_true", help="Quick check staged files only")
    parser.add_argument("--fixme", action="store_true", help="Auto-fix staged files")
    parser.add_argument("--full", action="store_true", help="Force full scan (ignore manifest cache)")

    args = parser.parse_args()

    if args.command == "version":
        print(f"AgentGuard v{VERSION}")
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
