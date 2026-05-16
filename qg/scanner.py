"""文件发现 + 增量检测模块。

职责：扫描目录 → 对比 manifest → 输出新增/修改/稳定三类文件

性能优化：
- 使用 `find` 命令（比 Python rglob 快 5-10 倍）
- 批量扫描多个目录
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Optional

from .config import QG_HOME, HERMES_HOME, ignored_path, load_config, resolve_scan_dirs

# 优先使用 QG_HOME（独立部署），兼容 HERMES_HOME（Hermes 环境）
MANIFEST_DIR = QG_HOME if QG_HOME.exists() else HERMES_HOME
MANIFEST_FILE = MANIFEST_DIR / "data" / "file-manifest.json"


def compute_file_hash(filepath: Path) -> str:
    """计算文件 MD5 哈希"""
    try:
        return hashlib.md5(filepath.read_bytes()).hexdigest()
    except (OSError, PermissionError):
        return ""


def _find_py_files(directory: Path) -> list[str]:
    """使用 find 命令快速查找 .py 文件（比 rglob 快 5-10 倍）"""
    try:
        result = subprocess.run(
            ["find", str(directory),
             "-name", "*.py",
             "-not", "-path", "*/__pycache__/*",
             "-not", "-path", "*.egg-info*",
             "-not", "-path", "*/node_modules/*",
             "-not", "-path", "*/.git/*",
             "-not", "-path", "*/venv/*",
             "-not", "-path", "*/.venv/*",
             "-not", "-path", "*/backups/*",
             "-not", "-path", "*/study_projects/*",
             "-not", "-path", "*/wasm-preview/*",
             "-type", "f"],
            capture_output=True, text=True, timeout=30,
        )
        return [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # fallback: Python rglob
        return [str(f) for f in sorted(directory.rglob("*.py"))
                if f.is_file() and not any(
                    p.startswith(".") for p in f.relative_to(directory).parts
                    if p in ("__pycache__", ".git", "node_modules", "venv", ".venv")
                )]


def scan_all(config: Optional[dict] = None) -> dict:
    """扫描所有配置的目录，返回三类文件列表。

    Returns:
        dict with keys: all_files, new_files, changed_files, stable_files, scan_dirs
    """
    if config is None:
        config = load_config()

    scan_dirs = resolve_scan_dirs(config)
    all_files: list[str] = []

    for d in scan_dirs:
        if not d.exists():
            continue
        files = _find_py_files(d)
        for f in files:
            fp = Path(f).resolve()
            if not ignored_path(fp, config) and fp.exists():
                all_files.append(str(fp))

    # 去重
    all_files = list(dict.fromkeys(all_files))

    # 加载 manifest
    manifest: dict[str, str] = {}
    if MANIFEST_FILE.exists():
        try:
            manifest = json.loads(MANIFEST_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    # 分类
    new_files: list[str] = []
    changed_files: list[str] = []
    stable_files: list[str] = []

    for f in all_files:
        cur_hash = compute_file_hash(Path(f))
        old_hash = manifest.get(f, "")
        if not old_hash:
            new_files.append(f)
        elif cur_hash != old_hash:
            changed_files.append(f)
        else:
            stable_files.append(f)

    return {
        "all_files": all_files,
        "new_files": new_files,
        "changed_files": changed_files,
        "stable_files": stable_files,
        "scan_dirs": [str(d) for d in scan_dirs],
    }


def update_manifest(all_files: list[str]):
    """更新文件清单 manifest"""
    HERMES_HOME.joinpath("data").mkdir(parents=True, exist_ok=True)
    manifest = {}
    for f in all_files:
        manifest[f] = compute_file_hash(Path(f))
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
