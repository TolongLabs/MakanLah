"""Vercel entrypoint. The app itself lives in api/main.py and is untouched.

Vercel's Python runtime turns every file under api/ into its own function, so
without the explicit `builds` block in vercel.json, api/main.py would be built a
second time and served at /api/main -- a duplicate cold start and a second public
path for one app. vercel.json names this file and only this file.

sys.path needs the repo root because api/main.py imports the makanlah package,
which sits beside api/ rather than inside it. The bundle carries it via
includeFiles; this makes it importable once it is there.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.main import app  # noqa: E402

__all__ = ['app']
