import os
import sys

# Add project root to sys.path so backend modules are imported cleanly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Vercel serverless environment has a read-only filesystem outside /tmp
if "VERCEL" in os.environ and not os.environ.get("SOVEREIGN_DB"):
    os.environ["SOVEREIGN_DB"] = "/tmp/sovereign.db"

from backend.app import app
