"""Tests for AgentGuard rules and engine."""

from __future__ import annotations
import tempfile
import os

# Add project to path
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from qg.engine import Engine
from qg.models import Issue, Severity
from qg.rules.base import discover_rules, get_all_rules


def test_rules_load():
    """All 17 rules should load without errors."""
    discover_rules()
    rules = get_all_rules()
    assert len(rules) >= 17, f"Expected >=17 rules, got {len(rules)}"
    names = [r.name for r in rules]
    assert "unsafe_api" in names
    assert "secret_leak" in names
    assert "sql_injection" in names
    assert "path_traversal" in names
    assert "exception_quality" in names
    assert "mutable_defaults" in names
    assert "compare_with_is" in names
    assert "placeholder_check" in names
    assert "performance" in names
    assert "logging_quality" in names
    assert "hardcoded_config" in names
    assert "ai_hallucination" in names
    assert "syntax_check" in names
    assert "ruff_blocker" in names
    assert "ruff_fixable" in names
    assert "bare_except" in names
    assert "hardcoded_paths" in names


def test_unsafe_api_rule():
    """unsafe_api should detect eval/exec/os.system etc."""
    discover_rules()
    from qg.rules.unsafe_api import UnsafeApiRule
    rule = UnsafeApiRule()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("import os\nimport subprocess\nimport pickle\n\n")
        f.write('eval("1+1")\n')
        f.write('os.system("ls")\n')
        f.write('subprocess.Popen("ls", shell=True)\n')
        f.write('pickle.loads(b"xxx")\n')
        fname = f.name

    try:
        issues = rule.diagnose(fname)
        codes = {i.code for i in issues}
        assert "UNSAFE_EVAL" in codes, f"Missing UNSAFE_EVAL in {codes}"
        assert "UNSAFE_SYSTEM" in codes, f"Missing UNSAFE_SYSTEM in {codes}"
        assert "UNSAFE_POPEN" in codes, f"Missing UNSAFE_POPEN in {codes}"
        assert "UNSAFE_LOADS" in codes, f"Missing UNSAFE_LOADS in {codes}"
        assert len(issues) == 4
    finally:
        os.unlink(fname)


def test_unsafe_api_no_false_positive():
    """unsafe_api should not flag its own source code."""
    discover_rules()
    from qg.rules.unsafe_api import UnsafeApiRule
    rule = UnsafeApiRule()

    own_path = os.path.join(os.path.dirname(__file__), "../qg/rules/unsafe_api.py")
    issues = rule.diagnose(own_path)
    assert len(issues) == 0, f"False positives in own source: {len(issues)}"


def test_unsafe_api_safe_code():
    """Safe code should not trigger unsafe_api."""
    discover_rules()
    from qg.rules.unsafe_api import UnsafeApiRule
    rule = UnsafeApiRule()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("x = 1 + 1\nprint(x)\nimport json\njson.dumps({'a': 1})\n")
        fname = f.name

    try:
        issues = rule.diagnose(fname)
        assert len(issues) == 0, f"False positives in safe code: {len(issues)}"
    finally:
        os.unlink(fname)


def test_secret_leak():
    """secret_leak should detect hardcoded API keys."""
    discover_rules()
    from qg.rules.secret_leak import SecretLeakRule
    rule = SecretLeakRule()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write('API_KEY = "sk-1234567890abcdef1234567890"\n')
        f.write('SECRET = "my-super-secret-password-12345"\n')
        f.write('token = "ghp_1234567890abcdefghijklmnop"\n')
        fname = f.name

    try:
        issues = rule.diagnose(fname)
        assert len(issues) >= 1, f"Expected >=1 leaks, got {len(issues)}"
        codes = {i.code for i in issues}
        assert "LEAK_SECRET" in codes
    finally:
        os.unlink(fname)


def test_secret_leak_safe():
    """Safe code should not trigger secret_leak."""
    discover_rules()
    from qg.rules.secret_leak import SecretLeakRule
    rule = SecretLeakRule()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write('API_KEY = os.getenv("API_KEY")\n')
        f.write('secret = config["secret"]\n')
        fname = f.name

    try:
        issues = rule.diagnose(fname)
        assert len(issues) == 0, f"False positives: {len(issues)}"
    finally:
        os.unlink(fname)


def test_bare_except():
    """bare_except should detect bare except: statements."""
    discover_rules()
    from qg.rules.bare_except import BareExceptRule
    rule = BareExceptRule()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("try:\n    x = 1\nexcept:\n    pass\n")
        fname = f.name

    try:
        issues = rule.diagnose(fname)
        assert len(issues) >= 1, "Should detect bare except"
        assert issues[0].code == "E722"
    finally:
        os.unlink(fname)


def test_hardcoded_paths():
    """hardcoded_paths should detect /home/*/ paths."""
    discover_rules()
    from qg.rules.hardcoded_paths import HardcodedPathsRule
    rule = HardcodedPathsRule()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write('path = "/home/xiaobai/something/file.txt"\n')
        fname = f.name

    try:
        issues = rule.diagnose(fname)
        assert len(issues) >= 1, "Should detect hardcoded path"
        assert issues[0].code == "HARDCODE"
    finally:
        os.unlink(fname)


def test_syntax_check():
    """syntax_check should detect syntax errors."""
    discover_rules()
    from qg.rules.syntax_check import SyntaxCheckRule
    rule = SyntaxCheckRule()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("def foo():\n    print(\"hello\"\n")
        fname = f.name

    try:
        issues = rule.diagnose(fname)
        assert len(issues) >= 1, "Should detect syntax error"
        assert issues[0].code == "SYNTAX"
    finally:
        os.unlink(fname)


def test_ai_hallucination():
    """ai_hallucination should detect AI placeholder comments."""
    discover_rules()
    from qg.rules.ai_hallucination import AiHallucinationRule
    rule = AiHallucinationRule()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("# TODO: implement the rest of this function\n")
        f.write("# Add your code here\n")
        f.write('print("hello")\n')
        fname = f.name

    try:
        issues = rule.diagnose(fname)
        assert len(issues) >= 2, f"Expected >=2 AI markers, got {len(issues)}"
    finally:
        os.unlink(fname)


def test_issue_model():
    """Issue dataclass should work correctly."""
    issue = Issue(
        filepath="/test/file.py",
        line=42,
        code="TEST001",
        message="Test issue",
        severity=Severity.BLOCKER,
        rule_name="test_rule",
        fixable=False,
    )
    assert issue.filepath == "/test/file.py"
    assert issue.line == 42
    assert issue.code == "TEST001"
    assert issue.severity == Severity.BLOCKER
    assert not issue.fixable


def test_engine_initialization():
    """Engine should load all rules without errors."""
    engine = Engine()
    assert len(engine.file_rules) >= 3  # file-level rules
    assert len(engine.batch_rules) >= 2  # batch-level rules (ruff)
    total = len(engine.file_rules) + len(engine.batch_rules)
    assert total >= 8


def test_engine_diagnose_single_file():
    """Engine should diagnose a single file."""
    engine = Engine()

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write("x = 1\nprint(x)\n")
        fname = f.name

    try:
        issues = engine.diagnose_file(fname)
        # Should not crash, may find nothing or minor issues
        assert isinstance(issues, list)
    finally:
        os.unlink(fname)
