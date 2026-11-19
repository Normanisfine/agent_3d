"""Durable reservations, audit events and conservative unknown-charge accounting."""
import json
import math
import sqlite3
import time
import uuid
from pathlib import Path


class BudgetExceeded(RuntimeError):
    pass


class Ledger:
    def __init__(self, path: Path, budget: float):
        self.path, self.budget = path, budget
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS charges (
                    id TEXT PRIMARY KEY, label TEXT, reserved REAL, actual REAL,
                    state TEXT, detail TEXT);
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY, time REAL, kind TEXT, detail TEXT);
            """)
            if 'budget_exempt' not in {row[1] for row in db.execute('PRAGMA table_info(charges)')}:
                db.execute('ALTER TABLE charges ADD COLUMN budget_exempt INTEGER NOT NULL DEFAULT 0')
            if 'category' not in {row[1] for row in db.execute('PRAGMA table_info(charges)')}:
                db.execute("ALTER TABLE charges ADD COLUMN category TEXT NOT NULL DEFAULT 'unclassified'")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def reserve(self, label: str, amount: float, holdback: float = 0, *, budget_exempt: bool = False,
                category: str = 'unclassified') -> str:
        """Atomically claim capacity while keeping holdback available for the judge."""
        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("A finite positive reservation is required")
        key = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            spent = db.execute("SELECT COALESCE(SUM(COALESCE(actual,reserved)),0) FROM charges WHERE budget_exempt=0").fetchone()[0]
            if not budget_exempt and spent + amount + holdback > self.budget + 1e-9:
                raise BudgetExceeded(f"Budget exhausted for {label}; spent/reserved={spent:.4f}")
            db.execute("INSERT INTO charges (id,label,reserved,actual,state,detail,budget_exempt,category) VALUES (?,?,?,?,?,?,?,?)",
                       (key, label, amount, None, "reserved", "{}", int(budget_exempt), category))
        return key

    def settle(self, key: str, actual: float | None, detail: dict):
        """Record actual spend, including overages; unknown spend retains its ceiling."""
        if actual is not None and (not math.isfinite(actual) or actual < 0):
            raise ValueError("Invalid actual charge")
        with self.connect() as db:
            row = db.execute("SELECT state FROM charges WHERE id=?", (key,)).fetchone()
            if row is None or row[0] != "reserved":
                raise ValueError("Reservation absent/already settled")
            db.execute("UPDATE charges SET actual=?, state=?, detail=? WHERE id=?",
                       (actual, "settled" if actual is not None else "unknown",
                        json.dumps(detail, allow_nan=False), key))

    def event(self, kind: str, detail: dict):
        with self.connect() as db:
            db.execute("INSERT INTO events(time,kind,detail) VALUES(?,?,?)",
                       (time.time(), kind, json.dumps(detail, allow_nan=False)))

    def summary(self):
        with self.connect() as db:
            rows = db.execute("SELECT label,reserved,actual,state,detail,budget_exempt,category FROM charges").fetchall()
        categories = {}
        for row in rows:
            group = categories.setdefault(row[6], dict(calls=0, accounted_usd=0.,
                known_actual_usd=0., unknown_or_pending_calls=0, wall_seconds=0.,
                input_tokens=0, output_tokens=0, cached_input_tokens=0))
            group['calls'] += 1
            group['accounted_usd'] += 0 if row[5] else (row[2] if row[2] is not None else row[1])
            group['known_actual_usd'] += row[2] or 0
            group['unknown_or_pending_calls'] += row[2] is None
            detail = json.loads(row[4])
            group['wall_seconds'] += detail.get('wall_seconds', 0)
            usage = detail.get('usage') or {}
            turns = usage.get('turns', [usage])
            for turn in turns:
                for key in ('input_tokens', 'output_tokens', 'cached_input_tokens'):
                    group[key] += turn.get(key, 0) or 0
        return {"categories": categories, "budget_usd": self.budget,
                "accounted_usd": sum(r[2] if r[2] is not None else r[1] for r in rows if not r[5]),
                "budget_exempt_calls": sum(bool(r[5]) for r in rows),
                "known_actual_usd": sum(r[2] for r in rows if r[2] is not None),
                "unknown_or_pending_calls": sum(r[2] is None for r in rows),
                "charges": [dict(label=r[0], reserved=r[1], actual=r[2], state=r[3],
                                 detail=json.loads(r[4]), budget_exempt=bool(r[5]), category=r[6]) for r in rows]}


def save(path: Path, value):
    """Atomic replace, for runtime-owned files only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temp.replace(path)
