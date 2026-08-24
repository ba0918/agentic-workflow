import definitely_missing_fixture_dependency


def test_existing_fixture() -> None:
    assert definitely_missing_fixture_dependency.ready()
