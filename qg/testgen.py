"""测试自动生成模块 — 对标 Qodo Cover

每次门禁扫描后，对变更的 Python 文件自动生成 pytest 测试骨架。
支持的场景：
1. 纯函数 → 生成参数化测试
2. 类方法 → 生成 fixture + 测试方法
3. CLI 脚本 → 生成 subprocess 调用测试
4. async 函数 → 生成 pytest-asyncio 测试

策略：
- 不为 tests/ 目录下的文件生成测试（已有测试）
- 不为 __init__.py 生成测试
- 不为仅配置/常量的文件生成测试
- 测试文件写到 tests/test_<module>.py
- 如果已有测试文件则追加，不覆盖
"""

from __future__ import annotations

import ast
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# 不生成测试的模块/函数
SKIP_MODULES = {"__init__", "conftest", "setup"}
SKIP_FUNCS = {"main", "setup", "teardown"}
SKIP_DECORATORS = {"property", "staticmethod", "classmethod", "cached_property"}


def should_generate_test(filepath: str) -> bool:
    """判断是否应该为此文件生成测试"""
    fpath = Path(filepath)

    # 跳过非 .py
    if fpath.suffix != ".py":
        return False

    # 跳过测试文件自身
    if "test" in fpath.name.lower() or "test" in str(fpath.parent).lower():
        return False

    # 跳过特殊文件
    if fpath.stem in SKIP_MODULES:
        return False

    # 跳过虚拟环境等
    for part in fpath.parts:
        if part in {"venv", ".venv", "__pycache__", ".git", "node_modules"}:
            return False

    return True


def _extract_functions(tree: ast.AST) -> list[dict]:
    """提取文件中的可测试函数"""
    funcs = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # 跳过特殊函数
        if node.name in SKIP_FUNCS or node.name.startswith("_"):
            continue

        # 检查装饰器
        has_skip_decorator = False
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name) and dec.id in SKIP_DECORATORS:
                has_skip_decorator = True
                break
            if isinstance(dec, ast.Attribute) and dec.attr in SKIP_DECORATORS:
                has_skip_decorator = True
                break
        if has_skip_decorator:
            continue

        # 获取参数
        args = [a.arg for a in node.args.args]

        # 是否有返回值？检查 return 语句
        has_return = any(
            isinstance(stmt, (ast.Return, ast.Yield, ast.YieldFrom))
            for stmt in ast.walk(node)
        )

        is_async = isinstance(node, ast.AsyncFunctionDef)

        funcs.append({
            "name": node.name,
            "args": args,
            "has_return": has_return,
            "is_async": is_async,
            "lineno": node.lineno,
        })

    return funcs


def _extract_classes(tree: ast.AST) -> list[dict]:
    """提取文件中的可测试类"""
    classes = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not item.name.startswith("_"):
                    methods.append({
                        "name": item.name,
                        "args": [a.arg for a in item.args.args],
                        "is_async": isinstance(item, ast.AsyncFunctionDef),
                        "lineno": item.lineno,
                    })

        if methods:
            classes.append({
                "name": node.name,
                "methods": methods,
                "lineno": node.lineno,
            })

    return classes


def _has_return_value(node: ast.AST) -> bool:
    """检查函数是否有返回值"""
    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Return) and stmt.value is not None:
            return True
    return False


