from overture import data


def test_source_checkout_reads_the_repository_root(tmp_path):
    missing = tmp_path / "absent"
    assert (data.root(missing) / "schemas").is_dir()


def test_wheel_reads_its_packaged_copy(tmp_path):
    assert data.root(tmp_path) == tmp_path
