from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_register_baseline_returns_201(api_client, baseline_request_payload):
    response = await api_client.post("/baseline/register", json=baseline_request_payload)
    assert response.status_code == 201
    body = response.json()
    assert body["selector_value"] == "//button[@id='btn-submit']"
    assert body["tag"] == "button"
    assert body["heal_count"] == 0


@pytest.mark.asyncio
async def test_register_baseline_upserts(api_client, baseline_request_payload):
    r1 = await api_client.post("/baseline/register", json=baseline_request_payload)
    r2 = await api_client.post("/baseline/register", json=baseline_request_payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]  # mismo registro


@pytest.mark.asyncio
async def test_list_baselines_by_project(api_client, baseline_request_payload):
    await api_client.post("/baseline/register", json=baseline_request_payload)

    response = await api_client.get("/baseline/test_project")
    assert response.status_code == 200
    body = response.json()
    assert body["project"] == "test_project"
    assert body["total"] >= 1
    assert any(
        item["selector_value"] == "//button[@id='btn-submit']"
        for item in body["items"]
    )


@pytest.mark.asyncio
async def test_get_baseline_by_selector(api_client, baseline_request_payload):
    await api_client.post("/baseline/register", json=baseline_request_payload)

    selector = "//button[@id='btn-submit']"
    response = await api_client.get(f"/baseline/test_project/{selector}")
    assert response.status_code == 200
    body = response.json()
    assert body["selector_value"] == selector


@pytest.mark.asyncio
async def test_get_baseline_not_found(api_client):
    response = await api_client.get("/baseline/proyecto_x///selector/inexistente")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_register_validates_missing_tag(api_client, baseline_request_payload):
    bad_payload = {
        **baseline_request_payload,
        "element_meta": {**baseline_request_payload["element_meta"], "tag": ""},
    }
    response = await api_client.post("/baseline/register", json=bad_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_health_endpoint(api_client):
    response = await api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body


@pytest.mark.asyncio
async def test_metrics_endpoint_empty_project(api_client):
    response = await api_client.get("/metrics/proyecto_vacio")
    assert response.status_code == 200
    body = response.json()
    assert body["total_healings"] == 0
    assert body["by_strategy"]["DOM"] == 0
    assert body["by_strategy"]["CV"] == 0


@pytest.mark.asyncio
async def test_history_endpoint_empty(api_client):
    response = await api_client.get("/history/proyecto_vacio")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []
