"""The committed test vectors are exactly what the generator makes (this.i 8kzvymmy)."""

import json

import pytest

from overture import data, errors, vectors

COMMITTED = data.root() / "vectors"


@pytest.fixture(scope="module")
def generated():
    return vectors.generate()


def test_every_scenario_has_a_committed_file_and_nothing_else(generated):
    assert {p.stem for p in COMMITTED.glob("*.json")} == set(generated)


def test_each_committed_vector_matches_a_fresh_generation_byte_for_byte(generated):
    for name, vector in generated.items():
        assert (COMMITTED / f"{name}.json").read_text() == vectors.render(vector), (
            f"vectors/{name}.json is stale; regenerate with python -m overture.vectors")


def test_every_refusal_code_has_its_check_step():
    codes = {v for v in vars(errors).values() if isinstance(v, errors.Code)}
    assert set(vectors.STEPS) == codes


def test_the_refusals_vector_covers_steps_three_to_eleven(generated):
    steps = {e["expect"]["refused"]["step"] for e in generated["refusals"]["exchanges"]
             if "refused" in e["expect"]}
    assert steps == {3, 4, 5, 6, 7, 9, 10, 11}


def test_generation_leaves_keripys_clock_alone(generated):
    from keri.help import helping
    assert helping.nowUTC.__module__ == "keri.help.helping"


def test_main_writes_every_vector(tmp_path, generated, capsys):
    assert vectors.main(["--out", str(tmp_path)]) == 0
    assert {p.stem for p in tmp_path.glob("*.json")} == set(generated)
    assert json.loads((tmp_path / "seen.json").read_text())["spec"].startswith("§")
