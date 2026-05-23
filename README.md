<p align="center">
  <img src="https://img.shields.io/badge/AgentGuard-6.0.0-8A2BE2?style=for-the-badge&logo=python&logoColor=white" width="300" alt="AgentGuard">
</p>

<p align="center">
  <em>AI-native quality gate for agent-generated code.</em>
  <br>
  Scan · Audit · Auto-fix · Track trends
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#commands">Commands</a> •
  <a href="#demo">Demo</a> •
  <a href="#rules">Rules</a> •
  <a href="#write-custom-rules">Custom Rules</a>
</p>

<p align="center">
  <a href="https://github.com/weijinsheng123456/agentguard/actions">
    <img src="https://img.shields.io/github/actions/workflow/status/weijinsheng123456/agentguard/ci.yml?branch=main&label=CI&logo=github&color=success" alt="CI">
  </a>
  <a href="https://pypi.org/project/agentguard-tool/">
    <img src="https://img.shields.io/pypi/v/agentguard-tool?label=PyPI&logo=pypi&color=blue" alt="PyPI">
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License">
  </a>
  <a href="https://github.com/weijinsheng123456/agentguard/stargazers">
    <img src="https://img.shields.io/github/stars/weijinsheng123456/agentguard?style=social" alt="Stars">
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue?logo=python" alt="Python">
  </a>
  <a href="https://github.com/weijinsheng123456/agentguard/blob/main/CHANGELOG.md">
    <img src="https://img.shields.io/badge/version-6.0.0-8A2BE2" alt="Version">
  </a>
</p>

---

# 🚀 Install in 3 seconds

```bash
pip install agentguard-tool
cd your-project
gate run
```

Done. AgentGuard scans your code, detects AI-specific issues (hardcoded secrets, unsafe APIs, hallucinations), auto-fixes what it can, and tracks quality trends over time.

---

## Why AgentGuard?

Traditional linters like SonarQube and CodeQL were built for **human-written code**. AI agents write code differently — they hallucinate module names, leave placeholder comments, generate giant functions, and introduce patterns that human linters miss.

**AgentGuard is built for the age of AI-generated code.**

It understands the patterns, pitfalls, and security risks specific to code written by LLMs. It runs as a CI-ready CLI, a pre-commit hook, or a daily cron.

---

## Features

### 🔍 AI-Specific Detection (3 rules)
| Rule | Severity | What It Finds |
|------|----------|---------------|
| `unsafe_api` | 🚫 BLOCKER | `eval()`, `exec()`, `os.system()`, `subprocess(shell=True)`, `pickle.loads()` |
| `secret_leak` | 🚫 BLOCKER | Hardcoded API keys, tokens, passwords in source code |
| `ai_hallucination` | ℹ️ INFO | AI placeholder comments, suspicious module names, giant auto-generated functions |

### 📊 Agent Behavior Audit
Reads agent trace data and produces a daily report:
- Tool call frequency & ranking
- Error rate & anomaly detection
- Token consumption & cost estimates
- Model usage distribution

### 📈 Trend Dashboard
Text-based trend chart with zero external dependencies:
```
━━━ 📈 Quality Trend (Last 14 days) ━━━
  05/08 ████████████████   0 issues  ✅
  05/09 ████████████░░░░   3 issues  ⚠️
  05/10 ████████████████   0 issues  ✅
```
Data persists in SQLite. View anytime with `gate trend`.

### 🔧 Auto-Fix Pipeline
Automatically fixes what it can, backed up and git-committed:
- Unused imports (`F401`) and variables (`F841`)
- Bare `except:` → `except Exception:`
- Hardcoded paths → `$HOME` references
- Ruff-safe auto-fixes

### 🧩 Plugin Rule Architecture
Rules are Python classes. Adding a new rule = one file, one class, one decorator.
```python
@register_rule
class MyRule(Rule):
    name = "my_rule"
    severity = Severity.BLOCKER

    def diagnose(self, filepath: str) -> list[Issue]:
        # Your detection logic here
        ...
```

