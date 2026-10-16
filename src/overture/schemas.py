"""Shape checks for each route's ``a`` block (spec §6.1 step 6; this.i 2uvl4uuz)."""

import json
from functools import cache

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from . import data

ROUTES = ("batch", "receipt", "poll", "abort", "status")
MAJOR = 1
BASE = f"https://raw.githubusercontent.com/dhh1128/overture-protocol/main/schemas/{MAJOR}/"


@cache
def _registry() -> Registry:
    resources = []
    for path in sorted((data.root() / "schemas" / str(MAJOR)).glob("*.json")):
        schema = json.loads(path.read_text())
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


def _schema(route: str) -> dict:
    if route not in ROUTES:
        raise KeyError(route)
    return _registry().contents(f"{BASE}{route}.json")


@cache
def _validator(route: str) -> Draft202012Validator:
    return Draft202012Validator(_schema(route), registry=_registry())


def check_schema(route: str) -> None:
    """Raise if the route's schema is not a valid 2020-12 schema."""
    Draft202012Validator.check_schema(_schema(route))


def errors(route: str, a: dict) -> list[str]:
    """Return one sentence per shape problem in ``a``, or an empty list."""
    found = _validator(route).iter_errors(a)
    return [f"At {e.json_path}: {e.message}." for e in sorted(found, key=str)]
