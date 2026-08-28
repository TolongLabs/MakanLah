"""Apply SQL migrations to the corpus database.

Migrations run against the DIRECT connection, never the pooled one: pgbouncer in
transaction mode does not support the session-level statements DDL issues.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg

from makanlah import config

MIGRATIONS = Path(__file__).resolve().parent / 'migrations'


def main() -> int:
    s = config.settings()
    dsn = s.database_url_direct or s.database_url
    if not dsn:
        print('no DATABASE_URL configured', file=sys.stderr)
        return 1
    files = sorted(MIGRATIONS.glob('*.sql'))
    with psycopg.connect(dsn, autocommit=True) as con:
        for f in files:
            print(f'applying {f.name} ...', end=' ', flush=True)
            con.execute(f.read_text())
            print('ok')
        tables = con.execute("""
            select table_name from information_schema.tables
            where table_schema = 'public' order by table_name
        """).fetchall()
    print('tables:', ', '.join(t[0] for t in tables))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