---

## Quick Start

```bash
# 🎯 Scan your project
pip install agentguard-tool
cd your-project
gate run

# 🔍 Quick check (staged files only)
gate run --quick

# 📊 Agent behavior audit
gate audit

# 📈 View quality trends
gate trend

# 🔧 Install pre-commit hooks
gate install
```

### Run from source
```bash
git clone https://github.com/weijinsheng123456/agentguard.git
cd agentguard
python gate.py run
```

---

## Demo

Terminal recording of a realistic `gate run` session:

```text
$ gate run
2026-05-18 09:42:11,238 [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-05-18 09:42:11,238 [INFO]   质量门禁 v1.0.0 — 全量扫描
2026-05-18 09:42:11,238 [INFO] ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2026-05-18 09:42:11,271 [INFO] 📦 共 42 个 .py 文件
2026-05-18 09:42:11,271 [INFO] 🆕 新增: 2  |  ✏️ 修改: 5  |  ✅ 稳定: 35
2026-05-18 09:42:11,279 [INFO] 引擎加载 8 条规则: (6 文件级 + 2 目录级)
2026-05-18 09:42:11,414 [INFO]   目录级规则: 2 个问题
2026-05-18 09:42:11,438 [INFO]   文件级规则: 3 个问题
2026-05-18 09:42:11,438 [INFO] 🔴 BLOCKER: 2  |  🟡 FIXABLE: 2  |  🔵 INFO: 1
2026-05-18 09:42:11,438 [WARNING] ⚠️  有 BLOCKER 问题，跳过自动修复
2026-05-18 09:42:11,438 [INFO] 🔍 全量关键项扫描...
2026-05-18 09:42:11,481 [INFO] 📊 运行Agent行为审计...

━━━ ⚠️ 质量门禁 05/18 ━━━
扫描: 42 个文件（+2/~5）
阻塞: 2 项 ❌ 需人工
  ❌ src/agent/tools.py:L18  UNSAFE_SYSTEM
  ❌ src/config.py:L7  LEAK_SECRET

━━━ 🤖 Agent行为审计 (7天) ━━━
Tool调用: 128 次
错误率: 2.3% ✅
Token消耗: 184,320
Top工具: edit, shell, read_file
```

## Screenshots

Trend dashboard output from `gate trend`:

```text
$ gate trend
━━━ 📈 质量门禁趋势 (最近14天) ━━━
  05-05 ████░░░░░░░░░░░░   3问题 修2 ✅
  05-06 ██████████░░░░░░   7问题 修4 ❌1 ❌
  05-07 ██░░░░░░░░░░░░░░   1问题 ✅
  05-08 █░░░░░░░░░░░░░░░   0问题 ✅
  05-09 ███████░░░░░░░░░   5问题 修3 ⚠️
  05-10 █░░░░░░░░░░░░░░░   0问题 ✅
  05-11 ███░░░░░░░░░░░░░   2问题 修2 ⚠️
  05-12 █░░░░░░░░░░░░░░░   0问题 ✅
  05-13 █████░░░░░░░░░░░   4问题 修1 ❌1 ❌
  05-14 █░░░░░░░░░░░░░░░   0问题 ✅
  05-15 ███░░░░░░░░░░░░░   2问题 修2 ⚠️
  05-16 ██░░░░░░░░░░░░░░   1问题 ✅
  05-17 █░░░░░░░░░░░░░░░   0问题 ✅
  05-18 █░░░░░░░░░░░░░░░   0问题 ✅

文件数趋势:
  05-12 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░ 38
  05-13 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░ 39
  05-14 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░ 39
  05-15 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░ 41
  05-16 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░ 41
  05-17 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░ 42
  05-18 ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░ 42

日均问题数: 1.8
健康天数: 6/14
```

## Commands

