"""Catalog entries (spec §8; this.i 0nztkj2q, 4zmcmynl)."""

import json
import re

import pytest
from jsonschema import Draft202012Validator

from overture import catalog, data

GCD_SCHEMA = "ELDiEui48xsASGvDcNdsOwPptW0v4i-oN6-75_I1d60c"
EFFECTS = "observe|create|modify|preserve|destroy"
KINDS = "info|record|commitment|authority|resource|relationship"
ACT = re.compile(rf"^(?:{EFFECTS}) (?:{KINDS})$")
SAID = "EAbcdefghijklmnopqrstuvwxyz0123456789_-ABCDE"
AID = "DKxy2sgzfplyr-tgwIxS19f2OchFHtLwPWD3v4oYimBx"


def entry_files():
    return sorted((data.root() / "catalog").glob("*.json"))


def test_the_initial_entries_are_present():
    titles = {e["title"] for e in catalog.entries().values()}
    assert titles == {
        "Issue a credential", "Revoke a credential", "Introduce me",
        "Accept an introduction", "Challenge me", "Create a relationship AID",
        "Start a protocol",
    }


@pytest.mark.parametrize("path", entry_files(), ids=lambda p: p.stem)
def test_each_file_is_a_verified_saidified_schema(path):
    entry = json.loads(path.read_text())
    assert catalog.verify(entry)
    Draft202012Validator.check_schema(entry)
    assert entry["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert entry["additionalProperties"] is False


@pytest.mark.parametrize("path", entry_files(), ids=lambda p: p.stem)
def test_each_entry_places_its_action_on_the_gcd_grid(path):
    ann = json.loads(path.read_text())["overture"]
    assert ann["gcdSchema"] == GCD_SCHEMA
    assert ann["acts"] and all(ACT.match(a) for a in ann["acts"])
    entry = json.loads(path.read_text())
    for pointer in ann["targets"]:
        assert pointer.startswith("/")
        assert pointer[1:] in entry["properties"]


def test_a_changed_entry_no_longer_verifies():
    entry = dict(next(iter(catalog.entries().values())))
    entry["title"] = entry["title"] + "!"
    assert not catalog.verify(entry)


def test_an_entry_without_an_id_does_not_verify():
    assert not catalog.verify({"title": "x"})


def test_saidify_fills_the_id_so_that_it_verifies():
    entry = catalog.saidify({"$id": "", "title": "x", "type": "object"})
    assert catalog.verify(entry)
    assert entry["$id"].startswith("E") and len(entry["$id"]) == 44


def test_entries_are_indexed_by_their_said():
    for said, entry in catalog.entries().items():
        assert entry["$id"] == said


def test_lookup_returns_none_for_an_unknown_action():
    assert catalog.lookup(SAID) is None


def test_params_validate_against_the_entry():
    issue = catalog.by_title("Issue a credential")
    assert catalog.param_errors(issue, {"schema": SAID, "issuee": AID}) == []
    assert catalog.param_errors(issue, {"schema": SAID}) != []
    assert catalog.param_errors(issue, {"schema": SAID, "issuee": AID, "extra": 1}) != []


def test_by_title_raises_for_an_unknown_title():
    with pytest.raises(KeyError):
        catalog.by_title("Teleport me")


def test_a_tampered_file_is_refused_when_loading(tmp_path):
    good = json.loads(entry_files()[0].read_text())
    good["title"] = "tampered"
    (tmp_path / "catalog").mkdir()
    (tmp_path / "catalog" / "x.json").write_text(json.dumps(good))
    with pytest.raises(ValueError, match="does not match"):
        catalog.load(tmp_path / "catalog")


def test_the_saidify_command_rewrites_a_file_with_its_said(tmp_path, capsys):
    path = tmp_path / "x.json"
    path.write_text(json.dumps({"$id": "", "title": "x", "type": "object"}))
    catalog.main(["saidify", str(path)])
    entry = json.loads(path.read_text())
    assert catalog.verify(entry)
    assert entry["$id"] in capsys.readouterr().out


def test_the_command_refuses_other_verbs():
    with pytest.raises(SystemExit):
        catalog.main(["publish", "x.json"])
