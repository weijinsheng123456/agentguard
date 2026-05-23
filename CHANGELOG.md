# Changelog

All notable changes to AgentGuard will be documented in this file.

## v1.0.6 (2026-05-18)

### Added
- **Demo section** — ASCII terminal recording of `gate run` output in README
- **Screenshots section** — ASCII trend dashboard visualization in README
- **Scanner tests** — 4 new tests in `test_scanner.py` covering file discovery, empty dirs, ignore patterns
- **Clean shutdown** — SIGTERM/SIGINT handler now re-raises signal after cleanup for proper process termination
- **Reliable lock detection** — `_clean_qdrant_lock` uses `portalocker` instead of `lsof` for accurate stale lock detection

### Changed
- Bumped version to 1.0.6

## v1.0.0 (2026-05-11)

### Initial Release

- **Plugin architecture** — Python-based rule system with hot-pluggable rules
- **8 built-in rules** — Syntax check, ruff blocker/fixable, bare except, hardcoded paths, unsafe API detection, secret leak detection, AI hallucination detection
- **Agent behavior audit** — Reads agent trace data for daily quality reporting
- **Trend dashboard** — SQLite-backed quality trend tracking with text-based charts
- **Auto-fix pipeline** — Automatic fix with backup, verification, and git commit
- **CI integration** — GitHub Actions workflow (3 Python versions, lint + test)
- **CLI interface** — `gate run`, `audit`, `trend`, `install` commands
- **Configuration** — YAML-based config with scan directories, ignore patterns, severity rules
- **Pre-commit hook** — Quick check on staged files (`gate run --quick`)

## v6.0.0 (2026-05-23)

### 🚀 规则引擎扩容 (8→17条)
- 新增 sql_injection — f-string/format拼接SQL注入检测
- 新增 path_traversal — 未验证用户输入拼接路径
- 新增 mutable_defaults — 可变默认参数检测
- 新增 exception_quality — 空except/吞异常检测
- 新增 compare_with_is — is比较字符串/数字
- 新增 placeholder_check — TODO/FIXME/HACK残留
- 新增 performance — 循环内调sleep/open
- 新增 hardcoded_config — 硬编码URL/IP/路径
- 新增 logging_quality — print替代logging

### 📊 评分系统
- 五维度加权评分(A-F/0-100): 阻断率/修复率/覆盖/安全/趋势
- 每次扫描输出评级，趋势图显示评分变化

### 🛡️ 抑制系统
- #gate:ignore <rule_name> 单行抑制
- #gate:ignore-start/end 范围抑制

### 🧪 测试自动生成
- 对标 Qodo Cover: 自动生成pytest骨架+fixture
- 对变更文件批量生成，已有测试文件追加不覆盖

### 🔧 其他
- ruff_blocker 更新: F821+F541+E722 (移除已删除的E999)
- Dashboard: 评分趋势+等级显示
- DB: 兼容旧表(ALTER TABLE ADD COLUMN)