| Command | Description |
|---------|-------------|
| `gate run` | Full scan + auto-fix + commit + audit |
| `gate run --quick` | Pre-commit check (staged files only) |
| `gate run --fixme` | Auto-fix staged files |
| `gate audit` | Agent behavior audit only |
| `gate trend [N]` | Show last N days of quality trends |
| `gate install` | Install pre-commit hooks & cron |
| `gate version` | Show version |

---

## Rules

### Built-in Rules (8 total)

**Code Quality (ported from ruff):**
| Rule | Code | Severity | Auto-fix |
|------|------|----------|:--------:|
| `syntax_check` | `SYNTAX` | BLOCKER | ❌ |
| `ruff_blocker` | `F821`, `E999` | BLOCKER | ❌ |
| `ruff_fixable` | `F401`, `F841`, `E711`, `E712` | FIXABLE | ✅ |
| `bare_except` | `E722` | FIXABLE | ✅ |
| `hardcoded_paths` | `HARDCODE` | FIXABLE | ✅ |

**AI-Specific:**
| Rule | Code | Severity | Auto-fix |
|------|------|----------|:--------:|
| `unsafe_api` | `UNSAFE_*` | BLOCKER | ❌ |
| `secret_leak` | `LEAK_SECRET` | BLOCKER | ❌ |
| `ai_hallucination` | `AI_*` | INFO | ❌ |

---

## Write Custom Rules

Create a new `.py` file in `qg/rules/`:

```python
from qg.models import Issue, Severity
from qg.rules.base import Rule, register_rule

@register_rule
class MyCustomRule(Rule):
    name = "my_custom_rule"
    severity = Severity.FIXABLE
    description = "Detects something specific"

    def should_check(self, filepath: str) -> bool:
        return filepath.endswith(".py")

    def diagnose(self, filepath: str) -> list[Issue]:
        issues = []
        # Your detection logic...
        return issues

    def fix(self, filepath: str, issue: Issue) -> bool:
        # Your fix logic...
        return True
```

Rules support two modes:
- **`Rule`** — per-file scanning (for AST analysis, regex)
- **`BatchRule`** — directory-level scanning (for ruff, 10-50x faster)

---

## Configuration

```yaml
scan_dirs:
  - "~/my-project/src"
  - "~/my-project/scripts"

ignore_patterns:
  - "*__pycache__*"
  - "*/tests/*"

severity:
  blocker_codes: ["F821", "E999", "SYNTAX"]
  auto_fix_codes: ["F401", "F841", "E711", "E712", "E722", "HARDCODE"]

report:
  to_wechat: true
```

---

## Architecture

```
gate.py (CLI entry)
└── qg/
    ├── scanner.py      # File discovery
    ├── engine.py       # Diagnostic engine (rule dispatching)
    ├── fixer.py        # Auto-fix engine
    ├── verifier.py     # Post-fix verification
    ├── committer.py    # Git commit automation
    ├── reporter.py     # Report generation (console + log)
    ├── auditor.py      # Agent behavior audit
    ├── dashboard.py    # Trend tracking (SQLite)
    ├── models.py       # Data models
    ├── config.py       # Configuration loader
    └── rules/          # Plugin rules (hot-pluggable)
        ├── base.py     # Rule + BatchRule base classes
        ├── syntax_check.py
        ├── ruff_blocker.py     (BatchRule)
        ├── ruff_fixable.py     (BatchRule)
        ├── bare_except.py
        ├── hardcoded_paths.py
        ├── unsafe_api.py
        ├── secret_leak.py
        └── ai_hallucination.py
```

---

## Roadmap

- [x] Phase 1: Python rewrite + plugin architecture
- [x] Phase 2: AI-specific rules + agent audit + trend dashboard
- [x] Phase 3: Open-source release + CI integration
- [ ] Phase 4: Security rules (OWASP Top 10 for AI code)
- [ ] Phase 5: GitHub Actions native action
- [ ] Phase 6: VS Code extension

---

## License

MIT License — see [LICENSE](LICENSE)

---

<p align="center">
  Built for the age of AI-generated code.
  <br>
  <sub>Because code quality doesn't matter less when AI writes it — it matters more.</sub>
</p>
