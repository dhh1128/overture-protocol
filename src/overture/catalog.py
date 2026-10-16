"""Catalog entries: SAIDified JSON Schemas for an action's params (spec §8; this.i 0nztkj2q).

An entry's top-level ``$id`` is its SAID, computed and verified by ACDC 1.0's schema rules,
which keripy implements as a Saider over the entry with ``$id`` as the SAID field.
"""

import json
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator
from keri.core.coring import Saider

from . import data

ID = "$id"


def saidify(entry: dict) -> dict:
    """Return a copy of ``entry`` whose ``$id`` is its SAID."""
    saider, sad = Saider.saidify(sad=dict(entry), label=ID)
    return sad


def verify(entry: dict) -> bool:
    """Return True if ``entry``'s ``$id`` is the SAID of the entry."""
    if not entry.get(ID):
        return False
    return Saider(qb64=entry[ID]).verify(entry, prefixed=True, label=ID)


def load(directory: Path) -> dict[str, dict]:
    """Load every entry in ``directory``, refusing any whose SAID does not verify."""
    found = {}
    for path in sorted(directory.glob("*.json")):
        entry = json.loads(path.read_text())
        if not verify(entry):
            raise ValueError(f"The catalog entry in {path.name} does not match its $id SAID.")
        found[entry[ID]] = entry
    return found


@cache
def entries() -> dict[str, dict]:
    """The catalog entries this package ships, by SAID."""
    return load(data.root() / "catalog")


def lookup(said: str) -> dict | None:
    """Return the shipped entry with this SAID, or None if it is not known."""
    return entries().get(said)


def by_title(title: str) -> dict:
    """Return the shipped entry with this title."""
    for entry in entries().values():
        if entry["title"] == title:
            return entry
    raise KeyError(title)


def param_errors(entry: dict, params: dict) -> list[str]:
    """Return one sentence per way ``params`` fails the entry, or an empty list."""
    found = Draft202012Validator(entry).iter_errors(params)
    return [f"At {e.json_path}: {e.message}." for e in sorted(found, key=str)]


def main(argv: list[str] | None = None) -> None:
    """``python -m overture.catalog saidify FILE...`` sets each entry's ``$id`` to its SAID."""
    import argparse

    parser = argparse.ArgumentParser(prog="python -m overture.catalog")
    parser.add_argument("verb", choices=["saidify"])
    parser.add_argument("files", nargs="+", type=Path)
    args = parser.parse_args(argv)
    for path in args.files:
        entry = saidify(json.loads(path.read_text()))
        path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n")
        print(f"{path}: {entry[ID]}")


if __name__ == "__main__":  # pragma: no cover
    main()
