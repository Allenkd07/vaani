import pytest
from fastapi.testclient import TestClient

from app.main import app, settings


@pytest.fixture
def web():
    if not (settings.frontend_dist / "index.html").is_file():
        pytest.skip("frontend not built (run npm run build)")
    return TestClient(app)


def test_hashed_assets_are_cached_and_compressed(web):
    asset = next(path for path in (settings.frontend_dist / "assets").iterdir() if path.suffix == ".js")
    response = web.get(f"/assets/{asset.name}", headers={"Accept-Encoding": "gzip"})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["content-encoding"] == "gzip"


def test_index_and_client_routes_are_revalidated(web):
    for path in ("/", "/dashboard"):
        response = web.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"


def test_unhashed_files_are_revalidated(web):
    assert web.get("/pcm-recorder.worklet.js").headers["cache-control"] == "no-cache"
