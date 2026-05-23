"""配置加载"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import fnmatch
import yaml


QG_HOME = Path(os.environ.get("QG_HOME", Path.home() / ".hermes" / "quality-gate"))
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def load_config() -> dict[str, Any]:
    """加载 config.yaml，合并默认值"""
    config_path = QG_HOME / "config.yaml"
    defaults = {
        "scan_dirs": [
            "~/.hermes/scripts",
            "~/.hermes/skills",
            "~/.hermes/content-toolkit",
        ],
        "ignore_patterns": [
            "*__pycache__*",
            "*.egg-info*",
            "*/node_modules/*",
            "*/.git/*",
            "*/venv/*",
            "*/.venv/*",
            "*/backups/*",
            "*/study_projects/*",
            "*/wasm-preview/*",
            "*/archive/*",
        ],
        "severity": {
            "blocker_codes": ["F821", "E999", "SYNTAX"],
            "auto_fix_codes": ["F401", "F841", "E711", "E712", "E722", "HARDCODE"],
            "info_codes": ["E501", "W"],
        },
        "report": {
            "to_wechat": True,
            "max_summary_lines": 8,
        },
        "log": {
            "dir": "~/.hermes/logs",
            "file": "quality-gate.log",
            "max_size_mb": 10,
        },
    }

    if config_path.exists():
        with open(config_path) as f:
            user_config = yaml.safe_load(f) or {}
        merged = defaults.copy()
        for k, v in user_config.items():
            if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
                merged[k].update(v)
            else:
                merged[k] = v
        return merged

    return defaults


def resolve_scan_dirs(config: dict[str, Any]) -> list[Path]:
    """解析扫描目录（支持 ~ 和 $HOME 前缀）"""
    dirs = []
    for d in config.get("scan_dirs", []):
        expanded = Path(os.path.expanduser(os.path.expandvars(d))).resolve()
        if expanded.exists():
            dirs.append(expanded)
    return dirs


def ignored_path(path: Path, config: dict[str, Any]) -> bool:
    """检查路径是否被忽略（支持 glob 模式）"""
    path_str = str(path)

    for pattern in config.get("ignore_patterns", []):
        # 尝试直接 fnmatch
        if fnmatch.fnmatch(path_str, pattern):
            return True
        # 尝试 pathlib match（支持 ** 通配）
        try:
            if path.match(pattern):
                return True
        except (ValueError, IndexError):
            pass
        # 检查单个路径组件
        for part in path.parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        # 检查子串（处理 */xxx/* 跨目录匹配）
        clean_pattern = pattern.strip("*").strip("/")
        if clean_pattern and clean_pattern != pattern:
            if clean_pattern in path_str:
                return True

    return False
