"""The agent's memory, kept in SQLite (spec §6.6; this.i 8fwdvgmg, 3yr7nvs7).

An admitted overture is remembered in its requester's scope with its status for as long as
it is pending, and with its outcome until its keptUntil time, unless the requester's seen
lets the agent forget it sooner (6fcnv3q0). Accepted message SAIDs are remembered for the
freshness window so a replay is refused (35wllumn).
"""

import datetime
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = """
create table if not exists overtures (
  requester text not null, said text not null, major integer not null,
  admitted text not null, kept_until text not null, overture text not null,
  batch_exn text not null, due text not null, plan text not null,
  status text not null default 'pending', results text, reason text, ended text,
  primary key (requester, said));
create table if not exists reports (
  said text not null, requester text not null, saids text not null,
  primary key (said, requester));
create table if not exists accepted (said text primary key, dt text not null);
"""


def _t(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _dt(value: str | None) -> datetime.datetime | None:
    return datetime.datetime.fromisoformat(value) if value is not None else None


@dataclass
class Record:
    requester: str
    said: str
    major: int
    admitted: datetime.datetime
    kept_until: datetime.datetime
    overture: dict
    batch_exn: str
    due: datetime.datetime
    plan: dict
    status: str = "pending"
    results: list = field(default_factory=list)
    reason: str | None = None
    ended: datetime.datetime | None = None


class Store:
    def __init__(self, path: Path | str):
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    def admit(self, r: Record) -> None:
        with self.db:
            self.db.execute(
                "insert into overtures (requester, said, major, admitted, kept_until, overture,"
                " batch_exn, due, plan) values (?,?,?,?,?,?,?,?,?)",
                (r.requester, r.said, r.major, _t(r.admitted), _t(r.kept_until),
                 json.dumps(r.overture), r.batch_exn, _t(r.due), json.dumps(r.plan)))

    def _rows(self, where: str, args: tuple) -> list[Record]:
        cur = self.db.execute(
            "select requester, said, major, admitted, kept_until, overture, batch_exn, due,"
            f" plan, status, results, reason, ended from overtures where {where}"
            " order by admitted, said", args)
        return [Record(requester=row[0], said=row[1], major=row[2], admitted=_dt(row[3]),
                       kept_until=_dt(row[4]), overture=json.loads(row[5]), batch_exn=row[6],
                       due=_dt(row[7]), plan=json.loads(row[8]), status=row[9],
                       results=json.loads(row[10]) if row[10] else [], reason=row[11],
                       ended=_dt(row[12])) for row in cur]

    def get(self, requester: str, said: str) -> Record | None:
        rows = self._rows("requester = ? and said = ?", (requester, said))
        return rows[0] if rows else None

    def pending(self, requester: str | None = None) -> list[Record]:
        if requester is None:
            return self._rows("status = 'pending'", ())
        return self._rows("status = 'pending' and requester = ?", (requester,))

    def end(self, requester, said, status, when, *, results=None, reason=None) -> None:
        with self.db:
            cur = self.db.execute(
                "update overtures set status = ?, results = ?, reason = ?, ended = ?"
                " where requester = ? and said = ? and status = 'pending'",
                (status, json.dumps(results or []), reason, _t(when), requester, said))
        if cur.rowcount != 1:
            raise ValueError(f"Overture {said} has already ended or was never admitted.")

    def forget(self, requester: str, saids: list[str]) -> None:
        with self.db:
            self.db.executemany(
                "delete from overtures where requester = ? and said = ? and status != 'pending'",
                [(requester, s) for s in saids])

    def expire(self, now: datetime.datetime) -> None:
        with self.db:
            self.db.execute("delete from overtures where status != 'pending' and kept_until < ?",
                            (_t(now),))

    def report(self, said: str, requester: str, saids: list[str]) -> None:
        with self.db:
            self.db.execute("insert or replace into reports values (?,?,?)",
                            (said, requester, json.dumps(saids)))

    def reported(self, said: str, requester: str) -> list[str]:
        row = self.db.execute("select saids from reports where said = ? and requester = ?",
                              (said, requester)).fetchone()
        return json.loads(row[0]) if row else []

    def accept_once(self, said: str, dt: datetime.datetime) -> bool:
        with self.db:
            cur = self.db.execute("insert or ignore into accepted values (?, ?)", (said, _t(dt)))
        return cur.rowcount == 1

    def prune_accepted(self, before: datetime.datetime) -> None:
        with self.db:
            self.db.execute("delete from accepted where dt < ?", (_t(before),))
