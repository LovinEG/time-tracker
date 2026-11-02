def test_static_page_assets_and_api_are_available(client, clock):
    page = client.get("/")
    script = client.get("/app.js")
    health = client.get("/api/health")

    assert page.status_code == 200
    assert "Учёт времени" in page.text
    assert script.status_code == 200
    assert "function formatDuration" in script.text
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
