"""配置加载 — 通用版本（不依赖 Hermes 环境）"""

from __future__ import annotations
import os
from pathlib import Path
from typing import Any
import fnmatch
import yaml


def _get_config_home() -> Path:
    """获取配置目录。优先 XDG 规范，兼容 ~/.hermes。"""
    # 环境变量覆盖
    if env := os.environ.get("QG_HOME"):
        return Path(env)
    # XDG 规范
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "agentguard"
    # 兼容 Hermes 环境
    hermes = Path.home() / ".hermes" / "quality-gate"
    if hermes.exists():
        return hermes
    # 默认
    return Path.home() / ".config" / "agentguard"


def _get_log_home() -> Path:
    """获取日志目录。"""
    if env := os.environ.get("QG_LOG_DIR"):
        return Path(env)
    return _get_config_home() / "logs"


QG_HOME = _get_config_home()
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def find_config() -> Path:
    """查找配置文件。优先级：环境变量 > 项目目录 > 用户配置目录"""
    # 1. QG_CONFIG 环境变量
    if env := os.environ.get("QG_CONFIG"):
        p = Path(env)
        if p.exists():
            return p

    # 2. 当前目录的 agentguard.yaml 或 agentguard.yml
    for name in ("agentguard.yaml", "agentguard.yml", "config.yaml"):
        p = Path.cwd() / name
        if p.exists():
            return p

    # 3. 当前目录的 qg-config.yaml
    p = Path.cwd() / "qg-config.yaml"
    if p.exists():
        return p

    # 4. 用户配置目录
    p = QG_HOME / "config.yaml"
    if p.exists():
        return p

    # 5. 兼容 Hermes 配置
    p = HERMES_HOME / "quality-gate" / "config.yaml"
    if p.exists():
        return p

    return QG_HOME / "config.yaml"


def load_config() -> dict[str, Any]:
    """加载配置，合并默认值"""
    config_path = find_config()

    # 新用户友好的默认值
    defaults = {
        "scan_dirs": [
            ".",  # 默认扫当前目录
        ],
        "ignore_patterns": [
            "*__pycache__*",
            "*.egg-info*",
            "*/node_modules/*",
            "*/.git/*",
            "*/venv/*",
            "*/.venv/*",
            "*/backups/*",
        ],
        "severity": {
            "blocker_codes": ["F821", "E999", "SYNTAX"],
            "auto_fix_codes": ["F401", "F841", "E711", "E712", "E722", "HARDCODE"],
            "info_codes": ["E501", "W"],
        },
        "report": {
            "max_summary_lines": 8,
        },
        "log": {
            "file": "quality-gate.log",
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
    for d in config.get("scan_dirs", ["."]):
        expanded = Path(os.path.expanduser(os.path.expandvars(d))).resolve()
        if expanded.exists():
            dirs.append(expanded)
    return dirs


def get_log_path(config: dict[str, Any]) -> Path:
    """获取日志文件路径"""
    log_dir = _get_log_home()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = config.get("log", {}).get("file", "quality-gate.log")
    return log_dir / log_file


def ignored_path(path: Path, config: dict[str, Any]) -> bool:
    """检查路径是否被忽略（支持 glob 模式）"""
    path_str = str(path)

    for pattern in config.get("ignore_patterns", []):
        if fnmatch.fnmatch(path_str, pattern):
            return True
        try:
            if path.match(pattern):
                return True
        except (ValueError, IndexError):
            pass
        for part in path.parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        clean_pattern = pattern.strip("*").strip("/")
        if clean_pattern and clean_pattern != pattern:
            if clean_pattern in path_str:
                return True

    return False
