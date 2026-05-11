<p align="center">
  <img src="https://raw.githubusercontent.com/hermes-labs/agentguard/main/docs/logo.png" width="120" alt="AgentGuard">
</p>

<h1 align="center">AgentGuard</h1>

<p align="center">
  <em>AI-native quality gate for agent-generated code.</em>
  <br>
  Scan · Audit · Auto-fix · Track trends
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#commands">Commands</a> •
  <a href="#rules">Rules</a> •
  <a href="#writing-custom-rules">Custom Rules</a> •
  <a href="#agent-audit">Agent Audit</a>
</p>

---

**AgentGuard** is a quality gate system purpose-built for **AI agent-generated code**. Unlike traditional linters (SonarQube, CodeQL) designed for human-written code, AgentGuard understands the patterns, pitfalls, and security risks specific to AI-generated code.

It runs as a CI-ready CLI, a pre-commit hook, or a daily cron — scanning, auto-fixing, and tracking quality trends over time.

---

## Features

### 🔍 AI-Specific Code Detection
| Rule | Severity | What It Finds |
|------|----------|---------------|
| `unsafe_api` | 🚫 BLOCKER | `eval()`, `exec()`, `os.system()`, `subprocess(shell=True)`, `pickle.loads()` |
| `secret_leak` | 🚫 BLOCKER | Hardcoded API keys, tokens, passwords in source code |
| `ai_hallucination` | ℹ️ INFO | AI placeholder comments, suspicious module names, giant auto-generated functions |

### 📊 Agent Behavior Audit
Reads agent trace data to produce a daily report:
- Tool call frequency & ranking
- Error rate & anomaly detection
- Token consumption & cost estimates
- Model usage distribution

### 📈 Trend Dashboard
Text-based trend chart (no external dependencies):
```
━━━ 📈 Quality Trend (Last 14 days) ━━━
  05/08 ████████████████   0 issues  ✅
  05/09 ████████████░░░░   3 issues  ⚠️
  05/10 ████████████████   0 issues  ✅
```
Data persists in SQLite. View anytime with `gate trend`.

### 🔧 Auto-Fix Pipeline
Automatically fixes what it can:
- Unused imports (`F401`)
- Unused variables (`F841`)
- Bare `except:` → `except Exception:`
- Hardcoded paths → `$HOME` references
- Ruff-safe auto-fixes

Fixes are backed up, verified, and git-committed automatically.

### 🧩 Plugin Rule Architecture
Rules are Python classes in `qg/rules/`. Adding a new rule = one file, one class, one decorator.

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
# Install
pip install agentguard

# Run a full scan on your project
gate run

# View agent behavior audit
gate audit

# Check quality trends
gate trend

# Install pre-commit hooks
gate install
```

### Run from source
```bash
git clone https://github.com/hermes-labs/agentguard.git
cd agentguard
python gate.py run
```

---

## Commands

| Command | Description |
|---------|-------------|
| `gate run` | Full scan + auto-fix + commit + audit |
| `gate run --quick` | Pre-commit quick check (staged files only) |
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

### Writing Custom Rules

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

## Agent Audit

AgentGuard reads from `agent_traces` (a SQLite table populated by agent tracing middleware) and reports:

```
━━━ 📊 Agent Behavior Audit ━━━
Total events: 3,960
Distribution: api_call=3,769 | tool_call=189 | error=2
Error rate: 0.33% ⚠️
Token consumption: 310M | Est. cost: ~$74.39
Top tools: read_file(74) → search_files(45) → skill_view(31)
Models: deepseek-v4-flash(3,517) | deepseek-v4-pro(252)
Anomalies: session ... read_file failed 3 times ⚠️
```

---

## Configuration

AgentGuard uses a YAML config file (default: `~/.hermes/quality-gate/config.yaml`):

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
    ├── scanner.py      # File discovery (find-based, fast)
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

- [ ] **Phase 1** ✅ Python rewrite + plugin architecture
- [ ] **Phase 2** ✅ AI-specific rules + agent audit + trend dashboard
- [ ] **Phase 3** 🔄 Open-source release + CI integration
- [ ] **Phase 4** Security rules (OWASP Top 10 for AI code)
- [ ] **Phase 5** GitHub Actions native action
- [ ] **Phase 6** VS Code extension

---

## License

MIT License — see [LICENSE](LICENSE)

---

<p align="center">
  Built for the age of AI-generated code.
  <br>
  <sub>Because code quality doesn't matter less when AI writes it — it matters more.</sub>
</p>
