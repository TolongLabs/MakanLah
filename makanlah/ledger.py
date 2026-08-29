"""Out-of-process ledger for request-bound counters.

A daily spend ceiling, a per-IP share, rate-limit buckets and a companion
free-tier quota all live in a durable store. A memory backend is provided for
workstations and CI. The in-memory dictionaries passed to every method are
always the current cache, so api/main.py can keep its existing module-level
counters and monkeypatched tests continue to work.
"""

import json
import os
import sqlite3
import time
from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

from makanlah import config, db


def ledger_backend() -> str:
    if os.environ.get('DATABASE_URL'):
        return 'postgres'
    if os.environ.get('LEDGER_PATH'):
        return 'sqlite'
    return 'memory'


def _budget_day() -> int:
    return int(time.time() // 86400)


class Ledger(ABC):
    @abstractmethod
    def spend_left(self, budget: float, _spend: dict, _ip_spend: dict) -> float: ...

    @abstractmethod
    def ip_left(self, ip: str, budget: float, share: float, _spend: dict, _ip_spend: dict) -> float: ...

    @abstractmethod
    def charge(self, ip: str, cost: float, _spend: dict, _ip_spend: dict) -> None: ...

    @abstractmethod
    def rate_limit(self, bucket: str, ip: str, limit: int, window: int, _attempts: dict) -> None: ...

    @abstractmethod
    def companion_quota(self, daily: int, per_min: int, _companion: dict, _companion_minute: list) -> bool: ...


class MemoryLedger(Ledger):
    def spend_left(self, budget: float, _spend: dict, _ip_spend: dict) -> float:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        return budget - _spend['myr']

    def ip_left(self, ip: str, budget: float, share: float, _spend: dict, _ip_spend: dict) -> float:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        return (budget * share) - _ip_spend.get(ip, 0.0)

    def charge(self, ip: str, cost: float, _spend: dict, _ip_spend: dict) -> None:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        _spend['myr'] += cost
        _ip_spend[ip] = _ip_spend.get(ip, 0.0) + cost

    def rate_limit(self, bucket: str, ip: str, limit: int, window: int, _attempts: dict) -> None:
        now = time.time()
        key = (bucket, ip)
        hits = [t for t in _attempts.get(key, []) if now - t < window]
        if len(hits) >= limit:
            raise HTTPException(status_code=429, detail='Too many attempts, try again shortly.')
        hits.append(now)
        _attempts[key] = hits

    def companion_quota(self, daily: int, per_min: int, _companion: dict, _companion_minute: list) -> bool:
        day = _budget_day()
        if _companion['day'] != day:
            _companion['day'], _companion['used'] = float(day), 0.0
            _companion_minute.clear()
        now = time.time()
        _companion_minute[:] = [t for t in _companion_minute if now - t < 60]
        if _companion['used'] >= daily or len(_companion_minute) >= per_min:
            return False
        _companion['used'] += 1
        _companion_minute.append(now)
        return True


class SqliteLedger(Ledger):
    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS ledger_spend (
        day INTEGER PRIMARY KEY,
        myr REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS ledger_ip_spend (
        day INTEGER NOT NULL,
        ip TEXT NOT NULL,
        myr REAL NOT NULL DEFAULT 0,
        PRIMARY KEY (day, ip)
    );
    CREATE TABLE IF NOT EXISTS ledger_rate_limit (
        bucket TEXT NOT NULL,
        ip TEXT NOT NULL,
        hits TEXT NOT NULL DEFAULT '[]',
        PRIMARY KEY (bucket, ip)
    );
    CREATE TABLE IF NOT EXISTS ledger_companion_day (
        day INTEGER PRIMARY KEY,
        used REAL NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS ledger_companion_minute (
        ts REAL PRIMARY KEY
    );
    """

    def __init__(self, path: str) -> None:
        self.path = path
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise sqlite3.OperationalError(str(e)) from e
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        con = sqlite3.connect(self.path, timeout=5.0)
        try:
            con.executescript(self._SCHEMA)
            con.commit()
        finally:
            con.close()

    @contextmanager
    def _transact(self):
        con = sqlite3.connect(self.path, isolation_level=None, timeout=5.0)
        con.row_factory = sqlite3.Row
        try:
            con.execute('BEGIN IMMEDIATE')
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def spend_left(self, budget: float, _spend: dict, _ip_spend: dict) -> float:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        with self._transact() as con:
            row = con.execute('SELECT myr FROM ledger_spend WHERE day = ?', (day,)).fetchone()
        _spend['myr'] = max(_spend['myr'], row['myr'] if row else 0.0)
        return budget - _spend['myr']

    def ip_left(self, ip: str, budget: float, share: float, _spend: dict, _ip_spend: dict) -> float:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        with self._transact() as con:
            row = con.execute('SELECT myr FROM ledger_ip_spend WHERE day = ? AND ip = ?', (day, ip)).fetchone()
        _ip_spend[ip] = max(_ip_spend.get(ip, 0.0), row['myr'] if row else 0.0)
        return (budget * share) - _ip_spend[ip]

    def charge(self, ip: str, cost: float, _spend: dict, _ip_spend: dict) -> None:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        with self._transact() as con:
            # Rehydrate from the ledger before writing, then make the cached
            # value authoritative with an atomic add.
            row = con.execute('SELECT myr FROM ledger_spend WHERE day = ?', (day,)).fetchone()
            _spend['myr'] = max(_spend['myr'], row['myr'] if row else 0.0)
            row = con.execute('SELECT myr FROM ledger_ip_spend WHERE day = ? AND ip = ?', (day, ip)).fetchone()
            _ip_spend[ip] = max(_ip_spend.get(ip, 0.0), row['myr'] if row else 0.0)
            row = con.execute(
                """INSERT INTO ledger_spend (day, myr) VALUES (?, ?)
                   ON CONFLICT (day) DO UPDATE
                   SET myr = max(ledger_spend.myr + ?, excluded.myr)
                   RETURNING myr""",
                (day, _spend['myr'] + cost, cost),
            ).fetchone()
            _spend['myr'] = row['myr']
            row = con.execute(
                """INSERT INTO ledger_ip_spend (day, ip, myr) VALUES (?, ?, ?)
                   ON CONFLICT (day, ip) DO UPDATE
                   SET myr = max(ledger_ip_spend.myr + ?, excluded.myr)
                   RETURNING myr""",
                (day, ip, _ip_spend[ip] + cost, cost),
            ).fetchone()
            _ip_spend[ip] = row['myr']
            con.execute('DELETE FROM ledger_spend WHERE day < ?', (day,))
            con.execute('DELETE FROM ledger_ip_spend WHERE day < ?', (day,))

    def rate_limit(self, bucket: str, ip: str, limit: int, window: int, _attempts: dict) -> None:
        now = time.time()
        cutoff = now - window
        key = (bucket, ip)
        _attempts[key] = [t for t in _attempts.get(key, []) if t > cutoff]
        with self._transact() as con:
            con.execute('INSERT OR IGNORE INTO ledger_rate_limit (bucket, ip) VALUES (?, ?)', (bucket, ip))
            row = con.execute('SELECT hits FROM ledger_rate_limit WHERE bucket = ? AND ip = ?', (bucket, ip)).fetchone()
            ledger_hits = json.loads(row['hits']) if row and row['hits'] else []
            hits = list(set(_attempts.get(key, []) + ledger_hits))
            hits = [t for t in hits if t > cutoff]
            if len(hits) >= limit:
                _attempts[key] = hits
                raise HTTPException(status_code=429, detail='Too many attempts, try again shortly.')
            hits.append(now)
            con.execute(
                'UPDATE ledger_rate_limit SET hits = ? WHERE bucket = ? AND ip = ?',
                (json.dumps(hits), bucket, ip),
            )
            _attempts[key] = hits

    def companion_quota(self, daily: int, per_min: int, _companion: dict, _companion_minute: list) -> bool:
        day = _budget_day()
        now = time.time()
        cutoff = now - 60
        if _companion['day'] != day:
            _companion['day'], _companion['used'] = float(day), 0.0
            _companion_minute.clear()
        _companion_minute[:] = [t for t in _companion_minute if t > cutoff]
        with self._transact() as con:
            row = con.execute(
                """INSERT INTO ledger_companion_day (day, used) VALUES (?, ?)
                   ON CONFLICT (day) DO UPDATE
                   SET used = max(ledger_companion_day.used, excluded.used)
                   RETURNING used""",
                (day, _companion['used']),
            ).fetchone()
            _companion['used'] = row['used']
            con.execute('DELETE FROM ledger_companion_minute WHERE ts <= ?', (cutoff,))
            rows = con.execute('SELECT ts FROM ledger_companion_minute WHERE ts > ? ORDER BY ts', (cutoff,)).fetchall()
            ledger_minute = [r['ts'] for r in rows]
            _companion_minute[:] = sorted(set(_companion_minute + ledger_minute))
            if _companion['used'] >= daily or len(_companion_minute) >= per_min:
                con.execute('DELETE FROM ledger_companion_day WHERE day < ?', (day,))
                return False
            con.execute('INSERT INTO ledger_companion_minute (ts) VALUES (?)', (now,))
            row = con.execute(
                """INSERT INTO ledger_companion_day (day, used) VALUES (?, ?)
                   ON CONFLICT (day) DO UPDATE
                   SET used = max(ledger_companion_day.used, excluded.used) + 1
                   RETURNING used""",
                (day, _companion['used']),
            ).fetchone()
            _companion['used'] = row['used']
            _companion_minute.append(now)
            con.execute('DELETE FROM ledger_companion_day WHERE day < ?', (day,))
            return True


class PostgresLedger(Ledger):
    _SCHEMA = (
        """CREATE TABLE IF NOT EXISTS ledger_spend (
            day INTEGER PRIMARY KEY,
            myr REAL NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS ledger_ip_spend (
            day INTEGER NOT NULL,
            ip TEXT NOT NULL,
            myr REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (day, ip)
        )""",
        """CREATE TABLE IF NOT EXISTS ledger_rate_limit (
            bucket TEXT NOT NULL,
            ip TEXT NOT NULL,
            hits TEXT NOT NULL DEFAULT '[]',
            PRIMARY KEY (bucket, ip)
        )""",
        """CREATE TABLE IF NOT EXISTS ledger_companion_day (
            day INTEGER PRIMARY KEY,
            used REAL NOT NULL DEFAULT 0
        )""",
        """CREATE TABLE IF NOT EXISTS ledger_companion_minute (
            ts REAL PRIMARY KEY
        )""",
    )

    def __init__(self) -> None:
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with db.connect(direct=True) as con:
            exists = con.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'ledger_spend'"
            ).fetchone()
            if exists:
                return
            for stmt in self._SCHEMA:
                con.execute(stmt)

    def spend_left(self, budget: float, _spend: dict, _ip_spend: dict) -> float:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        with db.connect() as con:
            row = con.execute('SELECT myr FROM ledger_spend WHERE day = %s', (day,)).fetchone()
        _spend['myr'] = max(_spend['myr'], row['myr'] if row else 0.0)
        return budget - _spend['myr']

    def ip_left(self, ip: str, budget: float, share: float, _spend: dict, _ip_spend: dict) -> float:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        with db.connect() as con:
            row = con.execute('SELECT myr FROM ledger_ip_spend WHERE day = %s AND ip = %s', (day, ip)).fetchone()
        _ip_spend[ip] = max(_ip_spend.get(ip, 0.0), row['myr'] if row else 0.0)
        return (budget * share) - _ip_spend[ip]

    def charge(self, ip: str, cost: float, _spend: dict, _ip_spend: dict) -> None:
        day = _budget_day()
        if _spend['day'] != day:
            _spend['day'], _spend['myr'] = float(day), 0.0
            _ip_spend.clear()
        with db.connect() as con:
            row = con.execute('SELECT myr FROM ledger_spend WHERE day = %s', (day,)).fetchone()
            _spend['myr'] = max(_spend['myr'], row['myr'] if row else 0.0)
            row = con.execute('SELECT myr FROM ledger_ip_spend WHERE day = %s AND ip = %s', (day, ip)).fetchone()
            _ip_spend[ip] = max(_ip_spend.get(ip, 0.0), row['myr'] if row else 0.0)
            row = con.execute(
                """INSERT INTO ledger_spend (day, myr) VALUES (%s, %s)
                   ON CONFLICT (day) DO UPDATE
                   SET myr = GREATEST(ledger_spend.myr + %s, excluded.myr)
                   RETURNING myr""",
                (day, _spend['myr'] + cost, cost),
            ).fetchone()
            _spend['myr'] = row['myr']
            row = con.execute(
                """INSERT INTO ledger_ip_spend (day, ip, myr) VALUES (%s, %s, %s)
                   ON CONFLICT (day, ip) DO UPDATE
                   SET myr = GREATEST(ledger_ip_spend.myr + %s, excluded.myr)
                   RETURNING myr""",
                (day, ip, _ip_spend[ip] + cost, cost),
            ).fetchone()
            _ip_spend[ip] = row['myr']
            con.execute('DELETE FROM ledger_spend WHERE day < %s', (day,))
            con.execute('DELETE FROM ledger_ip_spend WHERE day < %s', (day,))

    def rate_limit(self, bucket: str, ip: str, limit: int, window: int, _attempts: dict) -> None:
        now = time.time()
        cutoff = now - window
        key = (bucket, ip)
        _attempts[key] = [t for t in _attempts.get(key, []) if t > cutoff]
        with db.connect() as con:
            con.execute(
                """INSERT INTO ledger_rate_limit (bucket, ip) VALUES (%s, %s)
                   ON CONFLICT (bucket, ip) DO NOTHING""",
                (bucket, ip),
            )
            row = con.execute(
                'SELECT hits FROM ledger_rate_limit WHERE bucket = %s AND ip = %s FOR UPDATE',
                (bucket, ip),
            ).fetchone()
            ledger_hits = json.loads(row['hits']) if row and row['hits'] else []
            hits = list(set(_attempts.get(key, []) + ledger_hits))
            hits = [t for t in hits if t > cutoff]
            if len(hits) >= limit:
                _attempts[key] = hits
                raise HTTPException(status_code=429, detail='Too many attempts, try again shortly.')
            hits.append(now)
            con.execute(
                'UPDATE ledger_rate_limit SET hits = %s WHERE bucket = %s AND ip = %s',
                (json.dumps(hits), bucket, ip),
            )
            _attempts[key] = hits

    def companion_quota(self, daily: int, per_min: int, _companion: dict, _companion_minute: list) -> bool:
        day = _budget_day()
        now = time.time()
        cutoff = now - 60
        if _companion['day'] != day:
            _companion['day'], _companion['used'] = float(day), 0.0
            _companion_minute.clear()
        _companion_minute[:] = [t for t in _companion_minute if t > cutoff]
        with db.connect() as con:
            row = con.execute(
                """INSERT INTO ledger_companion_day (day, used) VALUES (%s, %s)
                   ON CONFLICT (day) DO UPDATE
                   SET used = GREATEST(ledger_companion_day.used, excluded.used)
                   RETURNING used""",
                (day, _companion['used']),
            ).fetchone()
            _companion['used'] = row['used']
            con.execute('DELETE FROM ledger_companion_minute WHERE ts <= %s', (cutoff,))
            rows = con.execute('SELECT ts FROM ledger_companion_minute WHERE ts > %s ORDER BY ts', (cutoff,)).fetchall()
            ledger_minute = [r['ts'] for r in rows]
            _companion_minute[:] = sorted(set(_companion_minute + ledger_minute))
            if _companion['used'] >= daily or len(_companion_minute) >= per_min:
                con.execute('DELETE FROM ledger_companion_day WHERE day < %s', (day,))
                return False
            con.execute('INSERT INTO ledger_companion_minute (ts) VALUES (%s)', (now,))
            row = con.execute(
                """INSERT INTO ledger_companion_day (day, used) VALUES (%s, %s)
                   ON CONFLICT (day) DO UPDATE
                   SET used = GREATEST(ledger_companion_day.used, excluded.used) + 1
                   RETURNING used""",
                (day, _companion['used']),
            ).fetchone()
            _companion['used'] = row['used']
            _companion_minute.append(now)
            con.execute('DELETE FROM ledger_companion_day WHERE day < %s', (day,))
            return True


_LEDGER_INSTANCES: dict[tuple[str, str | None], Ledger] = {}


def get_ledger() -> Ledger:
    backend = ledger_backend()
    if backend == 'memory':
        key = ('memory', None)
    elif backend == 'sqlite':
        key = ('sqlite', os.environ.get('LEDGER_PATH'))
    else:
        key = ('postgres', config.settings().database_url)
    if key not in _LEDGER_INSTANCES:
        if backend == 'sqlite':
            _LEDGER_INSTANCES[key] = SqliteLedger(key[1])
        elif backend == 'postgres':
            _LEDGER_INSTANCES[key] = PostgresLedger()
        else:
            _LEDGER_INSTANCES[key] = MemoryLedger()
    return _LEDGER_INSTANCES[key]
