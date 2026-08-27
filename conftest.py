import pytest

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture(autouse=True)
def api_token(monkeypatch):
    monkeypatch.setenv("API_TOKEN", "test-token")


@pytest.fixture(autouse=True)
def maia_weights_dir(tmp_path, monkeypatch):
    # ponytail: stub catalog so POST /games default 1900 works in every test
    d = tmp_path / "maia_weights"
    d.mkdir()
    for n in (1100, 1500, 1900):
        (d / f"maia-{n}.pb.gz").write_bytes(b"")
    monkeypatch.setenv("MAIA_WEIGHTS_DIR", str(d))
    return d
