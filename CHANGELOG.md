# Changelog

All notable changes to AgentGuard will be documented in this file.

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
