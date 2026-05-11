#!/usr/bin/env python3
"""AgentGuard — AI-native quality gate for agent-generated code.

Usage:
    gate run                  Full scan + fix + commit + audit
    gate run --quick         Pre-commit quick check
    gate run --fixme         Fix staged files
    gate audit               Run agent behavior audit
    gate trend [days]        Show quality trend dashboard
    gate install             Install hooks & cron
    gate version             Show version
"""

import sys
from pathlib import Path

# Allow running from source without pip install
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qg.main import main

if __name__ == "__main__":
    main()
