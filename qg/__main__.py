#!/usr/bin/env python3
"""AgentGuard CLI entry point.

Install: pip install agentguard
Usage:   gate run    gate audit    gate trend
"""

import sys
from pathlib import Path

# When installed via pip, this isn't needed. When run from source, add to path.
if not any(p.endswith("agentguard") for p in sys.path):
    pkg_dir = Path(__file__).resolve().parent.parent
    if (pkg_dir / "qg").exists():
        sys.path.insert(0, str(pkg_dir))

from qg.main import main

if __name__ == "__main__":
    main()
