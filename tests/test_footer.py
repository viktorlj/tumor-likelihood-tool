from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.scoring import TumorLikelihoodModel


HTML_ROUTES = ["/", "/tumor-profile", "/gene-profile", "/tutorial"]
GENIE_HOMEPAGE_URL = "https://genie.synapse.org/"
GENIE_MANUSCRIPT_DOI = "https://doi.org/10.1158/2159-8290.CD-17-0151"
GENIE_LOGO_SRC = "/static/genie-logo.jpeg"
DISCLAIMER_TEXT = "For research use and clinical decision support only"


@pytest.fixture()
def client(synthetic_data_dir):
    model = TumorLikelihoodModel.from_data_dir(synthetic_data_dir)
    app = create_app(data_dir=synthetic_data_dir, model=model)
    return TestClient(app)


@pytest.mark.parametrize("route", HTML_ROUTES)
def test_footer_renders_on_every_page(client, route):
    response = client.get(route)
    assert response.status_code == 200
    body = response.text
    assert 'class="mp-footer"' in body, f"footer container missing on {route}"
    assert GENIE_LOGO_SRC in body, f"GENIE logo missing on {route}"
    assert GENIE_HOMEPAGE_URL in body, f"GENIE homepage link missing on {route}"
    assert GENIE_MANUSCRIPT_DOI in body, f"GENIE manuscript link missing on {route}"
    assert DISCLAIMER_TEXT in body, f"disclaimer missing on {route}"


def test_footer_logo_asset_is_served(client):
    response = client.get(GENIE_LOGO_SRC)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/")
