"""Make the project root importable no matter how pytest is invoked.

Running bare `pytest` (instead of `python -m pytest`) does not add the current
directory to sys.path, so test modules can't `import security` / `from app ...`.
A conftest.py at the repo root fixes that for every invocation and CWD.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
