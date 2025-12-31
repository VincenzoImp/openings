"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

# Ensure scripts directory is in path for all tests
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
