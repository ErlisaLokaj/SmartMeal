"""
Pytest configuration and shared fixtures.
This file ensures the project root is in sys.path for imports.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
