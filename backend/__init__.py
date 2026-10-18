"""
Public Anomaly Detection Backend Package
Ensures backend directory is in sys.path when imported as a package.
"""
import sys
from pathlib import Path

backend_dir = str(Path(__file__).resolve().parent)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
