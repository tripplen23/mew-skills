#!/usr/bin/env python3
"""Backward-compatible wrapper for OpenCode installs."""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path

script = Path(__file__).with_name("install-agent-skills.py")
argv = [sys.executable, str(script), "--host", "opencode", *sys.argv[1:]]

if __name__ == "__main__":
    raise SystemExit(subprocess.call(argv))
