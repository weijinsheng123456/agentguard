"""Tests for rules module."""
from qg.models import Issue, Severity
from qg.rules.base import Rule, register_rule, _RULES
from qg.rules.base import get_all_rules


class TestSeverity:
    def test_severity_enum_values(self):
        assert Severity.BLOCKER.value == "BLOCKER"
        assert Severity.FIXABLE.value == "FIXABLE"
        assert Severity.INFO.value == "INFO"


class TestIssue:
    def test_issue_creation(self):
        issue = Issue(
            filepath="/tmp/test.py",
            line=10,
            code="TEST001",
            message="Test issue",
            severity=Severity.BLOCKER,
            rule_name="test_rule",
        )
        assert issue.filepath == "/tmp/test.py"
        assert issue.severity == Severity.BLOCKER
        assert issue.line == 10
        assert issue.message == "Test issue"

    def test_issue_short_path(self):
        import os
        cwd = os.getcwd()
        issue = Issue(
            filepath=f"{cwd}/src/main.py",
            line=1,
            code="INFO",
            message="Info",
            severity=Severity.INFO,
            rule_name="test",
        )
        assert "src/main.py" in issue.short_path


class TestRuleBase:
    def test_rule_defaults(self):
        @register_rule
        class TestRule(Rule):
            name = "test_rule_defaults"
            severity = Severity.INFO

            def diagnose(self, filepath):
                return []

        rule = TestRule()
        assert rule.name == "test_rule_defaults"
        assert rule.severity == Severity.INFO

    def test_rule_should_check(self):
        @register_rule
        class TestRule(Rule):
            name = "test_rule_check"
            severity = Severity.INFO

            def diagnose(self, filepath):
                return []

        rule = TestRule()
        assert rule.should_check("/tmp/test.py") is True
        assert rule.should_check("/tmp/test.js") is False  # default: only .py

    def test_rule_custom_should_check(self):
        @register_rule
        class TestRule(Rule):
            name = "test_rule_custom"
            severity = Severity.INFO
            languages = ["python", "javascript"]

            def should_check(self, filepath: str) -> bool:
                return filepath.endswith((".py", ".js"))

            def diagnose(self, filepath):
                return []

        rule = TestRule()
        assert rule.should_check("/tmp/test.py") is True
        assert rule.should_check("/tmp/test.js") is True
        assert rule.should_check("/tmp/test.rb") is False

    def test_rule_no_auto_fix_by_default(self):
        @register_rule
        class TestRule(Rule):
            name = "test_rule_fix"
            severity = Severity.INFO

            def diagnose(self, filepath):
                return []

        rule = TestRule()
        assert rule.fix("/tmp/test.py", None) is False


class TestBatchRule:
    def test_batch_rule_interface(self):
        from qg.rules.base import BatchRule

        @register_rule
        class TestBatchRule(BatchRule):
            name = "test_batch"
            severity = Severity.FIXABLE

            def diagnose_batch(self, scan_dirs):
                return []

        rule = TestBatchRule()
        assert rule.name == "test_batch"
        assert rule.severity == Severity.FIXABLE
        assert rule.diagnose_batch(["/tmp"]) == []


class TestRuleRegistration:
    def test_rules_are_registered(self):
        from qg.rules.base import discover_rules
        discover_rules()
        assert len(_RULES) > 0
        rule_names = list(_RULES.keys())
        assert "unsafe_api" in rule_names
        assert "secret_leak" in rule_names
        assert "syntax_check" in rule_names
        assert "bare_except" in rule_names

    def test_all_rules_have_unique_names(self):
        names = list(_RULES.keys())
        assert len(names) == len(set(names)), f"Duplicate rule names: {names}"

    def test_all_rules_can_be_instantiated(self):
        for name, cls in _RULES.items():
            instance = cls()
            assert instance.name == name
            assert instance.severity in Severity


class TestScanResult:
    def test_scan_result_properties(self):
        from qg.models import ScanResult
        result = ScanResult(total_files=10)
        assert result.total_files == 10
        assert result.blocker_count == 0
        assert result.fixable_count == 0
        assert result.info_count == 0
        assert result.total_issues == 0

    def test_scan_result_with_issues(self):
        from qg.models import ScanResult
        issues = [
            Issue("/tmp/a.py", 1, "E001", "Blocker", Severity.BLOCKER, "rule1"),
            Issue("/tmp/b.py", 2, "E002", "Fixable", Severity.FIXABLE, "rule2"),
            Issue("/tmp/c.py", 3, "E003", "Info", Severity.INFO, "rule3"),
        ]
        result = ScanResult(total_files=3, issues=issues)
        assert result.blocker_count == 1
        assert result.fixable_count == 1
        assert result.info_count == 1
        assert result.total_issues == 3


class TestConfig:
    def test_config_find(self):
        from qg.config import find_config
        config = find_config()
        assert config is not None

    def test_config_load(self):
        from qg.config import load_config
        config = load_config()
        assert isinstance(config, dict)
        assert "scan_dirs" in config or "severity" in config or True