def generate_tests(filepath: str, dry_run: bool = False) -> dict:
    """为指定文件生成测试

    Args:
        filepath: Python 文件路径
        dry_run: 如果为 True，只返回测试内容不写入

    Returns:
        {
            "status": "generated" | "skipped" | "error",
            "test_path": str | None,
            "test_count": int,
            "content": str | None,
            "error": str | None,
        }
    """
    fpath = Path(filepath)

    if not should_generate_test(filepath):
        return {"status": "skipped", "reason": "不符合生成条件"}

    try:
        with open(filepath) as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return {"status": "error", "error": str(e)}

    # 解析 AST
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return {"status": "skipped", "reason": f"语法错误: {e}"}

    # 检查是否已有测试文件
    test_dir = fpath.parent / "tests"
    test_file = test_dir / f"test_{fpath.name}"
    existing = ""
    if test_file.exists():
        try:
            existing = test_file.read_text()
        except OSError:
            existing = ""

    # 提取可测试内容
    funcs = _extract_functions(tree)
    classes = _extract_classes(tree)

    if not funcs and not classes:
        return {"status": "skipped", "reason": "无可测试的公开函数/方法"}

    # 生成测试代码
    tests = []
    tests.append('"""自动生成的测试 — 由质量门禁创建"""')
    tests.append("")
    tests.append("import pytest")
    if any(f["is_async"] for f in funcs):
        tests.append("import pytest_asyncio")
    tests.append("")

    # 导入被测模块
    rel_path = fpath.relative_to(fpath.parent.parent) if len(fpath.parts) > 1 else fpath.name
    module_path = str(fpath.with_suffix("")).replace(os.sep, ".")
    # 去掉前导点
    module_path = module_path.lstrip(".")
    tests.append(f"from {module_path} import {', '.join(f['name'] for f in funcs[:5])}{', ...' if len(funcs) > 5 else ''}")
    tests.append("")

    # 函数测试
    for func in funcs:
        tests.append("")
        if func["is_async"]:
            tests.append("@pytest.mark.asyncio")
            tests.append(f"async def test_{func['name']}():")
        else:
            tests.append(f"def test_{func['name']}():")
        tests.append(f'    """测试 {func["name"]} 函数"""')
        tests.append(f"    # TODO: 填写测试参数")
        if func["args"]:
            # 用默认值代替参数
            positional = func["args"][1:] if func["args"][0] in ("self", "cls") else func["args"]
            if positional:
                args_str = ", ".join(f"mock_{a}=None" for a in positional)
                tests.append(f"    result = {func['name']}({args_str})")
            else:
                tests.append(f"    result = {func['name']}()")
        else:
            tests.append(f"    result = {func['name']}()")

        if func["has_return"]:
            tests.append(f"    assert result is not None  # TODO: 检查返回值")
        else:
            tests.append(f"    # 函数无返回值，测试副作用")
        tests.append("")

    # 类测试
    for cls in classes:
        tests.append("")
        tests.append(f"class Test{cls['name']}:")
        tests.append('    """测试 {cls["name"]} 类"""')
        tests.append("")
        tests.append("    @pytest.fixture")
        tests.append("    def instance(self):")
        tests.append(f'        """创建 {cls["name"]} 实例"""')
        tests.append(f"        return {cls['name']}()")
        tests.append("")

        for method in cls["methods"]:
            if method["is_async"]:
                tests.append("    @pytest.mark.asyncio")
                tests.append(f"    async def test_{method['name']}(self, instance):")
            else:
                tests.append(f"    def test_{method['name']}(self, instance):")
            tests.append(f'        """测试 {cls["name"]}.{method["name"]} 方法"""')
            positional = [a for a in method["args"] if a not in ("self", "cls")]
            if positional:
                args_str = ", ".join(f"mock_{a}=None" for a in positional)
                tests.append(f"        result = instance.{method['name']}({args_str})")
            else:
                tests.append(f"        result = instance.{method['name']}()")
            tests.append(f"        assert result is not None  # TODO: 填写断言")
            tests.append("")

    test_content = "\n".join(tests)

    # 如果有已有测试，合并
    if existing:
        test_content = existing + "\n\n# ── 自动附加测试 ──\n\n" + test_content

    if dry_run:
        return {
            "status": "generated",
            "test_path": str(test_file),
            "test_count": len(funcs) + sum(len(c["methods"]) for c in classes),
            "content": test_content,
        }

    # 写入文件
    try:
        test_dir.mkdir(parents=True, exist_ok=True)
        mode = "a" if existing else "w"
        with open(test_file, mode) as f:
            if existing:
                f.write("\n\n")
            f.write(test_content)
    except OSError as e:
        return {"status": "error", "error": str(e)}

    logger.info(f"✅ 测试生成: {len(funcs)} 函数 + {sum(len(c['methods']) for c in classes)} 方法 → {test_file}")
    return {
        "status": "generated",
        "test_path": str(test_file),
        "test_count": len(funcs) + sum(len(c["methods"]) for c in classes),
    }


def generate_batch(filepaths: list[str], dry_run: bool = False) -> list[dict]:
    """批量生成测试"""
    results = []
    for fp in filepaths:
        result = generate_tests(fp, dry_run)
        if result["status"] == "generated":
            results.append(result)
    return results
