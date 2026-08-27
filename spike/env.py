"""Config loading for the spike.

The agent is deny-listed from reading .env directly, which is the right posture:
the program loads its own secrets, nothing prints a value, and `report()` names
keys only.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path=None):
    p = Path(path) if path else ROOT / '.env'
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        v = v.strip().strip('"').strip("'")
        # A <placeholder> means the name is not yet confirmed; treat it as unset.
        out[k.strip()] = '' if v.startswith('<') else v
    for k, v in out.items():
        os.environ.setdefault(k, v)
    return out


def report():
    cfg = load()
    if not cfg:
        return '.env absent'
    rows = [f'  {"SET  " if v else "EMPTY"}  {k}' for k, v in cfg.items()]
    return '\n'.join(rows)


if __name__ == '__main__':
    print(report())
