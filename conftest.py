"""Root conftest.py — platform-wide pytest configuration."""
import os
import sys

# Add project root to Python path
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
