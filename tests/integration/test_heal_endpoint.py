from __future__ import annotations

import pytest


BASE_DOM = """
<html><body>
  <form>
    <button id="btn-submit" class="btn btn-primary" type="submit">Iniciar sesión</button>
  </form>
</body></html>
"""

CHANGED_DOM = """
<html><body>
  <form>
    <button id="new-submit-id" class="btn btn-primary" type="submit">Iniciar sesión</button>
    <button id="new-cancel-id" class="btn btn-secondary" type="button">Cancelar</button>
  </form>
</body></html>
"""


@pytest.mark.asyncio
async def test_heal_returns_404_without_baseline(api_client):
    response = await api_client.post("/heal", json={
        "selector_type":  "xpath",
        "selector_value": "//button[@id='btn-submit']",
        "dom_html":       BASE_DOM,
        "project":        "test_project",
        "test_id":        "test_login",
    })
    assert response.status_code == 404
    assert "baseline" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_heal_finds_element_after_id_change(api_client, baseline_request_payload):
    # 1. Registra baseline
    reg = await api_client.post("/baseline/register", json=baseline_request_payload)
    assert reg.status_code == 201

    # 2. Solicita sanación con DOM que cambió el id
    response = await api_client.post("/heal", json={
        "selector_type":  "xpath",
        "selector_value": "//button[@id='btn-submit']",
        "dom_html":       CHANGED_DOM,
        "project":        "test_project",
        "test_id":        "test_login",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["healed"] is True
    assert body["strategy_used"] == "DOM"
    assert body["new_selector"].startswith("/")
    assert body["confidence"] > 0


@pytest.mark.asyncio
async def test_heal_returns_422_when_element_not_found(api_client, baseline_request_payload):
    await api_client.post("/baseline/register", json=baseline_request_payload)

    empty_dom = "<html><body><div>sin botones</div></body></html>"
    response = await api_client.post("/heal", json={
        "selector_type":  "xpath",
        "selector_value": "//button[@id='btn-submit']",
        "dom_html":       empty_dom,
        "project":        "test_project",
        "test_id":        "test_login",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_heal_validates_empty_selector(api_client):
    response = await api_client.post("/heal", json={
        "selector_type":  "xpath",
        "selector_value": "",          # inválido
        "dom_html":       BASE_DOM,
        "project":        "test_project",
    })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_heal_normalizes_project_name(api_client, baseline_request_payload):
    """Proyecto en mayúsculas debe funcionar igual que en minúsculas."""
    upper_payload = {**baseline_request_payload, "project": "TEST_PROJECT"}
    await api_client.post("/baseline/register", json=upper_payload)

    response = await api_client.post("/heal", json={
        "selector_type":  "xpath",
        "selector_value": "//button[@id='btn-submit']",
        "dom_html":       CHANGED_DOM,
        "project":        "test_project",  # minúsculas
        "test_id":        "test_normalize",
    })
    assert response.status_code == 200
    assert response.json()["healed"] is True
